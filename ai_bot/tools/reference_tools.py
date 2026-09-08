"""Exact lookups over the slow-moving reference tables.

These rows used to be embedded into the vector index, which was the wrong tool
for them: "Kyiv is a city in Ukraine (UA)." is a short categorical string with
no nuance to capture, and `WHERE code = 'KBP'` answers it exactly, cheaply, and
without competing for a place in the top-k against parking and contact text.
"""
import logging

from django.db.models import Q

from airports.models import Airline, Airplane, Airport, City, Country
from ai_bot.tools.common import clamp_limit

logger = logging.getLogger(__name__)


def _airport_row(airport) -> dict:
    return {
        "code": airport.code,
        "city": airport.city.name,
        "country": airport.country.name,
        "country_code": airport.country.code,
    }


def _city_row(city) -> dict:
    return {
        "name": city.name,
        "country": city.country.name,
        "country_code": city.country.code,
        "airports": sorted(airport.code for airport in city.airports.all()),
    }


def _country_row(country) -> dict:
    return {"name": country.name, "code": country.code}


def _airline_row(airline) -> dict:
    return {
        "name": airline.name,
        "country": airline.country.name if airline.country_id else None,
        "founded_year": airline.founded_year,
        "headquarters": airline.headquarters,
        "airports": sorted(airport.code for airport in airline.airport.all()),
    }


def _airplane_row(airplane) -> dict:
    return {
        "model": airplane.model,
        "reg_number": airplane.reg_number,
        "airline": airplane.airline.name,
        "seats": airplane.seats.count(),
    }


# One entry per entity, so adding another is a single line rather than a new
# branch in a dispatch chain.
ENTITIES = {
    "airport": {
        "queryset": lambda: Airport.objects.select_related("city", "country"),
        "search": lambda q: (
            Q( =q) | Q(city__name__icontains=q) | Q(country__name__icontains=q)
        ),
        "row": _airport_row,
    },
    "city": {
        "queryset": lambda: City.objects.select_related("country").prefetch_related("airports"),
        "search": lambda q: Q(name__icontains=q) | Q(country__name__icontains=q),
        "row": _city_row,
    },
    "country": {
        "queryset": lambda: Country.objects.all(),
        "search": lambda q: Q(name__icontains=q) | Q(code__iexact=q),
        "row": _country_row,
    },
    "airline": {
        "queryset": lambda: Airline.objects.select_related("country").prefetch_related("airport"),
        "search": lambda q: (
            Q(name__icontains=q) | Q(country__name__icontains=q) | Q(headquarters__icontains=q)
        ),
        "row": _airline_row,
    },
    "airplane": {
        "queryset": lambda: Airplane.objects.select_related("airline"),
        "search": lambda q: (
            Q(model__icontains=q) | Q(reg_number__iexact=q) | Q(airline__name__icontains=q)
        ),
        "row": _airplane_row,
    },
}


def lookup_reference(entity=None, query=None, limit=None) -> dict:
    """Look up airports, cities, countries, airlines or airplanes by name or code."""
    key = str(entity or "").strip().lower()
    spec = ENTITIES.get(key)
    if spec is None:
        return {
            "error": (
                f"Unknown entity {entity!r}. "
                f"Use one of: {', '.join(sorted(ENTITIES))}."
            )
        }

    queryset = spec["queryset"]()
    term = str(query).strip() if query else ""
    if term:
        queryset = queryset.filter(spec["search"](term))

    rows = [spec["row"](obj) for obj in queryset[: clamp_limit(limit)]]

    if not rows:
        return {
            "entity": key,
            "results": [],
            "detail": f"Nothing matching {query!r} in {key}s.",
        }

    return {"entity": key, "results": rows}
