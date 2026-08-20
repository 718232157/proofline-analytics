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


@pytest.mark.parametrize(
    "question",
    [
        "牛肉poke在6月份的营业额是多少？",
        "牛肉 poke 6月营业额是多少？",
        "6月份牛肉poke的营业额是多少？",
        "帮我看看今年六月，牛肉 poke 卖了多少？",
    ],
)
def test_product_entity_is_matched_from_the_governed_catalog_across_phrasings(
    assistant_session: Session,
    question: str,
) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question=question),
    )

    assert response.status == "answered"
    assert response.context is not None
    assert response.context.product == "牛肉poke"
    assert response.answer == "牛肉poke在6月的净营业额是¥13,440.00。"
    assert response.citations[0].value == 1_344_000


@pytest.mark.parametrize(
    "question",
    [
        "披萨在6月份的营业额是多少？",
        "牛肉poke和鸡肉poke六月营业额分别是多少？",
        "鸡肉和牛肉poke六月营业额分别是多少？",
    ],
)
def test_unknown_or_ambiguous_product_is_refused_instead_of_returning_zero(
    assistant_session: Session,
    question: str,
) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question=question),
    )

    assert response.status == "unsupported"
    assert "唯一且已收录的商品" in response.answer
    assert response.citations == ()
    assert response.chart_action is None


def test_unique_product_shorthand_is_resolved_but_out_of_range_month_is_explained(
    assistant_session: Session,
) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question="三文鱼3月的营业额"),
    )

    assert response.status == "unsupported"
    assert response.context is not None
    assert response.context.product == "三文鱼poke"
    assert response.answer == (
        "已识别商品“三文鱼poke”，但当前可信数据仅覆盖2026年5月1日至2026年7月31日，无法回答3月的数据。"
    )
    assert response.citations == ()
    assert response.chart_action is None


@pytest.mark.parametrize(
    "question",
    [
        "三文鱼6月份的营业额是多少？",
        "6月份三文鱼的营业额是多少？",
        "帮我看看今年六月，三文鱼卖了多少？",
    ],
)
def test_unique_product_shorthand_works_across_time_word_order(
    assistant_session: Session,
    question: str,
) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question=question),
    )

    assert response.status == "answered"
    assert response.context is not None
    assert response.context.product == "三文鱼poke"
    assert response.citations[0].value > 0


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


def test_product_summary_uses_the_full_governed_range(assistant_session: Session) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question="灌汤包相关数据"),
    )

    assert response.status == "answered"
    assert response.answer == "灌汤包在全部可信记录中的净营业额是¥24,775.00。"
    assert response.citations[0].value == 2_477_500
    assert response.chart_action is not None
    assert response.chart_action.query.filters == {"product": ("灌汤包",)}


@pytest.mark.parametrize(
    ("question", "canonical_product", "expected_display", "expected_value"),
    [
        ("三文鱼的营业额", "三文鱼poke", "¥37,316.00", 3_731_600),
        ("三文鱼poke的营业额是多少", "三文鱼poke", "¥37,316.00", 3_731_600),
        ("牛肉的营业额是", "牛肉poke", "¥39,690.00", 3_969_000),
    ],
)
def test_product_revenue_without_a_month_uses_the_full_governed_range(
    assistant_session: Session,
    question: str,
    canonical_product: str,
    expected_display: str,
    expected_value: int,
) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question=question),
    )

    assert response.status == "answered"
    assert response.context is not None
    assert response.context.product == canonical_product
    assert expected_display in response.answer
    assert response.citations[0].value == expected_value
    assert response.chart_action is not None


def test_product_ranking_returns_the_governed_top_ten(assistant_session: Session) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question="营业额前10的商品是什么？"),
    )

    assert response.status == "answered"
    assert response.answer == (
        "全部可信记录的营业额前10商品依次是：牛肉poke、三文鱼poke、鸡肉poke、"
        "豚骨拉面、味增拉面、照烧三明治、吞拿鱼三明治、灌汤包、照烧鸡饭、小笼包。"
        "精确金额已定位到商品排名表。"
    )
    assert response.citations[0].dimensions == {"product": "牛肉poke"}
    assert response.citations[0].value == 3_969_000
    assert response.chart_action is not None
    assert response.chart_action.target == "product_ranking"
    assert response.chart_action.highlight == "牛肉poke"


def test_product_ranking_honors_a_requested_month(assistant_session: Session) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question="六月商品营业额前10名"),
    )

    assert response.status == "answered"
    assert response.answer.startswith("6月的营业额前10商品依次是：")
    assert response.context is not None
    assert response.context.date_from == date(2026, 6, 1)
    assert response.context.date_to == date(2026, 6, 30)
    assert response.chart_action is not None
    assert response.chart_action.query.date_from == date(2026, 6, 1)


def test_store_comparison_uses_governed_store_metrics(assistant_session: Session) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question="五家门店经营表现有什么差异？"),
    )

    assert response.status == "answered"
    assert "净营业额最高的是Super Tetsudo" in response.answer
    assert len(response.citations) == 2
    assert response.citations[0].dimensions == {"store": "Super Tetsudo"}
    assert response.citations[0].value == 8_834_700
    assert response.chart_action is not None
    assert response.chart_action.target == "store_comparison"


def test_category_and_store_intents_honor_month_and_follow_up_context(
    assistant_session: Session,
) -> None:
    service = AssistantService(WorkspaceRegistry(PROJECT_ROOT))
    category = service.answer(
        assistant_session,
        "moneki",
        ChatRequest(question="六月哪个品类的门店营业额最高？"),
    )
    june_stores = service.answer(
        assistant_session,
        "moneki",
        ChatRequest(question="六月门店经营表现有什么差异？"),
    )
    may_stores = service.answer(
        assistant_session,
        "moneki",
        ChatRequest(question="那五月呢？", context=june_stores.context),
    )

    assert category.status == "answered"
    assert category.answer.startswith("6月营业额最高")
    assert category.chart_action is not None
    assert category.chart_action.query.date_from == date(2026, 6, 1)
    assert june_stores.status == "answered"
    assert may_stores.status == "answered"
    assert may_stores.answer.startswith("5月共有")
    assert may_stores.context is not None
    assert may_stores.context.intent == "store_comparison"
    assert may_stores.chart_action is not None
    assert may_stores.chart_action.query.date_to == date(2026, 5, 31)


@pytest.mark.parametrize(
    "question",
    ["三月哪个品类的门店营业额最高？", "三月门店经营表现有什么差异？"],
)
def test_dated_non_product_intents_refuse_outside_coverage(
    assistant_session: Session,
    question: str,
) -> None:
    response = AssistantService(WorkspaceRegistry(PROJECT_ROOT)).answer(
        assistant_session,
        "moneki",
        ChatRequest(question=question),
    )

    assert response.status == "unsupported"
    assert "当前可信数据仅覆盖2026年5月1日至2026年7月31日" in response.answer
    assert response.citations == ()
    assert response.chart_action is None


def test_answer_number_equals_an_independent_semantic_query(assistant_session: Session) -> None:
    registry = WorkspaceRegistry(PROJECT_ROOT)
    independent = AnalyticsService(registry).query(
        assistant_session,
        "moneki",
        AnalyticsQuery(
            metric="revenue",
            filters={"product": ("牛肉poke",)},
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 30),
        ),
    )
    response = AssistantService(registry).answer(
        assistant_session,
        "moneki",
        ChatRequest(question="牛肉poke六月卖了多少钱？"),
    )

    queried_value = independent.points[0].value
    assert response.citations[0].value == queried_value
    assert response.citations[0].display_value in response.answer
