from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkspaceMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    name: str
    description: str
    locale: str
    currency: str = Field(min_length=3, max_length=3)
    timezone: str
    processor: str = Field(pattern=r"^[a-zA-Z0-9_.]+:[A-Za-z][A-Za-z0-9_]*$")
    semantic_provider: str = Field(pattern=r"^[a-zA-Z0-9_.]+:[A-Za-z][A-Za-z0-9_]*$")


class SourceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: Literal["csv"]
    path: str
    role: Literal["fact", "dimension"]


class RelationDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_field: str = Field(alias="from")
    target_field: str = Field(alias="to")
    cardinality: Literal["many_to_one", "one_to_one"]


class DimensionDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    data_type: Literal["date", "entity", "category"]


class MetricDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    kind: Literal["sum", "count_distinct", "ratio"]
    field: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    format: Literal["currency", "integer", "decimal"]
    description: str

    @model_validator(mode="after")
    def validate_metric_operands(self) -> "MetricDefinition":
        if self.kind in {"sum", "count_distinct"} and not self.field:
            raise ValueError(f"{self.kind} metric requires field")
        if self.kind == "ratio" and not (self.numerator and self.denominator):
            raise ValueError("ratio metric requires numerator and denominator")
        return self


class SuggestedQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str


class WorkspaceManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace: WorkspaceMetadata
    sources: tuple[SourceDefinition, ...]
    relations: tuple[RelationDefinition, ...] = ()
    dimensions: tuple[DimensionDefinition, ...] = ()
    metrics: tuple[MetricDefinition, ...] = ()
    suggested_questions: tuple[SuggestedQuestion, ...] = ()

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "WorkspaceManifest":
        for label, values in (
            ("source", [source.name for source in self.sources]),
            ("dimension", [dimension.key for dimension in self.dimensions]),
            ("metric", [metric.key for metric in self.metrics]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} key in workspace manifest")

        metric_keys = {metric.key for metric in self.metrics}
        for metric in self.metrics:
            if (
                metric.kind == "ratio"
                and {
                    metric.numerator,
                    metric.denominator,
                }
                - metric_keys
            ):
                raise ValueError(f"ratio metric {metric.key} references an unknown metric")
        return self
