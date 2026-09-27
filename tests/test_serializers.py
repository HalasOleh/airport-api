from datetime import timedelta

import pytest
from django.utils import timezone

from airports.models import Flight, SeatClass
from airports.serializer import FlightSerializer, SeatTypeSerializer
from tickets.serializers import OrderSerializer


def test_seat_type_serializer_accepts_correct_number_of_seats():
    serializer = SeatTypeSerializer(
        data={
            "seat_class": SeatClass.ECONOMY,
            "num_seats": 6,
            "num_rows": 2,
            "seats_in_row": 3,
        }
    )

    assert serializer.is_valid() is True


def test_seat_type_serializer_rejects_wrong_number_of_seats():
    serializer = SeatTypeSerializer(
        data={
            "seat_class": SeatClass.ECONOMY,
            "num_seats": 5,
            "num_rows": 2,
            "seats_in_row": 3,
        }
    )

    assert serializer.is_valid() is False
    assert "non_field_errors" in serializer.errors


@pytest.mark.django_db
def test_flight_serializer_accepts_correct_data(airports, airplane):
    departure = timezone.now() + timedelta(days=1)
    serializer = FlightSerializer(
        data={
            "status": Flight.Status.SCHEDULED,
            "from_airport": airports[0].code,
            "to_airport": airports[1].code,
            "departure": departure,
            "arrival": departure + timedelta(hours=2),
            "airplane": airplane.reg_number,
        }
    )

    assert serializer.is_valid() is True


@pytest.mark.django_db
def test_flight_serializer_rejects_arrival_before_departure(
    airports,
    airplane,
):
    departure = timezone.now() + timedelta(days=1)
    serializer = FlightSerializer(
        data={
            "status": Flight.Status.SCHEDULED,
            "from_airport": airports[0].code,
            "to_airport": airports[1].code,
            "departure": departure,
            "arrival": departure - timedelta(hours=1),
            "airplane": airplane.reg_number,
        }
    )

    assert serializer.is_valid() is False
    assert "non_field_errors" in serializer.errors


@pytest.mark.django_db
def test_flight_serializer_rejects_unknown_status(airports, airplane):
    departure = timezone.now() + timedelta(days=1)
    serializer = FlightSerializer(
        data={
            "status": "UNKNOWN",
            "from_airport": airports[0].code,
            "to_airport": airports[1].code,
            "departure": departure,
            "arrival": departure + timedelta(hours=2),
            "airplane": airplane.reg_number,
        }
    )

    assert serializer.is_valid() is False
    assert "status" in serializer.errors


def test_order_serializer_rejects_empty_ticket_list():
    serializer = OrderSerializer(data={"tickets": []})

    assert serializer.is_valid() is False
    assert "tickets" in serializer.errors
