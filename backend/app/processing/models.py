from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.storage.models import IngestionRun, ProcessingRun
from app.workspaces.models import WorkspaceManifest


@dataclass(frozen=True)
class ProcessingResult:
    processing_run_id: int
    raw_run_id: int
    workspace_slug: str
    summary: dict[str, int]


class WorkspaceProcessor(Protocol):
    """Contract implemented by first-party workspace adapters."""

    def process(
        self,
        session: Session,
        manifest: WorkspaceManifest,
        raw_run: IngestionRun,
        processing_run: ProcessingRun,
    ) -> dict[str, int]: ...
