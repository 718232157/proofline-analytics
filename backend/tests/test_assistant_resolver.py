import json

import httpx
import pytest

from app.assistant.resolver import IntentResolver, OpenAICompatibleIntentResolver


def test_model_resolver_can_only_return_a_closed_intent_not_a_number() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert "Never calculate or invent numbers" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "product_revenue",
                                    "product": "牛肉poke",
                                    "month": 6,
                                }
                            )
                        }
                    }
                ]
            },
        )

    resolver = OpenAICompatibleIntentResolver(
        api_key="test-key",
        base_url="https://llm.invalid",
        model="test-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    intent = resolver.resolve("查一下六月牛肉 poke 的表现")

    assert intent is not None
    assert intent.name == "product_revenue"
    assert intent.product == "牛肉poke"
    assert intent.date_from is not None and intent.date_from.isoformat() == "2026-06-01"
    assert intent.date_to is not None and intent.date_to.isoformat() == "2026-06-30"


def test_deterministic_resolver_does_not_overreach() -> None:
    assert IntentResolver().resolve("预测明年利润") is None


def test_deterministic_resolver_understands_product_summary_language() -> None:
    intent = IntentResolver().resolve("灌汤包相关数据")

    assert intent is not None
    assert intent.name == "product_revenue"
    assert intent.product == "灌汤包"
    assert intent.date_from is None
    assert intent.date_to is None


@pytest.mark.parametrize(
    ("question", "expected_intent", "expected_product"),
    [
        ("三文鱼的营业额", "product_revenue", "三文鱼"),
        ("三文鱼poke的营业额是多少?", "product_revenue", "三文鱼poke"),
        ("牛肉的营业额是", "product_revenue", "牛肉"),
        ("营业额前10的商品是什么?", "product_ranking", None),
        ("商品销售额排名", "product_ranking", None),
        ("哪些商品卖得最好?", "product_ranking", None),
    ],
)
def test_deterministic_resolver_supports_common_revenue_language(
    question: str,
    expected_intent: str,
    expected_product: str | None,
) -> None:
    intent = IntentResolver().resolve(question)

    assert intent is not None
    assert intent.name == expected_intent
    assert intent.product == expected_product
