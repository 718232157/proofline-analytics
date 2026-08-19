from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.quality.models import QualityReason, QualitySummary
from app.storage.models import ProcessingRun, QualityEvent


class QualityService:
    def summary(self, session: Session, workspace_slug: str) -> QualitySummary:
        run = session.scalar(
            select(ProcessingRun)
            .where(
                ProcessingRun.workspace_slug == workspace_slug,
                ProcessingRun.status == "completed",
            )
            .order_by(ProcessingRun.id.desc())
            .limit(1)
        )
        if run is None:
            raise LookupError(f"workspace '{workspace_slug}' has no completed processing run")
        reason_rows = session.execute(
            select(QualityEvent.action, QualityEvent.reason_code, func.count())
            .where(QualityEvent.processing_run_id == run.id)
            .group_by(QualityEvent.action, QualityEvent.reason_code)
            .order_by(QualityEvent.action, QualityEvent.reason_code)
        ).all()
        summary = run.summary
        raw_count = int(summary["raw_sales_records"])
        accepted_count = int(summary["accepted_sales_records"])
        return QualitySummary(
            workspace=workspace_slug,
            processing_run_id=run.id,
            raw_sales_records=raw_count,
            accepted_sales_records=accepted_count,
            deduplicated_records=int(summary["deduplicated_records"]),
            quarantined_records=int(summary["quarantined_records"]),
            repair_events=int(summary["repair_events"]),
            refund_records=int(summary["refund_records"]),
            acceptance_rate=round(accepted_count / raw_count * 100, 2),
            reasons=tuple(
                QualityReason(action=action, reason_code=reason_code, count=count)
                for action, reason_code, count in reason_rows
            ),
        )
