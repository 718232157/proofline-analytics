from datetime import date, timedelta
from statistics import median

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
            priority="high" if abs(revenue_delta) >= 10 else "medium",
            title=(
                f"{period} 营业额{'增长' if revenue_delta >= 0 else '回落'} "
                f"{abs(revenue_delta):.2f}%"
            ),
            narrative=(
                f"环比订单数{self._direction(order_delta)}{abs(order_delta):.2f}%，"
                f"客单价{self._direction(aov_delta)}{abs(aov_delta):.2f}%；"
                f"本期变化主要由{primary_driver}驱动。"
            ),
            action=(
                "核对排班与备货是否能承接订单增长。"
                if primary_driver == "订单量" and revenue_delta >= 0
                else "检查高价值商品组合与价格策略。"
            ),
            impact_display=self._currency(latest_revenue.value - previous_revenue.value),
            target="revenue_trend",
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
            priority="medium",
            title=f"{driver_name} 是最大商品增量",
            narrative=f"相比上月，{driver_name}净营业额增加{self._currency(driver_delta)}。",
            action=f"检查{driver_name}的库存、备货和门店供应能力。",
            impact_display=self._currency(driver_delta),
            target="product_ranking",
            highlight=driver_name,
            evidence_ids=(
                previous_products.evidence.evidence_id,
                latest_products.evidence.evidence_id,
            ),
        )
        daily = self._daily_signal(session, workspace_slug)
        insights = tuple(
            sorted(
                (daily, pulse, driver),
                key=lambda insight: {"high": 0, "medium": 1, "low": 2}[insight.priority],
            )
        )
        return InsightFeed(workspace=workspace_slug, period=period, insights=insights)

    def _daily_signal(self, session: Session, workspace_slug: str) -> Insight:
        daily_revenue = self.analytics.query(
            session,
            workspace_slug,
            AnalyticsQuery(metric="revenue", group_by=("date",), date_grain="day", limit=500),
        )
        if len(daily_revenue.points) < 8:
            raise LookupError("at least eight days are required for a daily operating signal")
        latest = daily_revenue.points[-1]
        latest_date = date.fromisoformat(latest.dimensions["date"])
        comparable = [
            point.value
            for point in daily_revenue.points[:-1]
            if date.fromisoformat(point.dimensions["date"]).weekday() == latest_date.weekday()
        ][-4:]
        if not comparable:
            raise LookupError("same-weekday baseline is unavailable")
        baseline = median(comparable)
        delta = latest.value - baseline
        delta_percent = self._percent_change(baseline, latest.value)
        is_watch = delta_percent <= -15
        is_growth = delta_percent >= 15
        tone = "watch" if is_watch else "positive" if is_growth else "neutral"
        if is_watch:
            title = f"{latest_date.month}月{latest_date.day}日营业额低于同星期基线"
            action = "优先检查当日门店营业状态、缺货和异常退款。"
        elif is_growth:
            title = f"{latest_date.month}月{latest_date.day}日营业额高于同星期基线"
            action = "确认增长来源，并为下一同星期日准备排班与库存。"
        else:
            title = f"{latest_date.month}月{latest_date.day}日经营处于正常区间"
            action = "维持当前排班与备货，继续观察下一营业日。"
        return Insight(
            kind="daily_signal",
            tone=tone,
            priority="high"
            if abs(delta_percent) >= 25
            else "medium"
            if abs(delta_percent) >= 15
            else "low",
            title=title,
            narrative=(
                f"当日净营业额{self._money(latest.value)}，相比最近4个同星期日中位数"
                f"{'高' if delta >= 0 else '低'}{abs(delta_percent):.2f}%。"
            ),
            action=action,
            impact_display=self._currency(delta),
            target="revenue_trend",
            evidence_ids=(daily_revenue.evidence.evidence_id,),
        )

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

    @staticmethod
    def _money(minor_units: int | float) -> str:
        return f"¥{minor_units / 100:,.2f}"
