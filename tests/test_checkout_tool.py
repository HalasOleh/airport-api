from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from ai_bot.tools import TOOL_SCHEMAS, call_tool
from ai_bot.tools.booking_tools import create_checkout_link
from tickets.models import Order, Payment, Ticket


pytestmark = pytest.mark.django_db


def _schema(name):
    for schema in TOOL_SCHEMAS:
        if schema["function"]["name"] == name:
            return schema["function"]
    raise AssertionError(f"{name} is not in TOOL_SCHEMAS")


@pytest.fixture
def stripe_checkout(monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            id="cs_test_chat_checkout",
            payment_intent=None,
            url="https://checkout.stripe.test/session",
        )

    monkeypatch.setattr(
        "tickets.services.checkout.stripe.checkout.Session.create",
        create,
    )
    return calls


def test_checkout_tool_schema_exposes_only_booking_selection():
    properties = _schema("create_checkout_link")["parameters"]["properties"]

    assert set(properties) == {"flight_id", "seat_numbers"}
    assert not {
        "user",
        "user_id",
        "email",
        "price",
        "card_number",
        "expiry",
        "cvv",
    } & set(properties)


def test_checkout_tool_creates_order_tickets_payment_and_url(
    user,
    flight,
    airplane,
    stripe_checkout,
):
    seat_numbers = list(
        airplane.seats.order_by("seat_number").values_list("seat_number", flat=True)
    )

    result = call_tool(
        "create_checkout_link",
        {"flight_id": flight.pk, "seat_numbers": seat_numbers},
        user=user,
    )

    assert result["checkout_url"] == "https://checkout.stripe.test/session"
    assert result["total"] == {
        "amount_cents": 24000,
        "amount": "$240.00",
    }
    assert result["seat_numbers"] == seat_numbers

    order = Order.objects.get(pk=result["order_id"])
    assert order.user == user
    assert order.status == Order.Status.PENDING
    assert order.booked_until is not None
    assert list(
        order.tickets.order_by("seat__seat_number").values_list(
            "seat__seat_number", flat=True
        )
    ) == seat_numbers

    payment = Payment.objects.get(order=order)
    assert payment.stripe_session_id == "cs_test_chat_checkout"
    assert payment.amount == 240

    assert len(stripe_checkout) == 1
    assert stripe_checkout[0]["metadata"] == {"order_id": order.pk}
    assert [
        item["price_data"]["unit_amount"]
        for item in stripe_checkout[0]["line_items"]
    ] == [flight.base_price, flight.base_price]


def test_checkout_tool_rejects_a_past_flight_without_reserving(
    user,
    flight,
    airplane,
    stripe_checkout,
):
    flight.departure = timezone.now() - timedelta(minutes=1)
    flight.save(update_fields=["departure"])

    result = create_checkout_link(
        user=user,
        flight_id=flight.pk,
        seat_numbers=[airplane.seats.first().seat_number],
    )

    assert "already departed" in result["error"]
    assert Order.objects.count() == 0
    assert stripe_checkout == []


def test_checkout_tool_rejects_an_unavailable_seat(
    user,
    other_user,
    flight,
    airplane,
    stripe_checkout,
):
    seat = airplane.seats.first()
    Ticket.objects.create(user=other_user, flight=flight, seat=seat)

    result = create_checkout_link(
        user=user,
        flight_id=flight.pk,
        seat_numbers=[seat.seat_number],
    )

    assert "no longer available" in result["error"]
    assert Order.objects.count() == 0
    assert stripe_checkout == []


def test_failed_stripe_session_releases_the_reserved_seat(
    user,
    flight,
    airplane,
    monkeypatch,
):
    def fail(**kwargs):
        raise RuntimeError("Stripe is unavailable")

    monkeypatch.setattr(
        "tickets.services.checkout.stripe.checkout.Session.create",
        fail,
    )

    result = create_checkout_link(
        user=user,
        flight_id=flight.pk,
        seat_numbers=[airplane.seats.first().seat_number],
    )

    assert "seats were released" in result["error"]
    order = Order.objects.get()
    assert order.status == Order.Status.CANCELLED
    assert list(order.tickets.values_list("status", flat=True)) == [
        Ticket.Status.CANCELLED
    ]
    assert Payment.objects.count() == 0


def test_existing_checkout_endpoint_uses_the_shared_service(
    api_client,
    user,
    flight,
    airplane,
    stripe_checkout,
):
    order = Order.objects.create(user=user)
    order.set_booked_until()
    order.save(update_fields=["booked_until"])
    Ticket.objects.create(
        order=order,
        user=user,
        flight=flight,
        seat=airplane.seats.first(),
    )
    api_client.force_authenticate(user)

    response = api_client.post(
        reverse("tickets:create-checkout-session"),
        {"order_id": order.pk},
        format="json",
    )

    assert response.status_code == 201
    assert response.data == {
        "checkout_url": "https://checkout.stripe.test/session"
    }
    assert stripe_checkout[0]["cancel_url"].endswith("/ws-page/")
