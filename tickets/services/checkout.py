"""Stripe Checkout creation shared by the REST API and the chat tool."""

import logging
from decimal import Decimal

import stripe
from django.conf import settings

from tickets.models import Order, Payment


logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


class CheckoutError(Exception):
    """A checkout state error that is safe to show to the buyer."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def create_checkout_session(order: Order) -> dict:
    """Create a hosted Stripe Checkout session for one pending order."""
    if order.expire():
        raise CheckoutError("Booking expired. Order was cancelled.")

    if order.status != Order.Status.PENDING:
        raise CheckoutError("Order is no longer pending.")

    tickets = list(order.tickets.select_related("flight"))
    if not tickets:
        raise CheckoutError("Order has no tickets.")

    line_items = [
        {
            "price_data": {
                "currency": "usd",
                "unit_amount": ticket.price,
                "product_data": {
                    "name": f"Ticket #{ticket.id} -- {ticket.flight}",
                },
            },
            "quantity": 1,
        }
        for ticket in tickets
    ]

    logger.info("Creating Stripe Checkout session for order %s", order.id)
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=(
            f"{settings.BASE_URL}/tickets/payments/success/"
            "?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{settings.BASE_URL}/ws-page/",
        metadata={"order_id": order.id},
    )

    Payment.objects.create(
        order=order,
        stripe_session_id=session.id,
        stripe_payment_intent=session.payment_intent or "",
        amount=Decimal(order.price) / Decimal(100),
        currency="usd",
        status=Payment.Status.PENDING,
    )

    return {
        "checkout_url": session.url,
        "amount_cents": order.price,
        "currency": "usd",
    }
