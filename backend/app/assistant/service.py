from sqlalchemy.orm import Session

from app.analytics import AnalyticsQuery, AnalyticsService, MetricResult
from app.assistant.models import (
    ChartAction,
    ChatRequest,
    ChatResponse,
    EvidenceCitation,
)
from app.assistant.resolver import (
    HybridIntentResolver,
    IntentResolver,
    OpenAICompatibleIntentResolver,
    ResolvedIntent,
    Resolver,
)
from app.core.config import get_settings
from app.workspaces.registry import WorkspaceRegistry


class AssistantService:
    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        analytics_service: AnalyticsService | None = None,
        intent_resolver: Resolver | None = None,
    ) -> None:
        self.analytics = analytics_service or AnalyticsService(workspace_registry)
        self.intent_resolver = intent_resolver or self._default_resolver()

    def answer(self, session: Session, workspace_slug: str, request: ChatRequest) -> ChatResponse:
        intent = self.intent_resolver.resolve(request.question, request.context)
        if intent is None:
            return ChatResponse(
                status="unsupported",
                answer=(
                    "这个问题超出了当前数据范围。我只能基于已治理的日期、门店、品类、"
                    "商品、营业额、订单数和客单价回答；不会用常识补造数据。"
                ),
            )
        if intent.name == "category_leader":
            return self._category_leader(session, workspace_slug, intent)
        if intent.name == "product_revenue":
            return self._product_revenue(session, workspace_slug, intent)
        return self._aov_trend(session, workspace_slug, intent)

    def _category_leader(
        self, session: Session, workspace_slug: str, intent: ResolvedIntent
    ) -> ChatResponse:
        query = AnalyticsQuery(metric="revenue", group_by=("store_category",))
        result = self.analytics.query(session, workspace_slug, query)
        leader = max(result.points, key=lambda point: point.value)
        name = leader.dimensions["store_category"]
        display = self._currency(leader.value)
        return ChatResponse(
            status="answered",
            answer=f"营业额最高的门店品类是{name}，净营业额为{display}。",
            context=intent.context(),
            citations=(self._citation(result, leader.value, leader.dimensions, display),),
            chart_action=ChartAction(title="门店品类营业额", query=query),
        )

    def _product_revenue(
        self, session: Session, workspace_slug: str, intent: ResolvedIntent
    ) -> ChatResponse:
        assert intent.product is not None
        query = AnalyticsQuery(
            metric="revenue",
            filters={"product": (intent.product,)},
            date_from=intent.date_from,
            date_to=intent.date_to,
        )
        result = self.analytics.query(session, workspace_slug, query)
        value = result.points[0].value
        display = self._currency(value)
        if intent.date_from is None:
            if value == 0:
                answer = f"在全部可信记录中，没有找到{intent.product}的营业额。"
            else:
                answer = f"{intent.product}在全部可信记录中的净营业额是{display}。"
            title = f"{intent.product} · 全部可信记录"
        else:
            month = intent.date_from.month
            if value == 0:
                answer = f"在已接受记录中，没有找到{intent.product}在{month}月的营业额。"
            else:
                answer = f"{intent.product}在{month}月的净营业额是{display}。"
            title = f"{intent.product} · {month}月"
        return ChatResponse(
            status="answered",
            answer=answer,
            context=intent.context(),
            citations=(self._citation(result, value, {}, display),),
            chart_action=ChartAction(title=title, query=query),
        )

    def _aov_trend(
        self, session: Session, workspace_slug: str, intent: ResolvedIntent
    ) -> ChatResponse:
        query = AnalyticsQuery(metric="average_order_value", group_by=("date",), date_grain="month")
        result = self.analytics.query(session, workspace_slug, query)
        if len(result.points) < 2:
            return ChatResponse(
                status="unsupported",
                answer="当前有效月份不足两个，无法判断客单价趋势。",
            )
        previous, latest = result.points[-2:]
        direction = "回升" if latest.value > previous.value else "下降"
        delta = abs((latest.value - previous.value) / previous.value * 100)
        previous_display = self._currency(previous.value)
        latest_display = self._currency(latest.value)
        return ChatResponse(
            status="answered",
            answer=(
                f"客单价最近{direction}：从{previous.dimensions['date']}的{previous_display}"
                f"变为{latest.dimensions['date']}的{latest_display}，变动{delta:.2f}%。"
            ),
            context=intent.context(),
            citations=(
                self._citation(result, previous.value, previous.dimensions, previous_display),
                self._citation(result, latest.value, latest.dimensions, latest_display),
            ),
            chart_action=ChartAction(title="月度客单价趋势", query=query),
        )

    @staticmethod
    def _citation(
        result: MetricResult,
        value: int | float,
        dimensions: dict[str, str],
        display: str,
    ) -> EvidenceCitation:
        return EvidenceCitation(
            evidence_id=result.evidence.evidence_id,
            processing_run_id=result.evidence.processing_run_id,
            metric=result.metric,
            label=result.label,
            value=value,
            display_value=display,
            dimensions=dimensions,
            scope=result.evidence.scope,
        )

    @staticmethod
    def _currency(minor_units: int | float) -> str:
        return f"¥{minor_units / 100:,.2f}"

    @staticmethod
    def _default_resolver() -> Resolver:
        deterministic = IntentResolver()
        settings = get_settings()
        if not settings.llm_api_key:
            return deterministic
        return HybridIntentResolver(
            deterministic,
            OpenAICompatibleIntentResolver(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
            ),
        )
