import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, insert, update
from sqlalchemy.orm import Session

from app.storage.models import IngestionRun, RawRecord
from app.workspaces.registry import WorkspaceRegistry


@dataclass(frozen=True)
class IngestionResult:
    run_id: int
    workspace_slug: str
    source_counts: dict[str, int]

    @property
    def total_records(self) -> int:
        return sum(self.source_counts.values())


class RawIngestionService:
    """Copies source rows into the immutable raw layer without normalization."""

    def __init__(self, registry: WorkspaceRegistry) -> None:
        self.registry = registry

    def ingest(
        self,
        session: Session,
        workspace_slug: str,
        *,
        replace: bool = True,
    ) -> IngestionResult:
        manifest = self.registry.load(workspace_slug)
        if replace:
            session.execute(
                update(IngestionRun)
                .where(IngestionRun.workspace_slug == workspace_slug)
                .where(IngestionRun.status == "completed")
                .values(status="superseded")
            )
            session.execute(delete(RawRecord).where(RawRecord.workspace_slug == workspace_slug))

        run = IngestionRun(workspace_slug=workspace_slug, status="running", source_counts={})
        session.add(run)
        session.flush()

        source_counts: dict[str, int] = {}
        try:
            for source in manifest.sources:
                source_path = self.registry.source_path(source.path)
                records = list(self._read_csv(source_path, run.id, workspace_slug, source.name))
                if records:
                    session.execute(insert(RawRecord), records)
                source_counts[source.name] = len(records)

            run.status = "completed"
            run.source_counts = source_counts
            run.finished_at = datetime.now(UTC)
            session.commit()
        except Exception:
            session.rollback()
            raise

        return IngestionResult(
            run_id=run.id,
            workspace_slug=workspace_slug,
            source_counts=source_counts,
        )

    @staticmethod
    def _read_csv(
        path: Path,
        run_id: int,
        workspace_slug: str,
        source_name: str,
    ) -> list[dict[str, object]]:
        if not path.is_file():
            raise FileNotFoundError(f"source file not found: {path}")

        rows: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as source_file:
            reader = csv.DictReader(source_file)
            if not reader.fieldnames:
                raise ValueError(f"source file has no header: {path}")
            for row_number, payload in enumerate(reader, start=2):
                canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                rows.append(
                    {
                        "run_id": run_id,
                        "workspace_slug": workspace_slug,
                        "source_name": source_name,
                        "source_row_number": row_number,
                        "fingerprint": hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
                        "payload": payload,
                    }
                )
        return rows
