from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.ingestion import RawIngestionService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.models import Base, ProcessingRun, QualityEvent
from app.workspace_adapters.moneki.models import MonekiSale
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_full_dataset_quality_contract_and_golden_metrics() -> None:
    engine = create_engine("sqlite:///:memory:")
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        raw_result = RawIngestionService(registry).ingest(session, "moneki")
        result = ProcessingService(registry).process(session, "moneki")

        assert result.raw_run_id == raw_result.run_id
        assert result.summary == {
            "raw_sales_records": 12_131,
            "accepted_sales_records": 11_869,
            "deduplicated_records": 78,
            "quarantined_records": 184,
            "repair_events": 203,
            "refund_records": 49,
            "store_records": 5,
            "product_records": 20,
        }
        assert session.scalar(select(func.count()).select_from(MonekiSale)) == 11_869

        events = session.scalars(
            select(QualityEvent).where(QualityEvent.processing_run_id == result.processing_run_id)
        ).all()
        event_counts = Counter((event.action, event.reason_code) for event in events)
        assert event_counts == {
            ("repaired", "date_format_normalized"): 150,
            ("repaired", "identifier_normalized"): 13,
            ("repaired", "currency_symbol_removed"): 40,
            ("deduplicated", "canonical_duplicate"): 78,
            ("quarantined", "conflicting_order_id"): 4,
            ("quarantined", "unknown_store"): 7,
            ("quarantined", "unknown_product"): 30,
            ("quarantined", "invalid_quantity"): 24,
            ("quarantined", "missing_or_invalid_amount"): 119,
            ("classified", "refund_preserved"): 49,
        }

        monthly = session.execute(
            select(
                func.strftime("%Y-%m", MonekiSale.sale_date),
                func.sum(MonekiSale.amount_cents),
                func.count(),
            )
            .group_by(func.strftime("%Y-%m", MonekiSale.sale_date))
            .order_by(func.strftime("%Y-%m", MonekiSale.sale_date))
        ).all()
        assert monthly == [
            ("2026-05", 13_944_600, 3_836),
            ("2026-06", 13_244_000, 3_789),
            ("2026-07", 15_152_700, 4_244),
        ]

        repeated = ProcessingService(registry).process(session, "moneki")
        assert repeated.summary == result.summary
        assert session.scalar(select(func.count()).select_from(MonekiSale)) == 11_869
        assert session.scalars(select(ProcessingRun.status).order_by(ProcessingRun.id)).all() == [
            "superseded",
            "completed",
        ]


def test_processing_requires_a_completed_raw_run() -> None:
    engine = create_engine("sqlite:///:memory:")
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        try:
            ProcessingService(registry).process(session, "moneki")
        except LookupError as error:
            assert "no completed raw ingestion" in str(error)
        else:
            raise AssertionError("processing should reject a missing raw run")
