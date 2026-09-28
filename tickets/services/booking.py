"""Business logic for validating and reserving flight seats."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from airports.models import Flight, Seat
from tickets.models import Order, Ticket


class BookingError(Exception):
    """A booking error that can safely be shown to the user."""


def normalise_booking_request(flight_id, seat_numbers):
    """Validate and normalise values received from an external caller."""
    try:
        normalised_flight_id = int(flight_id)
    except (TypeError, ValueError):
        raise BookingError(
            "flight_id must be an integer from search_flights."
        ) from None

    if not isinstance(seat_numbers, list) or not seat_numbers:
        raise BookingError("Choose at least one seat number.")

    try:
        normalised_seat_numbers = [
            int(number)
            for number in seat_numbers
        ]
    except (TypeError, ValueError):
        raise BookingError(
            "Every seat number must be an integer."
        ) from None

    if len(normalised_seat_numbers) != len(
        set(normalised_seat_numbers)
    ):
        raise BookingError(
            "Each seat number may be selected only once."
        )

    return normalised_flight_id, normalised_seat_numbers


def _get_bookable_flight(flight_id: int) -> Flight:
    """Return and lock a flight that is currently allowed to be sold."""
    flight = (
        Flight.objects.select_for_update(of=("self",))
        .select_related(
            "airplane",
            "from_airport__city",
            "to_airport__city",
        )
        .filter(pk=flight_id)
        .first()
    )

    if flight is None:
        raise BookingError("Flight not found. Search for the flight again.")

    if flight.departure <= timezone.now():
        raise BookingError(
            "This flight has already departed and cannot be booked."
        )

    if flight.status not in (
        Flight.Status.SCHEDULED,
        Flight.Status.DELAYED,
    ):
        raise BookingError(
            f"A flight with status {flight.status} cannot be booked."
        )

    if flight.airplane_id is None:
        raise BookingError("This flight has no airplane assigned.")

    if not flight.base_price:
        raise BookingError("This flight is not currently on sale.")

    return flight


def _get_requested_seats(
    flight: Flight,
    seat_numbers: list[int],
) -> list[Seat]:
    """Resolve seat numbers and ensure that every requested seat is free."""
    seats = list(
        Seat.objects.filter(
            airplane_id=flight.airplane_id,
            seat_number__in=seat_numbers,
        ).order_by("seat_number")
    )

    found_numbers = {seat.seat_number for seat in seats}
    missing_numbers = sorted(set(seat_numbers) - found_numbers)
    if missing_numbers:
        missing = ", ".join(str(number) for number in missing_numbers)
        raise BookingError(
            f"These seats do not exist on this airplane: {missing}"
        )

    unavailable_numbers = list(
        Ticket.objects.filter(
            flight=flight,
            seat__seat_number__in=seat_numbers,
            status__in=(Ticket.Status.BOOKED, Ticket.Status.USED),
        )
        .order_by("seat__seat_number")
        .values_list("seat__seat_number", flat=True)
    )
    if unavailable_numbers:
        unavailable = ", ".join(
            str(number) for number in unavailable_numbers
        )
        raise BookingError(
            f"These seats are no longer available: {unavailable}"
        )

    return seats


@transaction.atomic
def reserve_seats(user, flight_id, seat_numbers) -> Order:
    """Validate one selection and reserve all its seats atomically."""
    flight_id, seat_numbers = normalise_booking_request(
        flight_id,
        seat_numbers,
    )
    flight = _get_bookable_flight(flight_id)
    seats = _get_requested_seats(flight, seat_numbers)

    order = Order.objects.create(user=user)
    order.set_booked_until()
    order.save(update_fields=["booked_until"])

    try:
        for seat in seats:
            Ticket.objects.create(
                order=order,
                user=user,
                flight=flight,
                seat=seat,
            )
    except (IntegrityError, ValidationError) as exc:
        raise BookingError(
            "One of the selected seats was just booked by someone else."
        ) from exc

    return order


@transaction.atomic
def cancel_reservation(order: Order) -> None:
    """Cancel a pending order and release all of its seats."""
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    order.tickets.update(status=Ticket.Status.CANCELLED)
