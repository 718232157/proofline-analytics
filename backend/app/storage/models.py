from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_slug: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(24))
    source_counts: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    records: Mapped[list["RawRecord"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = (Index("ix_raw_workspace_source", "workspace_slug", "source_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="CASCADE"))
    workspace_slug: Mapped[str] = mapped_column(String(80))
    source_name: Mapped[str] = mapped_column(String(80))
    source_row_number: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

    run: Mapped[IngestionRun] = relationship(back_populates="records")


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"))
    workspace_slug: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(24))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    quality_events: Mapped[list["QualityEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class QualityEvent(Base):
    __tablename__ = "quality_events"
    __table_args__ = (Index("ix_quality_run_reason", "processing_run_id", "reason_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    processing_run_id: Mapped[int] = mapped_column(
        ForeignKey("processing_runs.id", ondelete="CASCADE")
    )
    source_name: Mapped[str] = mapped_column(String(80))
    source_row_number: Mapped[int] = mapped_column(Integer)
    record_key: Mapped[str | None] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(24))
    reason_code: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    run: Mapped[ProcessingRun] = relationship(back_populates="quality_events")
