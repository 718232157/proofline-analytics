from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ingestion import RawIngestionService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.quality import QualityService
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_quality_summary_exposes_pipeline_outcomes() -> None:
    engine = create_engine("sqlite:///:memory:")
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        RawIngestionService(registry).ingest(session, "moneki")
        ProcessingService(registry).process(session, "moneki")
        summary = QualityService().summary(session, "moneki")

    assert summary.acceptance_rate == 97.84
    assert summary.accepted_sales_records == 11_869
    assert summary.quarantined_records == 184
    assert sum(reason.count for reason in summary.reasons if reason.action == "quarantined") == 184
