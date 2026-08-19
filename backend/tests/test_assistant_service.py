from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.assistant import AssistantService, ChatRequest
from app.ingestion import RawIngestionService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def assistant_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)
    session = Session(engine)
    RawIngestionService(registry).ingest(session, "moneki")
    ProcessingService(registry).process(session, "moneki")
    yield session
    session.close()


@pytest.mark.parametrize(
    ("question", "expected_text", "expected_value"),
    [
        ("哪个品类的门店营业额最高？", "日料", 8_834_700),
        ("牛肉 poke 六月卖了多少钱？", "¥13,440.00", 1_344_000),
        ("客单价最近是涨了还是跌了？", "最近回升", 3_570.38),
    ],
)
def test_required_answers_are_grounded_in_semantic_results(
    assistant_session: Session,
    question: str,
    expected_text: str,
    expected_value: int | float,
) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session, "moneki", ChatRequest(question=question)
    )

    assert response.status == "answered"
    assert expected_text in response.answer
    assert response.citations[-1].value == expected_value
    assert response.citations[-1].processing_run_id == 1
    assert response.chart_action is not None


def test_follow_up_reuses_product_context_but_changes_month(
    assistant_session: Session,
) -> None:
    service = AssistantService(WorkspaceRegistry(PROJECT_ROOT))
    june = service.answer(
        assistant_session,
        "moneki",
        ChatRequest(question="牛肉poke六月卖了多少钱？"),
    )
    may = service.answer(
        assistant_session,
        "moneki",
        ChatRequest(question="那五月呢？", context=june.context),
    )

    assert may.status == "answered"
    assert may.context is not None
    assert may.context.product == "牛肉poke"
    assert may.answer == "牛肉poke在5月的净营业额是¥13,020.00。"
    assert may.citations[0].value == 1_302_000


def test_unsupported_question_refuses_to_invent_data(assistant_session: Session) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question="下个月天气会影响多少营业额？"),
    )

    assert response.status == "unsupported"
    assert "不会用常识补造数据" in response.answer
    assert response.citations == ()
    assert response.chart_action is None
