from typing import Literal

from pydantic import BaseModel, ConfigDict


class Insight(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["performance_pulse", "growth_driver"]
    tone: Literal["positive", "watch", "neutral"]
    title: str
    narrative: str
    evidence_ids: tuple[str, ...]


class InsightFeed(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace: str
    period: str
    insights: tuple[Insight, ...]
