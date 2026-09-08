"""The price must come from the flight, never from the request.

Every test here corresponds to a hole that was open in production: a ticket
could be created for one cent, on a flight with no fare, holding a seat from a
different airplane, on a plane that was already full.
"""
import pytest
from django.core.exceptions import ValidationError

from airports.models import Airline, Airplane, SeatClass, SeatType
from tickets.models import Ticket


@pytest.mark.django_db
def test_price_is_taken_from_the_flight_not_the_caller(user, flight, airplane):
    seat = airplane.seats.first()

    ticket = Ticket(user=user, flight=flight, seat=seat, price=1)
    ticket.save()

    # 1 was supplied and ignored; 12000 is the flight's economy fare.
    assert ticket.price == 12000


@pytest.mark.django_db
def test_seat_class_multiplies_the_fare(user, flight, airplane):
    SeatType.objects.create(
        seat_class=SeatClass.BUSINESS, airplane=airplane,
        num_seats=1, num_rows=1, seats_in_row=1,
    )
    business_seat = airplane.seats.filter(seat_class=SeatClass.BUSINESS).first()

    ticket = Ticket(user=user, flight=flight, seat=business_seat)
    ticket.save()

    assert ticket.price == 30000  # 12000 * 2.5


@pytest.mark.django_db
def test_price_is_frozen_at_purchase_time(user, flight, airplane):
    ticket = Ticket(user=user, flight=flight, seat=airplane.seats.first())
    ticket.save()

    flight.base_price = 99000
    flight.save(update_fields=["base_price"])
    ticket.status = Ticket.Status.USED
    ticket.save()

    ticket.refresh_from_db()
    # A later fare change must not rewrite what somebody already paid.
    assert ticket.price == 12000


@pytest.mark.django_db
def test_flight_without_a_fare_cannot_be_sold(user, flight, airplane):
    flight.base_price = 0
    flight.save(update_fields=["base_price"])

    with pytest.raises(ValidationError) as exc:
        Ticket(user=user, flight=flight, seat=airplane.seats.first()).save()

    assert "fare" in str(exc.value)


@pytest.mark.django_db
def test_seat_must_belong_to_the_flights_airplane(user, flight, country):
    other_airline = Airline.objects.create(name="Other Air", country=country)
    other_plane = Airplane.objects.create(
        model="Boeing 737", reg_number="BO01", airline=other_airline
    )
    SeatType.objects.create(
        seat_class=SeatClass.ECONOMY, airplane=other_plane,
        num_seats=1, num_rows=1, seats_in_row=1,
    )
    alien_seat = other_plane.seats.first()

    with pytest.raises(ValidationError) as exc:
        Ticket(user=user, flight=flight, seat=alien_seat).save()

    assert "seat" in exc.value.message_dict


@pytest.mark.django_db
def test_the_same_seat_cannot_be_sold_twice(user, flight, airplane):
    seat = airplane.seats.first()
    Ticket(user=user, flight=flight, seat=seat).save()

    with pytest.raises(ValidationError):
        Ticket(user=user, flight=flight, seat=seat).save()


@pytest.mark.django_db
def test_seatless_tickets_are_capped_by_capacity(user, flight, airplane):
    """NULL never collides with NULL in a unique index, so the constraint
    alone allowed unlimited seatless tickets. Capacity is what stops them."""
    capacity = airplane.seats.count()
    assert capacity == 2

    for _ in range(capacity):
        Ticket(user=user, flight=flight, seat=None).save()

    with pytest.raises(ValidationError) as exc:
        Ticket(user=user, flight=flight, seat=None).save()

    assert "fully booked" in str(exc.value)


@pytest.mark.django_db
def test_cancelled_tickets_free_the_capacity(user, flight, airplane):
    tickets = []
    for _ in range(airplane.seats.count()):
        t = Ticket(user=user, flight=flight, seat=None)
        t.save()
        tickets.append(t)

    tickets[0].status = Ticket.Status.CANCELLED
    tickets[0].save()

    # Capacity counts BOOKED and USED only, so a seat is back on sale.
    Ticket(user=user, flight=flight, seat=None).save()
