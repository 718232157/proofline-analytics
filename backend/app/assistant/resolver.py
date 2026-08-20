import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from app.assistant.models import AnalysisContext, IntentName

MONTHS = {
    "一月": 1,
    "1月": 1,
    "二月": 2,
    "2月": 2,
    "三月": 3,
    "3月": 3,
    "四月": 4,
    "4月": 4,
    "五月": 5,
    "5月": 5,
    "六月": 6,
    "6月": 6,
    "七月": 7,
    "7月": 7,
    "八月": 8,
    "8月": 8,
    "九月": 9,
    "9月": 9,
    "十月": 10,
    "10月": 10,
    "十一月": 11,
    "11月": 11,
    "十二月": 12,
    "12月": 12,
}
MONTH_TOKENS = tuple(sorted(MONTHS, key=len, reverse=True))
MONTH_PATTERN = "(?:" + "|".join(re.escape(token) for token in MONTH_TOKENS) + ")"


@dataclass(frozen=True)
class ResolvedIntent:
    name: IntentName
    product: str | None = None
    date_from: date | None = None
    date_to: date | None = None

    def context(self) -> AnalysisContext:
        return AnalysisContext(
            intent=self.name,
            product=self.product,
            date_from=self.date_from,
            date_to=self.date_to,
        )


class Resolver(Protocol):
    def resolve(
        self, question: str, prior: AnalysisContext | None = None
    ) -> ResolvedIntent | None: ...


class IntentResolver:
    """Deterministic baseline for common operational questions and follow-ups."""

    def resolve(self, question: str, prior: AnalysisContext | None = None) -> ResolvedIntent | None:
        normalized = re.sub(r"\s+", "", question).lower()
        month = self._month(normalized)
        if prior and month and self._is_follow_up(normalized):
            start, end = self._month_range(2026, month)
            return ResolvedIntent(prior.intent, prior.product, start, end)
        if "客单价" in normalized and any(word in normalized for word in ("趋势", "涨", "跌")):
            return ResolvedIntent("aov_trend")
        if "品类" in normalized and any(word in normalized for word in ("最高", "最多", "第一")):
            if month:
                start, end = self._month_range(2026, month)
                return ResolvedIntent("category_leader", date_from=start, date_to=end)
            return ResolvedIntent("category_leader")
        if "门店" in normalized and any(
            word in normalized for word in ("对比", "比较", "哪家", "排名", "差异")
        ):
            if month:
                start, end = self._month_range(2026, month)
                return ResolvedIntent("store_comparison", date_from=start, date_to=end)
            return ResolvedIntent("store_comparison")
        if self._is_product_ranking_question(normalized):
            if month:
                start, end = self._month_range(2026, month)
                return ResolvedIntent("product_ranking", date_from=start, date_to=end)
            return ResolvedIntent("product_ranking")
        if self._is_external_or_predictive_question(normalized):
            return None
        if any(word in normalized for word in ("卖了多少", "多少钱", "营业额", "销售额")):
            product = self._product(normalized)
            if month:
                start, end = self._month_range(2026, month)
                return ResolvedIntent("product_revenue", product, start, end)
            return ResolvedIntent("product_revenue", product)
        if any(word in normalized for word in ("相关数据", "商品表现", "销售情况", "卖得怎么样")):
            product = self._summary_product(normalized)
            if product:
                return ResolvedIntent("product_revenue", product)
        return None

    @staticmethod
    def _month(question: str) -> int | None:
        return next((MONTHS[token] for token in MONTH_TOKENS if token in question), None)

    @staticmethod
    def _month_range(year: int, month: int) -> tuple[date, date]:
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
        return start, end

    @staticmethod
    def _is_follow_up(question: str) -> bool:
        return len(question) <= 12 or any(token in question for token in ("那", "呢", "改成"))

    @staticmethod
    def _is_product_ranking_question(question: str) -> bool:
        has_product_scope = "商品" in question or "产品" in question
        has_ranking_language = any(
            token in question
            for token in ("前10", "前十", "排名", "排行", "榜单", "最高", "最多", "最好")
        )
        has_revenue_language = any(
            token in question for token in ("营业额", "销售额", "卖得", "卖的")
        )
        return has_product_scope and has_ranking_language and has_revenue_language

    @staticmethod
    def _is_external_or_predictive_question(question: str) -> bool:
        return any(
            token in question
            for token in ("天气", "预测", "影响", "利润", "成本", "未来", "下个月", "明年")
        )

    @staticmethod
    def _product(question: str) -> str | None:
        product = question.strip("？?。！!")
        for prefix in ("请问", "帮我看一下", "帮我看看", "看一下", "查一下"):
            product = product.removeprefix(prefix)
        product = re.sub(
            rf"(?:(?:今年|本年)|(?:20\d{{2}}年))?{MONTH_PATTERN}(?:份)?",
            "",
            product,
            count=1,
        )
        for phrase in (
            "的营业额是多少",
            "营业额是多少",
            "的营业额是",
            "营业额是",
            "的销售额是多少",
            "销售额是多少",
            "的销售额是",
            "销售额是",
            "卖了多少钱",
            "卖了多少",
            "多少钱",
            "的营业额",
            "营业额",
            "的销售额",
            "销售额",
        ):
            product = product.replace(phrase, "")
        product = product.strip("，,：:；;的在于")
        return product.removeprefix("那") or None

    @staticmethod
    def _summary_product(question: str) -> str | None:
        product = question
        for prefix in ("请问", "帮我看一下", "帮我看看", "看一下", "查一下"):
            product = product.removeprefix(prefix)
        suffixes = (
            "相关数据",
            "的相关数据",
            "商品表现",
            "的商品表现",
            "销售情况",
            "的销售情况",
            "卖得怎么样",
        )
        for suffix in suffixes:
            product = product.removesuffix(suffix)
        return product.removesuffix("的") or None


class ModelIntent(BaseModel):
    intent: IntentName | None
    product: str | None = None
    month: int | None = None


class OpenAICompatibleIntentResolver:
    """Uses an LLM only to map language into the closed semantic intent schema."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=12)

    def resolve(self, question: str, prior: AnalysisContext | None = None) -> ResolvedIntent | None:
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Map the user's analytics question to JSON only. Allowed intents: "
                            "category_leader, product_revenue, product_ranking, aov_trend, "
                            "store_comparison, or null. "
                            "Return {intent, product, month}. Never calculate or invent numbers."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"prior={prior.model_dump_json() if prior else 'null'}\n{question}"
                        ),
                    },
                ],
            },
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
            parsed = ModelIntent.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValidationError, ValueError):
            return None
        if parsed.intent is None:
            return None
        product = parsed.product or (prior.product if prior else None)
        date_from: date | None
        date_to: date | None
        if parsed.month is not None and 1 <= parsed.month <= 12:
            date_from, date_to = IntentResolver._month_range(2026, parsed.month)
        else:
            date_from, date_to = None, None
        if parsed.intent == "product_revenue" and not product:
            return None
        return ResolvedIntent(parsed.intent, product, date_from, date_to)


class HybridIntentResolver:
    """Keeps common questions deterministic and delegates long-tail phrasing to an LLM."""

    def __init__(self, deterministic: Resolver, model: Resolver) -> None:
        self.deterministic = deterministic
        self.model = model

    def resolve(self, question: str, prior: AnalysisContext | None = None) -> ResolvedIntent | None:
        resolved = self.deterministic.resolve(question, prior)
        if resolved is not None:
            return resolved
        try:
            return self.model.resolve(question, prior)
        except httpx.HTTPError:
            return None
