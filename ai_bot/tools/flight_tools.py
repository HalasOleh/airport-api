"""Flights: search, fares and seat maps.

This is the data that can never live in the vector index - it changes by the
minute, and "is seat 12 free" has exactly one right answer, not a nearest match.
"""
import logging

from django.db.models import Count
from django.utils import timezone

from airports.models import Flight, Seat, SeatClass
from ai_bot.tools.common import airport_q, clamp_limit, day_range, money

logger = logging.getLogger(__name__)

# Listing every seat of an A320 would spend 180 rows of context on something
# the model only needs a sample of.
MAX_SEATS_LISTED = 60

SEAT_NUMBERING_NOTE = (
    "Seats are identified by a plain integer (1, 2, 3...). This airline has no "
    "letter suffixes - never invent one like '12A'."
)


def _active_ticket_filter(flight_id: int) -> dict:
    from tickets.models import Ticket

    return {
        "flight_id": flight_id,
        "status__in": (Ticket.Status.BOOKED, Ticket.Status.USED),
    }


def availability(flight: Flight) -> dict:
    """Free seats on one flight, in total and per class.

    Deliberately mirrors the capacity rule in Ticket.clean(): capacity is the
    airplane's seat count, and only BOOKED/USED tickets hold a seat. Reporting
    anything looser would let the bot promise a seat that the booking path then
    refuses with a ValidationError.

    Tickets sitting in expired PENDING orders are counted as taken. Order.expire()
    only runs lazily from checkout, so those tickets are still BOOKED and
    Ticket.clean() still counts them - calling them free would offer a seat that
    cannot actually be sold.
    """
    from tickets.models import Ticket

    if flight.airplane_id is None:
        return {
            "capacity": 0,
            "seats_taken": 0,
            "seats_available": 0,
            "by_class": {},
            "note": "This flight has no airplane assigned, so it has no seats to sell.",
        }

    capacity = Seat.objects.filter(airplane_id=flight.airplane_id).count()
    taken = Ticket.objects.filter(**_active_ticket_filter(flight.pk)).count()
    available = max(0, capacity - taken)

    seats_per_class = dict(
        Seat.objects.filter(airplane_id=flight.airplane_id)
        .values_list("seat_class")
        .annotate(total=Count("id"))
    )
    taken_per_class = dict(
        Ticket.objects.filter(**_active_ticket_filter(flight.pk), seat__isnull=False)
        .values_list("seat__seat_class")
        .annotate(total=Count("id"))
    )

    # A seatless ticket eats capacity without belonging to any class, so the
    # per-class numbers can add up to more than `available`. Clamping each class
    # to the total keeps the breakdown from over-promising.
    by_class = {
        seat_class: max(0, min(total - taken_per_class.get(seat_class, 0), available))
        for seat_class, total in seats_per_class.items()
    }

    return {
        "capacity": capacity,
        "seats_taken": taken,
        "seats_available": available,
        "by_class": by_class,
    }


def _validate_seat_class(seat_class):
    """Returns (normalised_class, error_dict). Exactly one of them is None."""
    if not seat_class:
        return None, None
    normalised = str(seat_class).strip().upper()
    if normalised not in SeatClass.values:
        return None, {
            "error": (
                f"Unknown seat class {seat_class!r}. "
                f"Use one of: {', '.join(SeatClass.values)}."
            )
        }
    return normalised, None


def _serialise_flight(flight: Flight, seat_class: str | None) -> dict:
    classes = [seat_class] if seat_class else list(SeatClass.values)
    return {
        # Flight has no flight number, so the id is the only way a follow-up
        # tool call can point back at this exact flight.
        "flight_id": flight.pk,
        "from": {"code": flight.from_airport.code, "city": flight.from_airport.city.name},
        "to": {"code": flight.to_airport.code, "city": flight.to_airport.city.name},
        "departure": timezone.localtime(flight.departure).isoformat(),
        "arrival": timezone.localtime(flight.arrival).isoformat(),
        "status": flight.status,
        "airplane": flight.airplane.model if flight.airplane else None,
        # base_price 0 means no fare was ever set; Ticket.clean() refuses to
        # sell such a flight, so saying "free" would be a lie.
        "on_sale": bool(flight.base_price),
        "prices": {sc: money(flight.price_for(sc)) for sc in classes},
        **availability(flight),
    }


def search_flights(
    from_airport=None, to_airport=None, date=None, seat_class=None, limit=None
) -> dict:
    """Find flights, with live fares and seat availability."""
    seat_class, error = _validate_seat_class(seat_class)
    if error:
        return error

    queryset = Flight.objects.select_related(
        "from_airport__city", "to_airport__city", "airplane"
    )

    if from_airport:
        queryset = queryset.filter(airport_q(from_airport, "from_airport"))
    if to_airport:
        queryset = queryset.filter(airport_q(to_airport, "to_airport"))

    if date:
        window = day_range(date)
        if window is None:
            return {
                "error": f"Could not read {date!r} as a date. Use the YYYY-MM-DD format."
            }
        queryset = queryset.filter(departure__gte=window[0], departure__lt=window[1])
    else:
        # With no date asked for, a flight that already left is never the answer.
        queryset = queryset.filter(departure__gte=timezone.now())

    flights = list(queryset.order_by("departure")[: clamp_limit(limit)])

    if not flights:
        # An empty result is an answer, not a failure.
        return {
            "flights": [],
            "detail": "No flights match that search.",
            "searched": {"from": from_airport, "to": to_airport, "date": date},
        }

    return {
        "flights": [_serialise_flight(flight, seat_class) for flight in flights],
        "seat_numbering": SEAT_NUMBERING_NOTE,
    }


def get_flight_seats(flight_id=None, seat_class=None) -> dict:
    """Which individual seats are still free on one flight."""
    seat_class, error = _validate_seat_class(seat_class)
    if error:
        return error

    try:
        flight = Flight.objects.select_related(
            "airplane", "from_airport__city", "to_airport__city"
        ).get(pk=flight_id)
    except (Flight.DoesNotExist, TypeError, ValueError):
        return {
            "error": (
                f"No flight with id {flight_id!r}. "
                "Use search_flights first to find the flight and its id."
            )
        }

    if flight.airplane_id is None:
        return {
            "from": {
                "code": flight.from_airport.code,
                "city": flight.from_airport.city.name,
            },
            "to": {
                "code": flight.to_airport.code,
                "city": flight.to_airport.city.name,
            },
            "departure": timezone.localtime(flight.departure).isoformat(),
            "arrival": timezone.localtime(flight.arrival).isoformat(),
            "free_seats": [],
            "detail": "This flight has no airplane assigned, so it has no seats.",
        }

    from tickets.models import Ticket

    seats = Seat.objects.filter(airplane_id=flight.airplane_id)
    if seat_class:
        seats = seats.filter(seat_class=seat_class)

    taken_seat_ids = set(
        Ticket.objects.filter(
            **_active_ticket_filter(flight.pk), seat__isnull=False
        ).values_list("seat_id", flat=True)
    )

    free = [
        {"seat_number": seat.seat_number, "row": seat.row, "seat_class": seat.seat_class}
        for seat in seats.order_by("seat_number")
        if seat.pk not in taken_seat_ids
    ]

    return {
        "from": {
            "code": flight.from_airport.code,
            "city": flight.from_airport.city.name,
        },
        "to": {
            "code": flight.to_airport.code,
            "city": flight.to_airport.city.name,
        },
        "departure": timezone.localtime(flight.departure).isoformat(),
        "arrival": timezone.localtime(flight.arrival).isoformat(),
        "seat_numbering": SEAT_NUMBERING_NOTE,
        "free_seat_count": len(free),
        "free_seats": free[:MAX_SEATS_LISTED],
        "truncated": len(free) > MAX_SEATS_LISTED,
        **availability(flight),
    }
