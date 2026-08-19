from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analytics import AnalyticsQuery, AnalyticsService
from app.analytics.service import InvalidAnalyticsQuery
from app.ingestion import RawIngestionService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def analytics_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    registry = WorkspaceRegistry(PROJECT_ROOT)
    ProcessorRegistry(registry).create("moneki")
    Base.metadata.create_all(engine)
    session = Session(engine)
    RawIngestionService(registry).ingest(session, "moneki")
    ProcessingService(registry).process(session, "moneki")
    yield session
    session.close()


def test_monthly_metrics_share_the_golden_semantic_contract(
    analytics_session: Session,
) -> None:
    service = AnalyticsService(WorkspaceRegistry(PROJECT_ROOT))

    revenue = service.query(
        analytics_session,
        "moneki",
        AnalyticsQuery(metric="revenue", group_by=("date",), date_grain="month"),
    )
    orders = service.query(
        analytics_session,
        "moneki",
        AnalyticsQuery(metric="order_count", group_by=("date",), date_grain="month"),
    )
    aov = service.query(
        analytics_session,
        "moneki",
        AnalyticsQuery(metric="average_order_value", group_by=("date",), date_grain="month"),
    )

    assert [point.value for point in revenue.points] == [13_944_600, 13_244_000, 15_152_700]
    assert [point.value for point in orders.points] == [3_836, 3_789, 4_244]
    assert [point.value for point in aov.points] == [3_635.19, 3_495.38, 3_570.38]
    assert revenue.evidence.metric_definition.startswith("有效销售")
    assert revenue.evidence.scope == "group_by=date"


def test_category_and_product_questions_are_deterministic(
    analytics_session: Session,
) -> None:
    service = AnalyticsService(WorkspaceRegistry(PROJECT_ROOT))
    by_category = service.query(
        analytics_session,
        "moneki",
        AnalyticsQuery(metric="revenue", group_by=("store_category",)),
    )
    beef_poke_june = service.query(
        analytics_session,
        "moneki",
        AnalyticsQuery(
            metric="revenue",
            filters={"product": ("牛肉poke",)},
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 30),
        ),
    )

    category_values = {
        point.dimensions["store_category"]: point.value for point in by_category.points
    }
    assert max(category_values, key=category_values.__getitem__) == "日料"
    assert category_values["日料"] == 8_834_700
    assert beef_poke_june.points[0].value == 1_344_000
    assert beef_poke_june.evidence.scope == ("date=2026-06-01..2026-06-30; product=牛肉poke")


def test_unknown_semantic_keys_are_rejected(analytics_session: Session) -> None:
    service = AnalyticsService(WorkspaceRegistry(PROJECT_ROOT))

    with pytest.raises(InvalidAnalyticsQuery, match="unknown dimension"):
        service.query(
            analytics_session,
            "moneki",
            AnalyticsQuery(metric="revenue", group_by=("raw_sql",)),
        )
