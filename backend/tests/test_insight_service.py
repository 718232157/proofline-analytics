from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ingestion import RawIngestionService
from app.insights import InsightService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_insights_decompose_growth_with_governed_metrics() -> None:
    engine = create_engine("sqlite:///:memory:")
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        RawIngestionService(registry).ingest(session, "moneki")
        ProcessingService(registry).process(session, "moneki")
        feed = InsightService(registry).generate(session, "moneki")

    assert feed.period == "2026-07"
    assert feed.insights[0].title == "2026-07 营业额增长 14.41%"
    assert "订单数增长12.01%" in feed.insights[0].narrative
    assert "客单价增长2.15%" in feed.insights[0].narrative
    assert "订单量驱动" in feed.insights[0].narrative
    assert len(feed.insights[0].evidence_ids) == 3
