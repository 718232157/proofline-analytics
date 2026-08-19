from typing import Literal

from pydantic import BaseModel, ConfigDict


class Insight(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["performance_pulse", "growth_driver", "daily_signal"]
    tone: Literal["positive", "watch", "neutral"]
    priority: Literal["high", "medium", "low"]
    title: str
    narrative: str
    action: str
    impact_display: str
    target: Literal["revenue_trend", "product_ranking", "store_comparison"]
    highlight: str | None = None
    evidence_ids: tuple[str, ...]


class InsightFeed(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace: str
    period: str
    insights: tuple[Insight, ...]
