from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.analytics.models import AnalyticsQuery

IntentName = Literal["category_leader", "product_revenue", "aov_trend", "store_comparison"]
ChartTarget = Literal[
    "overview",
    "revenue_trend",
    "product_ranking",
    "category_contribution",
    "aov_trend",
    "store_comparison",
]


class AnalysisContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent: IntentName
    product: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1, max_length=500)
    context: AnalysisContext | None = None


class EvidenceCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    processing_run_id: int
    metric: str
    label: str
    value: int | float
    display_value: str
    dimensions: dict[str, str]
    scope: str


class ChartAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    query: AnalyticsQuery
    target: ChartTarget
    highlight: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["answered", "unsupported"]
    answer: str
    context: AnalysisContext | None = None
    citations: tuple[EvidenceCitation, ...] = ()
    chart_action: ChartAction | None = None
