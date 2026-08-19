from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.ingestion import RawIngestionService
from app.storage.models import Base, IngestionRun, RawRecord
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_ingestion_preserves_every_source_row_and_provenance() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        result = RawIngestionService(WorkspaceRegistry(PROJECT_ROOT)).ingest(session, "moneki")

        assert result.source_counts == {"sales": 12_131, "stores": 5, "products": 20}
        assert result.total_records == 12_156
        assert session.scalar(select(func.count()).select_from(RawRecord)) == 12_156

        first_sale = session.scalar(
            select(RawRecord)
            .where(RawRecord.source_name == "sales")
            .order_by(RawRecord.source_row_number)
            .limit(1)
        )
        assert first_sale is not None
        assert first_sale.source_row_number == 2
        assert first_sale.payload["order_id"] == "ORD109456"
        assert len(first_sale.fingerprint) == 64


def test_replacement_ingestion_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    service = RawIngestionService(WorkspaceRegistry(PROJECT_ROOT))

    with Session(engine) as session:
        first = service.ingest(session, "moneki")
        second = service.ingest(session, "moneki")

        assert second.run_id > first.run_id
        assert session.scalar(select(func.count()).select_from(IngestionRun)) == 2
        assert session.scalar(select(func.count()).select_from(RawRecord)) == 12_156

        statuses = session.scalars(select(IngestionRun.status).order_by(IngestionRun.id)).all()
        assert statuses == ["superseded", "completed"]
