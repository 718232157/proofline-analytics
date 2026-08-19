from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ingestion import RawIngestionService
from app.main import app
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.database import get_session
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_analytics_api_returns_metric_and_evidence() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)
    session = Session(engine)
    RawIngestionService(registry).ingest(session, "moneki")
    ProcessingService(registry).process(session, "moneki")

    def override_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        response = TestClient(app).post(
            "/api/workspaces/moneki/analytics/query",
            json={
                "metric": "revenue",
                "filters": {"product": ["牛肉poke"]},
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
            },
        )
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["points"] == [{"dimensions": {}, "value": 1_344_000}]
    assert payload["currency"] == "CNY"
    assert payload["evidence"]["processing_run_id"] == 1
    assert len(payload["evidence"]["evidence_id"]) == 16
