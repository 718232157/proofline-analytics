from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.processing.models import ProcessingResult
from app.processing.registry import ProcessorRegistry
from app.storage.models import IngestionRun, ProcessingRun
from app.workspaces.registry import WorkspaceRegistry


class ProcessingService:
    """Runs a workspace adapter against the latest completed raw ingestion."""

    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        processor_registry: ProcessorRegistry | None = None,
    ) -> None:
        self.workspace_registry = workspace_registry
        self.processor_registry = processor_registry or ProcessorRegistry(workspace_registry)

    def process(self, session: Session, workspace_slug: str) -> ProcessingResult:
        manifest = self.workspace_registry.load(workspace_slug)
        raw_run = session.scalar(
            select(IngestionRun)
            .where(IngestionRun.workspace_slug == workspace_slug)
            .where(IngestionRun.status == "completed")
            .order_by(IngestionRun.id.desc())
            .limit(1)
        )
        if raw_run is None:
            raise LookupError(f"workspace '{workspace_slug}' has no completed raw ingestion")

        session.execute(
            update(ProcessingRun)
            .where(ProcessingRun.workspace_slug == workspace_slug)
            .where(ProcessingRun.status == "completed")
            .values(status="superseded")
        )
        processing_run = ProcessingRun(
            raw_run_id=raw_run.id,
            workspace_slug=workspace_slug,
            status="running",
            summary={},
        )
        session.add(processing_run)
        session.flush()

        try:
            processor = self.processor_registry.create(workspace_slug)
            summary = processor.process(session, manifest, raw_run, processing_run)
            processing_run.summary = summary
            processing_run.status = "completed"
            processing_run.finished_at = datetime.now(UTC)
            session.commit()
        except Exception:
            session.rollback()
            raise

        return ProcessingResult(
            processing_run_id=processing_run.id,
            raw_run_id=raw_run.id,
            workspace_slug=workspace_slug,
            summary=summary,
        )
