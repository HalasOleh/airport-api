"""The webhook handler, which used to raise TypeError on every real payment.

Stripe's signature is faked out here: construct_event is the only thing that
talks to the network, and what these tests care about is what happens *after*
the event is accepted.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from tickets.models import Order, Payment, Ticket


def _event(event_type, session_id, payment_intent=None):
    return {
        "id": "evt_test_1",
        "type": event_type,
        "data": {"object": {"id": session_id, "payment_intent": payment_intent}},
    }


@pytest.fixture
def payment(db, user, order, flight, airplane):
    Ticket(user=user, flight=flight, seat=airplane.seats.first(), order=order).save()
    return Payment.objects.create(
        order=order,
        stripe_session_id="cs_test_123",
        stripe_payment_intent="",
        amount=Decimal("120.00"),
        currency="usd",
        status=Payment.Status.PENDING,
    )


@pytest.mark.django_db
def test_completed_session_marks_payment_and_order(api_client, payment):
    event = _event("checkout.session.completed", "cs_test_123", "pi_test_999")

    with patch("stripe.Webhook.construct_event", return_value=event), \
         patch("tickets.views.send_payment_confirmation_email") as send_mail:
        response = api_client.post(
            reverse("payments-webhook"), data="{}", content_type="application/json"
        )

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.SUCCEEDED
    assert payment.order.status == Order.Status.COMPLETED
    # The payment intent only exists once Stripe has charged the card, so the
    # webhook is the only place it can be recorded.
    assert payment.stripe_payment_intent == "pi_test_999"
    send_mail.assert_called_once_with(payment)


@pytest.mark.django_db
def test_expired_session_cancels_the_order(api_client, payment):
    event = _event("checkout.session.expired", "cs_test_123")

    with patch("stripe.Webhook.construct_event", return_value=event), \
         patch("tickets.views.send_payment_confirmation_email") as send_mail:
        response = api_client.post(
            reverse("payments-webhook"), data="{}", content_type="application/json"
        )

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.FAILED
    assert payment.order.status == Order.Status.CANCELLED
    send_mail.assert_not_called()


@pytest.mark.django_db
def test_unhandled_event_type_is_acknowledged(api_client, payment):
    """Anything other than 2xx makes Stripe retry with backoff for days."""
    event = _event("customer.created", "cs_test_123")

    with patch("stripe.Webhook.construct_event", return_value=event):
        response = api_client.post(
            reverse("payments-webhook"), data="{}", content_type="application/json"
        )

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING


@pytest.mark.django_db
def test_unknown_session_does_not_blow_up(api_client, payment):
    event = _event("checkout.session.completed", "cs_does_not_exist")

    with patch("stripe.Webhook.construct_event", return_value=event):
        response = api_client.post(
            reverse("payments-webhook"), data="{}", content_type="application/json"
        )

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING


@pytest.mark.django_db
def test_bad_signature_is_rejected(api_client):
    import stripe

    with patch("stripe.Webhook.construct_event",
               side_effect=stripe.error.SignatureVerificationError("bad", "sig")):
        response = api_client.post(
            reverse("payments-webhook"), data="{}", content_type="application/json"
        )

    assert response.status_code == 400


@pytest.mark.django_db
def test_mail_failure_does_not_fail_the_webhook(api_client, payment):
    """A non-2xx would make Stripe replay a payment that was already applied."""
    event = _event("checkout.session.completed", "cs_test_123", "pi_test_999")

    with patch("stripe.Webhook.construct_event", return_value=event), \
         patch("tickets.views.send_payment_confirmation_email",
               side_effect=RuntimeError("smtp down")):
        response = api_client.post(
            reverse("payments-webhook"), data="{}", content_type="application/json"
        )

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.SUCCEEDED
