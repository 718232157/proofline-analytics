from pydantic import BaseModel, ConfigDict


class QualityReason(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str
    reason_code: str
    count: int


class QualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace: str
    processing_run_id: int
    raw_sales_records: int
    accepted_sales_records: int
    deduplicated_records: int
    quarantined_records: int
    repair_events: int
    refund_records: int
    acceptance_rate: float
    reasons: tuple[QualityReason, ...]
