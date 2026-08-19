from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.workspaces.models import MetricDefinition, WorkspaceManifest


class AnalyticsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    group_by: tuple[str, ...] = Field(default=(), max_length=2)
    filters: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    date_from: date | None = None
    date_to: date | None = None
    date_grain: str = Field(default="day", pattern=r"^(day|month)$")
    limit: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_dates(self) -> "AnalyticsQuery":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self


class PrimitiveAggregate(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimensions: dict[str, str]
    values: dict[str, int]


class MetricPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimensions: dict[str, str]
    value: int | float


class QueryEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    processing_run_id: int
    metric_definition: str
    scope: str
    row_count: int


class MetricResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace: str
    metric: str
    label: str
    format: str
    currency: str | None
    points: tuple[MetricPoint, ...]
    evidence: QueryEvidence


class SemanticProvider(Protocol):
    def aggregate(
        self,
        session: Session,
        manifest: WorkspaceManifest,
        primitive_metrics: tuple[MetricDefinition, ...],
        query: AnalyticsQuery,
    ) -> list[PrimitiveAggregate]: ...
