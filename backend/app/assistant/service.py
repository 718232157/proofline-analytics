import re
from datetime import date

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
        if intent.name != "product_revenue" and self._is_outside_coverage(
            session, workspace_slug, intent
        ):
            coverage = self.analytics.date_range(session, workspace_slug)
            if coverage is None:
                return ChatResponse(
                    status="unsupported",
                    answer="当前还没有已进入分析层的可信日期数据。",
                    context=intent.context(),
                )
            assert intent.date_from is not None
            coverage_start, coverage_end = coverage
            return ChatResponse(
                status="unsupported",
                answer=(
                    f"当前可信数据仅覆盖{self._display_date(coverage_start)}至"
                    f"{self._display_date(coverage_end)}，无法回答"
                    f"{intent.date_from.month}月的数据。"
                ),
                context=intent.context(),
            )
        if intent.name == "category_leader":
            return self._category_leader(session, workspace_slug, intent)
        if intent.name == "product_revenue":
            product = self._canonical_product(
                session,
                workspace_slug,
                request.question,
                intent.product,
            )
            if product is None:
                return ChatResponse(
                    status="unsupported",
                    answer=(
                        "没有识别到唯一且已收录的商品。请只写一个可唯一识别的商品名称，"
                        "我会用商品维表核对全名或唯一简称，不会猜测或混合多个商品。"
                    ),
                )
            intent = ResolvedIntent(
                name=intent.name,
                product=product,
                date_from=intent.date_from,
                date_to=intent.date_to,
            )
            if intent.date_from is not None and intent.date_to is not None:
                coverage = self.analytics.date_range(session, workspace_slug)
                if coverage is not None:
                    coverage_start, coverage_end = coverage
                    if intent.date_to < coverage_start or intent.date_from > coverage_end:
                        return ChatResponse(
                            status="unsupported",
                            answer=(
                                f"已识别商品“{product}”，但当前可信数据仅覆盖"
                                f"{self._display_date(coverage_start)}至"
                                f"{self._display_date(coverage_end)}，"
                                f"无法回答{intent.date_from.month}月的数据。"
                            ),
                            context=intent.context(),
                        )
            return self._product_revenue(session, workspace_slug, intent)
        if intent.name == "aov_trend":
            return self._aov_trend(session, workspace_slug, intent)
        return self._store_comparison(session, workspace_slug, intent)

    def _canonical_product(
        self,
        session: Session,
        workspace_slug: str,
        question: str,
        parsed_product: str | None,
    ) -> str | None:
        """Resolve products against governed dimension values instead of guessed text spans."""
        catalog = self.analytics.query(
            session,
            workspace_slug,
            AnalyticsQuery(metric="revenue", group_by=("product",), limit=500),
        )
        names = tuple(point.dimensions["product"] for point in catalog.points)
        normalized_question = self._normalize_entity_text(question)
        matches = self._catalog_entity_matches(normalized_question, names)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None

        if parsed_product:
            parsed_key = self._normalize_entity_text(parsed_product)
            exact_matches = [
                name for name in names if self._normalize_entity_text(name) == parsed_key
            ]
            if len(exact_matches) == 1:
                return exact_matches[0]
            if len(parsed_key) >= 2:
                partial_matches = [
                    name for name in names if parsed_key in self._normalize_entity_text(name)
                ]
                if len(partial_matches) == 1:
                    return partial_matches[0]
        return None

    @classmethod
    def _catalog_entity_matches(cls, normalized_question: str, names: tuple[str, ...]) -> list[str]:
        """Match full names and catalog-unique substrings without guessing across entities."""
        normalized_names = {name: cls._normalize_entity_text(name) for name in names}
        alias_owners: dict[str, set[str]] = {}
        for name, key in normalized_names.items():
            for start in range(len(key)):
                for end in range(start + 2, len(key) + 1):
                    alias_owners.setdefault(key[start:end], set()).add(name)

        matched: list[str] = []
        for name in names:
            if any(
                alias in normalized_question and owners == {name}
                for alias, owners in alias_owners.items()
            ):
                matched.append(name)
        return matched

    @staticmethod
    def _normalize_entity_text(value: str) -> str:
        return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()

    @staticmethod
    def _display_date(value: date) -> str:
        return f"{value.year}年{value.month}月{value.day}日"

    def _is_outside_coverage(
        self,
        session: Session,
        workspace_slug: str,
        intent: ResolvedIntent,
    ) -> bool:
        if intent.date_from is None or intent.date_to is None:
            return False
        coverage = self.analytics.date_range(session, workspace_slug)
        if coverage is None:
            return True
        coverage_start, coverage_end = coverage
        return intent.date_to < coverage_start or intent.date_from > coverage_end

    def _category_leader(
        self, session: Session, workspace_slug: str, intent: ResolvedIntent
    ) -> ChatResponse:
        query = AnalyticsQuery(
            metric="revenue",
            group_by=("store_category",),
            date_from=intent.date_from,
            date_to=intent.date_to,
        )
        result = self.analytics.query(session, workspace_slug, query)
        if not result.points:
            return ChatResponse(
                status="unsupported",
                answer="当前筛选范围内没有可比较的可信门店品类数据。",
                context=intent.context(),
            )
        leader = max(result.points, key=lambda point: point.value)
        name = leader.dimensions["store_category"]
        display = self._currency(leader.value)
        period = f"{intent.date_from.month}月" if intent.date_from else "当前可信范围内"
        return ChatResponse(
            status="answered",
            answer=f"{period}营业额最高的门店品类是{name}，净营业额为{display}。",
            context=intent.context(),
            citations=(self._citation(result, leader.value, leader.dimensions, display),),
            chart_action=ChartAction(
                title="门店品类营业额",
                query=query,
                target="category_contribution",
                highlight=name,
            ),
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
            chart_action=ChartAction(
                title=title,
                query=query,
                target="revenue_trend",
                highlight=intent.product,
            ),
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
            chart_action=ChartAction(
                title="月度客单价趋势",
                query=query,
                target="aov_trend",
            ),
        )

    def _store_comparison(
        self, session: Session, workspace_slug: str, intent: ResolvedIntent
    ) -> ChatResponse:
        revenue_query = AnalyticsQuery(
            metric="revenue",
            group_by=("store",),
            date_from=intent.date_from,
            date_to=intent.date_to,
        )
        aov_query = AnalyticsQuery(
            metric="average_order_value",
            group_by=("store",),
            date_from=intent.date_from,
            date_to=intent.date_to,
        )
        revenue = self.analytics.query(session, workspace_slug, revenue_query)
        aov = self.analytics.query(session, workspace_slug, aov_query)
        if not revenue.points:
            return ChatResponse(status="unsupported", answer="当前没有可比较的可信门店数据。")
        revenue_leader = max(revenue.points, key=lambda point: point.value)
        aov_by_store = {point.dimensions["store"]: point for point in aov.points}
        store = revenue_leader.dimensions["store"]
        leader_aov = aov_by_store.get(store)
        if leader_aov is None:
            return ChatResponse(
                status="unsupported",
                answer="当前门店数据缺少可核验的客单价，暂不生成门店比较结论。",
                context=intent.context(),
            )
        period = f"{intent.date_from.month}月" if intent.date_from else "当前可信范围内"
        return ChatResponse(
            status="answered",
            answer=(
                f"{period}共有{len(revenue.points)}家门店。净营业额最高的是{store}，"
                f"为{self._currency(revenue_leader.value)}，客单价为"
                f"{self._currency(leader_aov.value)}；完整差异已定位到门店对比视图。"
            ),
            context=intent.context(),
            citations=(
                self._citation(
                    revenue,
                    revenue_leader.value,
                    revenue_leader.dimensions,
                    self._currency(revenue_leader.value),
                ),
                self._citation(
                    aov,
                    leader_aov.value,
                    leader_aov.dimensions,
                    self._currency(leader_aov.value),
                ),
            ),
            chart_action=ChartAction(
                title="门店经营对比",
                query=revenue_query,
                target="store_comparison",
                highlight=store,
            ),
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
