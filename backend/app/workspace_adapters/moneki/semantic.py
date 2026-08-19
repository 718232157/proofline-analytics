from datetime import date
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.analytics.models import AnalyticsQuery, PrimitiveAggregate
from app.workspace_adapters.moneki.models import MonekiProduct, MonekiSale, MonekiStore
from app.workspaces.models import MetricDefinition, WorkspaceManifest


class MonekiSemanticProvider:
    """Maps governed semantic keys to the canonical Moneki schema."""

    def aggregate(
        self,
        session: Session,
        manifest: WorkspaceManifest,
        primitive_metrics: tuple[MetricDefinition, ...],
        query: AnalyticsQuery,
    ) -> list[PrimitiveAggregate]:
        del manifest
        dimensions = self._dimensions(query.date_grain)
        fields: dict[str, Any] = {
            "amount_cents": MonekiSale.amount_cents,
            "order_id": MonekiSale.order_id,
        }
        selected_dimensions: list[Any] = [dimensions[key].label(key) for key in query.group_by]
        selected_metrics: list[Any] = []
        for metric in primitive_metrics:
            assert metric.field is not None
            field = fields[metric.field]
            expression = (
                func.coalesce(func.sum(field), 0)
                if metric.kind == "sum"
                else func.count(distinct(field))
            )
            selected_metrics.append(expression.label(metric.key))

        statement = (
            select(*selected_dimensions, *selected_metrics)
            .select_from(MonekiSale)
            .join(MonekiStore, MonekiStore.store_id == MonekiSale.store_id)
            .join(MonekiProduct, MonekiProduct.product_id == MonekiSale.product_id)
        )
        if query.date_from:
            statement = statement.where(MonekiSale.sale_date >= query.date_from)
        if query.date_to:
            statement = statement.where(MonekiSale.sale_date <= query.date_to)
        for key, values in query.filters.items():
            statement = statement.where(dimensions[key].in_(values))
        if selected_dimensions:
            group_expressions = [dimensions[key] for key in query.group_by]
            statement = statement.group_by(*group_expressions).order_by(*group_expressions)
        statement = statement.limit(query.limit)

        rows = session.execute(statement).mappings().all()
        return [
            PrimitiveAggregate(
                dimensions={key: str(row[key]) for key in query.group_by},
                values={metric.key: int(row[metric.key]) for metric in primitive_metrics},
            )
            for row in rows
        ]

    def date_range(self, session: Session, manifest: WorkspaceManifest) -> tuple[date, date] | None:
        del manifest
        first, last = session.execute(
            select(func.min(MonekiSale.sale_date), func.max(MonekiSale.sale_date))
        ).one()
        if first is None or last is None:
            return None
        return first, last

    @staticmethod
    def _dimensions(date_grain: str) -> dict[str, Any]:
        date_expression: Any = (
            func.strftime("%Y-%m", MonekiSale.sale_date)
            if date_grain == "month"
            else func.strftime("%Y-%m-%d", MonekiSale.sale_date)
        )
        return {
            "date": date_expression,
            "store": MonekiStore.store_name,
            "store_category": MonekiStore.category,
            "product": MonekiProduct.product_name,
            "product_category": MonekiProduct.product_category,
        }
