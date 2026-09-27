import pytest

from airports.models import Seat


def test_seat_number_inside_airplane_capacity_is_valid():
    Seat.validate_seat(seat=3, num_seats=10)


def test_seat_number_outside_airplane_capacity_is_invalid():
    with pytest.raises(ValueError):
        Seat.validate_seat(seat=11, num_seats=10)
