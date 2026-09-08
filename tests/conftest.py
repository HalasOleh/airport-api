"""Shared fixtures.

Everything the suite needs to build a sellable flight lives here, because the
domain has a long chain of required objects: a ticket needs a seat, which needs
an airplane, which needs an airline, and a flight needs two airports, which need
cities and countries. Repeating that setup in every test would bury the thing
each test is actually about.
"""
import pytest
from django.contrib.auth import get_user_model

from airports.models import (
    Airline,
    Airplane,
    Airport,
    City,
    Country,
    Flight,
    SeatClass,
    SeatType,
)
from tickets.models import Order


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        email="buyer@example.com", password="buyer-pass-123"
    )


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(
        email="stranger@example.com", password="stranger-pass-123"
    )


@pytest.fixture
def country(db):
    return Country.objects.create(name="Ukraine", code="UA")


@pytest.fixture
def airports(db, country):
    kyiv = City.objects.create(name="Kyiv", country=country)
    lviv = City.objects.create(name="Lviv", country=country)
    return (
        Airport.objects.create(code="KBP", country=country, city=kyiv),
        Airport.objects.create(code="LWO", country=country, city=lviv),
    )


@pytest.fixture
def airplane(db, country):
    """An airplane with exactly two economy seats.

    Two is deliberate: it is the smallest number that lets a capacity test
    fill the plane and still tell "full" apart from "empty".
    """
    airline = Airline.objects.create(name="Test Air", country=country)
    plane = Airplane.objects.create(model="Airbus A320", reg_number="AR01", airline=airline)
    # SeatType.save() creates the Seat rows as a side effect.
    SeatType.objects.create(
        seat_class=SeatClass.ECONOMY, airplane=plane, num_seats=2, num_rows=1, seats_in_row=2
    )
    return plane


@pytest.fixture
def flight(db, airports, airplane):
    """A flight that can actually be sold: it has an airplane and a fare."""
    from django.utils import timezone
    from datetime import timedelta

    departure = timezone.now() + timedelta(days=1)
    return Flight.objects.create(
        from_airport=airports[0],
        to_airport=airports[1],
        departure=departure,
        arrival=departure + timedelta(hours=2),
        airplane=airplane,
        base_price=12000,  # 120.00 in cents
    )


@pytest.fixture
def order(db, user):
    return Order.objects.create(user=user)


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()
