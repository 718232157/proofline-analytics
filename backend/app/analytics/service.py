import hashlib
import json
from collections.abc import Iterable
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.models import (
    AnalyticsQuery,
    MetricPoint,
    MetricResult,
    QueryEvidence,
)
from app.analytics.registry import SemanticProviderRegistry
from app.storage.models import ProcessingRun
from app.workspaces.models import MetricDefinition
from app.workspaces.registry import WorkspaceRegistry


class InvalidAnalyticsQuery(ValueError):
    """Raised when a query escapes the workspace semantic contract."""


class AnalyticsService:
    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        provider_registry: SemanticProviderRegistry | None = None,
    ) -> None:
        self.workspace_registry = workspace_registry
        self.provider_registry = provider_registry or SemanticProviderRegistry(workspace_registry)

    def query(self, session: Session, workspace_slug: str, query: AnalyticsQuery) -> MetricResult:
        manifest = self.workspace_registry.load(workspace_slug)
        metric_map = {metric.key: metric for metric in manifest.metrics}
        dimension_keys = {dimension.key for dimension in manifest.dimensions}
        metric = metric_map.get(query.metric)
        if metric is None:
            raise InvalidAnalyticsQuery(f"unknown metric '{query.metric}'")

        requested_dimensions = set(query.group_by) | set(query.filters)
        unknown_dimensions = requested_dimensions - dimension_keys
        if unknown_dimensions:
            unknown = ", ".join(sorted(unknown_dimensions))
            raise InvalidAnalyticsQuery(f"unknown dimension(s): {unknown}")
        if len(query.group_by) != len(set(query.group_by)):
            raise InvalidAnalyticsQuery("group_by dimensions must be unique")
        if any(not values for values in query.filters.values()):
            raise InvalidAnalyticsQuery("filter value lists must not be empty")

        processing_run_id = session.scalar(
            select(func.max(ProcessingRun.id)).where(
                ProcessingRun.workspace_slug == workspace_slug,
                ProcessingRun.status == "completed",
            )
        )
        if processing_run_id is None:
            raise LookupError(f"workspace '{workspace_slug}' has no completed processing run")

        primitive_metrics = tuple(
            {
                primitive.key: primitive
                for primitive in self._primitive_metrics(metric, metric_map)
            }.values()
        )
        aggregates = self.provider_registry.create(workspace_slug).aggregate(
            session, manifest, primitive_metrics, query
        )
        points = tuple(
            MetricPoint(
                dimensions=row.dimensions,
                value=self._metric_value(metric, row.values, metric_map),
            )
            for row in aggregates
        )
        scope = self._scope(query)
        evidence_payload = {
            "workspace": workspace_slug,
            "processing_run_id": processing_run_id,
            "query": query.model_dump(mode="json"),
        }
        evidence_id = hashlib.sha256(
            json.dumps(evidence_payload, sort_keys=True).encode()
        ).hexdigest()[:16]
        return MetricResult(
            workspace=workspace_slug,
            metric=metric.key,
            label=metric.label,
            format=metric.format,
            currency=manifest.workspace.currency if metric.format == "currency" else None,
            points=points,
            evidence=QueryEvidence(
                evidence_id=evidence_id,
                processing_run_id=processing_run_id,
                metric_definition=metric.description,
                scope=scope,
                row_count=len(points),
            ),
        )

    def date_range(self, session: Session, workspace_slug: str) -> tuple[date, date] | None:
        manifest = self.workspace_registry.load(workspace_slug)
        return self.provider_registry.create(workspace_slug).date_range(session, manifest)

    def _primitive_metrics(
        self,
        metric: MetricDefinition,
        metric_map: dict[str, MetricDefinition],
    ) -> Iterable[MetricDefinition]:
        if metric.kind != "ratio":
            yield metric
            return
        assert metric.numerator is not None
        assert metric.denominator is not None
        yield from self._primitive_metrics(metric_map[metric.numerator], metric_map)
        yield from self._primitive_metrics(metric_map[metric.denominator], metric_map)

    @staticmethod
    def _metric_value(
        metric: MetricDefinition,
        values: dict[str, int],
        metric_map: dict[str, MetricDefinition],
    ) -> int | float:
        if metric.kind != "ratio":
            return values[metric.key]
        assert metric.numerator is not None
        assert metric.denominator is not None
        numerator = AnalyticsService._metric_value(metric_map[metric.numerator], values, metric_map)
        denominator = AnalyticsService._metric_value(
            metric_map[metric.denominator], values, metric_map
        )
        return round(numerator / denominator, 2) if denominator else 0

    @staticmethod
    def _scope(query: AnalyticsQuery) -> str:
        parts: list[str] = []
        if query.date_from or query.date_to:
            parts.append(f"date={query.date_from or '*'}..{query.date_to or '*'}")
        parts.extend(f"{key}={','.join(values)}" for key, values in sorted(query.filters.items()))
        if query.group_by:
            parts.append(f"group_by={','.join(query.group_by)}")
        return "; ".join(parts) if parts else "all accepted records"
