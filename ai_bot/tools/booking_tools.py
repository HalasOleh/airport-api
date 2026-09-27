"""The connected user's own tickets and orders.

The only tool that touches per-user data, and the reason call_tool injects the
user instead of letting the model supply one.
"""
import logging

from ai_bot.tools.common import clamp_limit, money

logger = logging.getLogger(__name__)


def _serialise_ticket(ticket) -> dict:
    flight = ticket.flight
    order = ticket.order
    return {
        "ticket_id": ticket.pk,
        "status": ticket.status,
        "flight_id": flight.pk,
        "from": {"code": flight.from_airport.code, "city": flight.from_airport.city.name},
        "to": {"code": flight.to_airport.code, "city": flight.to_airport.city.name},
        "departure": flight.departure.isoformat(),
        "flight_status": flight.status,
        # Seat is nullable, and its number is a plain integer - see
        # SEAT_NUMBERING_NOTE in flight_tools.
        "seat_number": ticket.seat.seat_number if ticket.seat_id else None,
        "seat_class": ticket.seat.seat_class if ticket.seat_id else None,
        "price": money(ticket.price),
        "order": (
            {
                "order_id": order.pk,
                "status": order.status,
                "booked_until": order.booked_until.isoformat() if order.booked_until else None,
            }
            if order is not None
            else None
        ),
    }


def get_my_bookings(user=None, status=None, limit=None) -> dict:
    """Tickets belonging to the person currently in this chat.

    `user` is injected by call_tool from the authenticated WebSocket scope and
    is deliberately absent from this tool's JSON schema. If it were a parameter
    the model would fill it in, which means the person chatting could dictate it
    ("show bookings for user 5").

    Payment rows are never touched: stripe_session_id and stripe_payment_intent
    have no business in a chat transcript.
    """
    from tickets.models import Ticket

    if user is None or not getattr(user, "is_authenticated", False):
        return {"error": "You need to be signed in before I can look up your bookings."}

    queryset = Ticket.objects.filter(user=user).select_related(
        "flight__from_airport__city", "flight__to_airport__city", "seat", "order"
    )

    if status:
        normalised = str(status).strip().upper()
        if normalised not in Ticket.Status.values:
            return {
                "error": (
                    f"Unknown ticket status {status!r}. "
                    f"Use one of: {', '.join(Ticket.Status.values)}."
                )
            }
        queryset = queryset.filter(status=normalised)

    # Ticket.Meta orders by seat, which is meaningless to a person reading their
    # own bookings - the next flight is what they want first.
    tickets = list(queryset.order_by("-flight__departure")[: clamp_limit(limit)])

    if not tickets:
        return {"bookings": [], "detail": "You have no bookings matching that."}

    return {"bookings": [_serialise_ticket(ticket) for ticket in tickets]}
