from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.analytics import AnalyticsQuery, AnalyticsService, MetricResult
from app.insights.models import Insight, InsightFeed
from app.workspaces.registry import WorkspaceRegistry


class InsightService:
    """Creates deterministic proactive findings from governed metric results."""

    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        analytics_service: AnalyticsService | None = None,
    ) -> None:
        self.analytics = analytics_service or AnalyticsService(workspace_registry)

    def generate(self, session: Session, workspace_slug: str) -> InsightFeed:
        monthly_revenue = self.analytics.query(
            session,
            workspace_slug,
            AnalyticsQuery(metric="revenue", group_by=("date",), date_grain="month"),
        )
        monthly_orders = self.analytics.query(
            session,
            workspace_slug,
            AnalyticsQuery(metric="order_count", group_by=("date",), date_grain="month"),
        )
        monthly_aov = self.analytics.query(
            session,
            workspace_slug,
            AnalyticsQuery(metric="average_order_value", group_by=("date",), date_grain="month"),
        )
        if (
            min(len(monthly_revenue.points), len(monthly_orders.points), len(monthly_aov.points))
            < 2
        ):
            raise LookupError("at least two complete months are required for proactive insights")

        previous_revenue, latest_revenue = monthly_revenue.points[-2:]
        previous_orders, latest_orders = monthly_orders.points[-2:]
        previous_aov, latest_aov = monthly_aov.points[-2:]
        period = latest_revenue.dimensions["date"]
        revenue_delta = self._percent_change(previous_revenue.value, latest_revenue.value)
        order_delta = self._percent_change(previous_orders.value, latest_orders.value)
        aov_delta = self._percent_change(previous_aov.value, latest_aov.value)
        primary_driver = "订单量" if abs(order_delta) >= abs(aov_delta) else "客单价"
        pulse = Insight(
            kind="performance_pulse",
            tone="positive" if revenue_delta >= 0 else "watch",
            title=(
                f"{period} 营业额{'增长' if revenue_delta >= 0 else '回落'} "
                f"{abs(revenue_delta):.2f}%"
            ),
            narrative=(
                f"环比订单数{self._direction(order_delta)}{abs(order_delta):.2f}%，"
                f"客单价{self._direction(aov_delta)}{abs(aov_delta):.2f}%；"
                f"本期变化主要由{primary_driver}驱动。"
            ),
            evidence_ids=(
                monthly_revenue.evidence.evidence_id,
                monthly_orders.evidence.evidence_id,
                monthly_aov.evidence.evidence_id,
            ),
        )

        year, month = (int(part) for part in period.split("-"))
        previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
        latest_products = self._product_revenue(session, workspace_slug, year, month)
        previous_products = self._product_revenue(
            session, workspace_slug, previous_year, previous_month
        )
        previous_values = {
            point.dimensions["product"]: point.value for point in previous_products.points
        }
        deltas = [
            (
                point.dimensions["product"],
                point.value - previous_values.get(point.dimensions["product"], 0),
            )
            for point in latest_products.points
        ]
        driver_name, driver_delta = max(deltas, key=lambda item: item[1])
        driver = Insight(
            kind="growth_driver",
            tone="positive" if driver_delta >= 0 else "watch",
            title=f"{driver_name} 是最大商品增量",
            narrative=f"相比上月，{driver_name}净营业额增加{self._currency(driver_delta)}。",
            evidence_ids=(
                previous_products.evidence.evidence_id,
                latest_products.evidence.evidence_id,
            ),
        )
        return InsightFeed(workspace=workspace_slug, period=period, insights=(pulse, driver))

    def _product_revenue(
        self, session: Session, workspace_slug: str, year: int, month: int
    ) -> MetricResult:
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
        return self.analytics.query(
            session,
            workspace_slug,
            AnalyticsQuery(
                metric="revenue",
                group_by=("product",),
                date_from=start,
                date_to=end,
            ),
        )

    @staticmethod
    def _percent_change(previous: int | float, current: int | float) -> float:
        return (current - previous) / previous * 100 if previous else 0

    @staticmethod
    def _direction(value: float) -> str:
        return "增长" if value >= 0 else "下降"

    @staticmethod
    def _currency(minor_units: int | float) -> str:
        sign = "+" if minor_units >= 0 else "-"
        return f"{sign}¥{abs(minor_units) / 100:,.2f}"
