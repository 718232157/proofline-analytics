import json

import httpx

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
