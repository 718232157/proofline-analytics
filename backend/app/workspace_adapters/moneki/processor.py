import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, TypedDict

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.storage.models import IngestionRun, ProcessingRun, QualityEvent, RawRecord
from app.workspace_adapters.moneki.models import MonekiProduct, MonekiSale, MonekiStore
from app.workspace_adapters.moneki.normalization import (
    normalize_identifier,
    normalize_text,
    parse_date,
    parse_integer,
    parse_money_to_cents,
)
from app.workspaces.models import WorkspaceManifest


@dataclass(frozen=True)
class SaleCandidate:
    source_row_number: int
    order_id: str
    sale_date: date | None
    raw_date: str | None
    store_id: str | None
    product_id: str | None
    quantity: int | None
    raw_quantity: str | None
    amount_cents: int | None
    raw_amount: str | None
    payment_method: str | None
    repairs: tuple[tuple[str, dict[str, Any]], ...]

    @property
    def signature(self) -> str:
        canonical = (
            self.order_id,
            self.sale_date.isoformat() if self.sale_date else f"invalid:{self.raw_date}",
            self.store_id,
            self.product_id,
            self.quantity if self.quantity is not None else f"invalid:{self.raw_quantity}",
            self.amount_cents if self.amount_cents is not None else f"invalid:{self.raw_amount}",
            self.payment_method,
        )
        return json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))


class StoreRecord(TypedDict):
    store_id: str
    store_name: str
    category: str
    district: str


class ProductRecord(TypedDict):
    product_id: str
    product_name: str
    product_category: str
    unit_price_cents: int


class MonekiProcessor:
    """Canonicalizes the Moneki workspace using explicit, auditable policy."""

    def process(
        self,
        session: Session,
        manifest: WorkspaceManifest,
        raw_run: IngestionRun,
        processing_run: ProcessingRun,
    ) -> dict[str, int]:
        del manifest  # The validated manifest selected this adapter; rules live here.
        self._clear_current_canonical_data(session)

        stores = self._canonicalize_stores(session, raw_run)
        products = self._canonicalize_products(session, raw_run)
        candidates = self._normalize_sales(session, raw_run)

        events: list[dict[str, object]] = []
        for candidate in candidates:
            for reason_code, details in candidate.repairs:
                events.append(
                    self._event(processing_run, candidate, "repaired", reason_code, details)
                )

        primary_candidates, duplicate_events = self._deduplicate(candidates, processing_run)
        events.extend(duplicate_events)

        conflict_ids = {
            order_id
            for order_id, rows in self._group_by_order(primary_candidates).items()
            if len(rows) > 1
        }

        accepted: list[dict[str, object]] = []
        quarantined = 0
        refunds = 0
        for candidate in primary_candidates:
            quarantine_reason = self._quarantine_reason(candidate, stores, products, conflict_ids)
            if quarantine_reason:
                quarantined += 1
                events.append(
                    self._event(
                        processing_run,
                        candidate,
                        "quarantined",
                        quarantine_reason,
                        {},
                    )
                )
                continue

            assert candidate.sale_date is not None
            assert candidate.store_id is not None
            assert candidate.product_id is not None
            assert candidate.quantity is not None
            assert candidate.amount_cents is not None
            assert candidate.payment_method is not None
            accepted.append(
                {
                    "processing_run_id": processing_run.id,
                    "source_row_number": candidate.source_row_number,
                    "order_id": candidate.order_id,
                    "sale_date": candidate.sale_date,
                    "store_id": candidate.store_id,
                    "product_id": candidate.product_id,
                    "quantity": candidate.quantity,
                    "amount_cents": candidate.amount_cents,
                    "payment_method": candidate.payment_method,
                }
            )
            if candidate.amount_cents < 0:
                refunds += 1
                events.append(
                    self._event(
                        processing_run,
                        candidate,
                        "classified",
                        "refund_preserved",
                        {"amount_cents": candidate.amount_cents},
                    )
                )

        if accepted:
            session.execute(insert(MonekiSale), accepted)
        if events:
            session.execute(insert(QualityEvent), events)

        return {
            "raw_sales_records": len(candidates),
            "accepted_sales_records": len(accepted),
            "deduplicated_records": len(duplicate_events),
            "quarantined_records": quarantined,
            "repair_events": sum(event["action"] == "repaired" for event in events),
            "refund_records": refunds,
            "store_records": len(stores),
            "product_records": len(products),
        }

    @staticmethod
    def _clear_current_canonical_data(session: Session) -> None:
        session.execute(delete(MonekiSale))
        session.execute(delete(MonekiProduct))
        session.execute(delete(MonekiStore))

    @staticmethod
    def _raw_records(session: Session, raw_run: IngestionRun, source_name: str) -> list[RawRecord]:
        return list(
            session.scalars(
                select(RawRecord)
                .where(RawRecord.run_id == raw_run.id)
                .where(RawRecord.source_name == source_name)
                .order_by(RawRecord.source_row_number)
            )
        )

    def _canonicalize_stores(
        self, session: Session, raw_run: IngestionRun
    ) -> dict[str, StoreRecord]:
        stores: dict[str, StoreRecord] = {}
        for record in self._raw_records(session, raw_run, "stores"):
            store_id = normalize_identifier(record.payload.get("store_id")).value
            store_name = normalize_text(record.payload.get("store_name"))
            category = normalize_text(record.payload.get("category"))
            district = normalize_text(record.payload.get("district"))
            if store_id is None or store_name is None or category is None or district is None:
                raise ValueError(
                    f"invalid store dimension at source row {record.source_row_number}"
                )
            if store_id in stores:
                raise ValueError(f"duplicate store dimension key: {store_id}")
            stores[store_id] = {
                "store_id": store_id,
                "store_name": store_name,
                "category": category,
                "district": district,
            }
        session.execute(insert(MonekiStore), list(stores.values()))
        return stores

    def _canonicalize_products(
        self, session: Session, raw_run: IngestionRun
    ) -> dict[str, ProductRecord]:
        products: dict[str, ProductRecord] = {}
        for record in self._raw_records(session, raw_run, "products"):
            product_id = normalize_identifier(record.payload.get("product_id")).value
            product_name = normalize_text(record.payload.get("product_name"))
            product_category = normalize_text(record.payload.get("product_category"))
            unit_price_cents = parse_money_to_cents(record.payload.get("unit_price")).value
            if (
                product_id is None
                or product_name is None
                or product_category is None
                or unit_price_cents is None
            ):
                raise ValueError(
                    f"invalid product dimension at source row {record.source_row_number}"
                )
            if product_id in products:
                raise ValueError(f"duplicate product dimension key: {product_id}")
            products[product_id] = {
                "product_id": product_id,
                "product_name": product_name,
                "product_category": product_category,
                "unit_price_cents": unit_price_cents,
            }
        session.execute(insert(MonekiProduct), list(products.values()))
        return products

    def _normalize_sales(self, session: Session, raw_run: IngestionRun) -> list[SaleCandidate]:
        candidates: list[SaleCandidate] = []
        for record in self._raw_records(session, raw_run, "sales"):
            payload = record.payload
            order_id_value = normalize_identifier(payload.get("order_id"))
            date_value = parse_date(payload.get("date"))
            store_value = normalize_identifier(payload.get("store_id"))
            product_value = normalize_identifier(payload.get("product_id"))
            quantity_value = parse_integer(payload.get("qty"))
            amount_value = parse_money_to_cents(payload.get("amount"))
            payment_method = normalize_text(payload.get("payment"))
            if order_id_value.value is None:
                order_id = f"missing-row-{record.source_row_number}"
            else:
                order_id = order_id_value.value

            repairs: list[tuple[str, dict[str, Any]]] = []
            for normalized, field_name, original in (
                (date_value, "date", payload.get("date")),
                (store_value, "store_id", payload.get("store_id")),
                (product_value, "product_id", payload.get("product_id")),
                (amount_value, "amount", payload.get("amount")),
            ):
                if normalized.repair_reason:
                    repairs.append(
                        (
                            normalized.repair_reason,
                            {"field": field_name, "original": original},
                        )
                    )

            candidates.append(
                SaleCandidate(
                    source_row_number=record.source_row_number,
                    order_id=order_id,
                    sale_date=date_value.value,
                    raw_date=payload.get("date"),
                    store_id=store_value.value,
                    product_id=product_value.value,
                    quantity=quantity_value.value,
                    raw_quantity=payload.get("qty"),
                    amount_cents=amount_value.value,
                    raw_amount=payload.get("amount"),
                    payment_method=payment_method,
                    repairs=tuple(repairs),
                )
            )
        return candidates

    def _deduplicate(
        self,
        candidates: list[SaleCandidate],
        processing_run: ProcessingRun,
    ) -> tuple[list[SaleCandidate], list[dict[str, object]]]:
        seen: dict[str, SaleCandidate] = {}
        primary: list[SaleCandidate] = []
        events: list[dict[str, object]] = []
        for candidate in candidates:
            original = seen.get(candidate.signature)
            if original is None:
                seen[candidate.signature] = candidate
                primary.append(candidate)
                continue
            events.append(
                self._event(
                    processing_run,
                    candidate,
                    "deduplicated",
                    "canonical_duplicate",
                    {"kept_source_row_number": original.source_row_number},
                )
            )
        return primary, events

    @staticmethod
    def _group_by_order(candidates: list[SaleCandidate]) -> dict[str, list[SaleCandidate]]:
        grouped: dict[str, list[SaleCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.order_id].append(candidate)
        return grouped

    @staticmethod
    def _quarantine_reason(
        candidate: SaleCandidate,
        stores: dict[str, StoreRecord],
        products: dict[str, ProductRecord],
        conflict_ids: set[str],
    ) -> str | None:
        if candidate.order_id in conflict_ids:
            return "conflicting_order_id"
        if candidate.sale_date is None:
            return "invalid_date"
        if candidate.store_id not in stores:
            return "unknown_store"
        if candidate.product_id not in products:
            return "unknown_product"
        if candidate.quantity is None or candidate.quantity <= 0:
            return "invalid_quantity"
        if candidate.amount_cents is None:
            return "missing_or_invalid_amount"
        assert candidate.product_id is not None
        unit_price_cents = products[candidate.product_id]["unit_price_cents"]
        if abs(candidate.amount_cents) != candidate.quantity * unit_price_cents:
            return "amount_unit_price_mismatch"
        if candidate.payment_method is None:
            return "missing_payment_method"
        return None

    @staticmethod
    def _event(
        processing_run: ProcessingRun,
        candidate: SaleCandidate,
        action: str,
        reason_code: str,
        details: dict[str, Any],
    ) -> dict[str, object]:
        return {
            "processing_run_id": processing_run.id,
            "source_name": "sales",
            "source_row_number": candidate.source_row_number,
            "record_key": candidate.order_id,
            "action": action,
            "reason_code": reason_code,
            "details": details,
        }
