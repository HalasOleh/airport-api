import json
from unittest.mock import AsyncMock

import pytest

from ai_bot.consumers import TestConsumer as ChatConsumer
from ai_bot.payment_safety import contains_payment_card_number
from ai_bot.prompt import build_system_prompt


@pytest.mark.parametrize(
    "message",
    [
        "Use test card 4242 4242 4242 4242",
        "Use test card 4242-4242-4242-4242",
    ],
)
def test_detects_luhn_valid_card_numbers(message):
    assert contains_payment_card_number(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "Flight 123 departs on 2026-10-15",
        "I want seats 5 and 6",
        "Order 1234567890123456",
    ],
)
def test_does_not_reject_normal_numeric_messages(message):
    assert contains_payment_card_number(message) is False


@pytest.mark.asyncio
async def test_card_number_is_rejected_before_storage_or_model_call():
    consumer = ChatConsumer()
    consumer.provider = "openai"
    consumer.dialog = type("Dialog", (), {"id": 42})()
    consumer.messages = [{"role": "system", "content": "system"}]
    consumer.send = AsyncMock()
    consumer.generate_reply = AsyncMock()

    await consumer.receive(json.dumps({
        "message": "My test card is 4242 4242 4242 4242",
    }))

    assert consumer.messages == [{"role": "system", "content": "system"}]
    consumer.generate_reply.assert_not_awaited()
    payload = json.loads(consumer.send.await_args.kwargs["text_data"])
    assert "card numbers" in payload["error"]


def test_system_prompt_forbids_collecting_payment_details():
    prompt = build_system_prompt()

    assert "Never ask the user for a card number" in prompt
    assert "Stripe-hosted Checkout page" in prompt
    assert "unless the corresponding tool returned a successful result" in prompt


@pytest.mark.asyncio
async def test_checkout_url_is_sent_as_structured_websocket_data():
    consumer = ChatConsumer()
    consumer.provider = "openai"
    consumer.dialog = None
    consumer.messages = [{"role": "system", "content": "system"}]
    consumer.send = AsyncMock()

    async def generate_reply():
        consumer.remember_checkout_url(
            {"checkout_url": "https://checkout.stripe.test/session"}
        )
        return "Your secure payment link is ready."

    consumer.generate_reply = generate_reply

    await consumer.receive(json.dumps({"message": "I confirm the booking"}))

    payload = json.loads(consumer.send.await_args.kwargs["text_data"])
    assert payload == {
        "reply": "Your secure payment link is ready.",
        "checkout_url": "https://checkout.stripe.test/session",
    }


def test_non_https_checkout_url_is_not_exposed():
    consumer = ChatConsumer()
    consumer.checkout_url = None

    consumer.remember_checkout_url({"checkout_url": "javascript:alert(1)"})

    assert consumer.checkout_url is None


@pytest.mark.asyncio
async def test_checkout_url_survives_a_provider_failure_after_tool_success():
    consumer = ChatConsumer()
    consumer.provider = "openai"
    consumer.dialog = None
    consumer.messages = [{"role": "system", "content": "system"}]
    consumer.send = AsyncMock()

    async def generate_reply():
        consumer.remember_checkout_url(
            {"checkout_url": "https://checkout.stripe.test/session"}
        )
        raise RuntimeError("provider failed after the tool call")

    consumer.generate_reply = generate_reply

    await consumer.receive(json.dumps({"message": "I confirm the booking"}))

    payload = json.loads(consumer.send.await_args.kwargs["text_data"])
    assert payload["checkout_url"] == "https://checkout.stripe.test/session"
    assert "reserved" in payload["reply"]
    assert "error" not in payload
