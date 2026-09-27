from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from tickets.models import Order, Ticket
from tickets.serializers import OrderSerializer


pytestmark = pytest.mark.django_db


@pytest.fixture
def created_booking(
    user,
    flight,
    airplane,
):
    seats = list(airplane.seats.order_by("seat_number"))

    serializer = OrderSerializer(
        data={
            "tickets": [
                {
                    "flight": flight.pk,
                    "seat": seats[0].pk,
                },
                {
                    "flight": flight.pk,
                    "seat": seats[1].pk,
                },
            ]
        }
    )

    assert serializer.is_valid(), serializer.errors

    order = serializer.save(user=user)
    order.refresh_from_db()

    tickets = list(order.tickets.order_by("seat__seat_number"))

    return {
        "order": order,
        "tickets": tickets,
        "seats": seats,
        "user": user,
        "flight": flight,
    }


def test_created_order_is_pending(created_booking):
    order = created_booking["order"]

    assert order.status == Order.Status.PENDING
    assert order.booked_until is not None


def test_booking_creates_booked_tickets(created_booking):
    tickets = created_booking["tickets"]

    assert len(tickets) == 2
    assert all(
        ticket.status == Ticket.Status.BOOKED
        for ticket in tickets
    )


def test_created_tickets_have_correct_data(created_booking):
    tickets = created_booking["tickets"]
    seats = created_booking["seats"]
    user = created_booking["user"]
    flight = created_booking["flight"]

    assert all(ticket.user_id == user.id for ticket in tickets)
    assert [ticket.seat_id for ticket in tickets] == [
        seats[0].pk,
        seats[1].pk,
    ]
    assert all(ticket.price == flight.base_price for ticket in tickets)


@pytest.fixture
def expired_booking(user, flight, airplane):
    current_time = timezone.now()
    order = Order.objects.create(
        user=user,
        booked_until=current_time + timedelta(minutes=10),
    )
    ticket = Ticket.objects.create(
        user=user,
        order=order,
        flight=flight,
        seat=airplane.seats.first(),
    )
    expired_time = current_time + timedelta(minutes=11)

    with patch(
        "tickets.models.timezone.now", return_value=expired_time
    ) as mocked_now:
        was_expired = order.expire()

    order.refresh_from_db()
    ticket.refresh_from_db()

    return {
        "order": order,
        "ticket": ticket,
        "was_expired": was_expired,
        "mocked_now": mocked_now,
    }


def test_expired_booking_is_detected(expired_booking):
    assert expired_booking["was_expired"] is True


def test_expired_booking_cancels_order(expired_booking):
    order = expired_booking["order"]

    assert order.status == Order.Status.CANCELLED


def test_expired_booking_cancels_ticket(expired_booking):
    ticket = expired_booking["ticket"]

    assert ticket.status == Ticket.Status.CANCELLED


def test_booking_expiration_checks_current_time(expired_booking):
    mocked_now = expired_booking["mocked_now"]

    mocked_now.assert_called_once_with()


@pytest.fixture
def rebooked_seat(
    user,
    other_user,
    flight,
    airplane,
):
    seat = airplane.seats.first()

    cancelled_ticket = Ticket.objects.create(
        user=user,
        flight=flight,
        seat=seat,
    )

    cancelled_ticket.status = Ticket.Status.CANCELLED
    cancelled_ticket.save(update_fields=["status"])

    new_ticket = Ticket.objects.create(
        user=other_user,
        flight=flight,
        seat=seat,
    )

    cancelled_ticket.refresh_from_db()
    new_ticket.refresh_from_db()

    return {
        "seat": seat,
        "cancelled_ticket": cancelled_ticket,
        "new_ticket": new_ticket,
        "flight": flight,
    }


def test_cancelled_ticket_releases_seat(rebooked_seat):
    seat = rebooked_seat["seat"]
    cancelled_ticket = rebooked_seat["cancelled_ticket"]
    new_ticket = rebooked_seat["new_ticket"]

    assert cancelled_ticket.status == Ticket.Status.CANCELLED
    assert new_ticket.status == Ticket.Status.BOOKED
    assert new_ticket.seat_id == seat.id


def test_rebooked_seat_has_only_one_active_ticket(rebooked_seat):
    seat = rebooked_seat["seat"]
    flight = rebooked_seat["flight"]
    new_ticket = rebooked_seat["new_ticket"]

    active_ticket_ids = Ticket.objects.filter(
        flight=flight,
        seat=seat,
        status__in=[
            Ticket.Status.BOOKED,
            Ticket.Status.USED,
        ],
    ).values_list("id", flat=True)

    assert list(active_ticket_ids) == [new_ticket.id]
