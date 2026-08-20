"""Prove assistant numbers equal independently executed semantic queries."""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analytics import AnalyticsQuery, AnalyticsService
from app.assistant import AssistantService, ChatRequest
from app.ingestion import RawIngestionService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def verified_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)
    session = Session(engine)
    RawIngestionService(registry).ingest(session, "moneki")
    ProcessingService(registry).process(session, "moneki")
    yield session
    session.close()


def test_category_answer_equals_independent_database_query(verified_session: Session) -> None:
    registry = WorkspaceRegistry(PROJECT_ROOT)
    query_result = AnalyticsService(registry).query(
        verified_session,
        "moneki",
        AnalyticsQuery(metric="revenue", group_by=("store_category",)),
    )
    expected = max(query_result.points, key=lambda point: point.value)
    answer = AssistantService(registry).answer(
        verified_session,
        "moneki",
        ChatRequest(question="哪个品类的门店营业额最高?"),
    )

    assert answer.status == "answered"
    assert answer.citations[0].value == expected.value
    assert answer.citations[0].dimensions == expected.dimensions
    assert answer.citations[0].display_value in answer.answer


def test_product_month_answer_equals_independent_database_query(
    verified_session: Session,
) -> None:
    registry = WorkspaceRegistry(PROJECT_ROOT)
    query_result = AnalyticsService(registry).query(
        verified_session,
        "moneki",
        AnalyticsQuery(
            metric="revenue",
            filters={"product": ("牛肉poke",)},
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 30),
        ),
    )
    answer = AssistantService(registry).answer(
        verified_session,
        "moneki",
        ChatRequest(question="牛肉 poke 六月卖了多少钱?"),
    )

    assert answer.status == "answered"
    assert answer.citations[0].value == query_result.points[0].value
    assert answer.citations[0].display_value in answer.answer


def test_aov_trend_answer_equals_independent_database_query(verified_session: Session) -> None:
    registry = WorkspaceRegistry(PROJECT_ROOT)
    query_result = AnalyticsService(registry).query(
        verified_session,
        "moneki",
        AnalyticsQuery(
            metric="average_order_value",
            group_by=("date",),
            date_grain="month",
        ),
    )
    answer = AssistantService(registry).answer(
        verified_session,
        "moneki",
        ChatRequest(question="客单价最近是涨了还是跌了?"),
    )

    assert answer.status == "answered"
    assert [citation.value for citation in answer.citations] == [
        point.value for point in query_result.points[-2:]
    ]
    assert all(citation.display_value in answer.answer for citation in answer.citations)
