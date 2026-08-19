from pathlib import Path

from sqlalchemy import text

from app.storage.database import create_database_engine, create_session_factory


def test_sqlite_engine_creates_parent_and_enables_foreign_keys(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "proofline.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")

    with engine.connect() as connection:
        foreign_keys = connection.scalar(text("PRAGMA foreign_keys"))

    assert database_path.parent.is_dir()
    assert foreign_keys == 1


def test_session_factory_binds_the_requested_engine() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        assert session.get_bind() is engine
