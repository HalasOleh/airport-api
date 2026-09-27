"""Exact lookups over the slow-moving reference tables.

These rows used to be embedded into the vector index, which was the wrong tool
for them: "Kyiv is a city in Ukraine (UA)." is a short categorical string with
no nuance to capture, and `WHERE code = 'KBP'` answers it exactly, cheaply, and
without competing for a place in the top-k against parking and contact text.
"""
from django.db.models import Count, Q

from airports.models import Airline, Airplane, Airport, City, Country
from ai_bot.tools.common import clamp_limit


def _lookup_airports(term: str, limit: int) -> list[dict]:
    queryset = Airport.objects.select_related("city", "country")
    if term:
        queryset = queryset.filter(
            Q(code__iexact=term)
            | Q(city__name__icontains=term)
            | Q(country__name__icontains=term)
        )

    return [
        {
            "code": airport.code,
            "city": airport.city.name,
            "country": airport.country.name,
            "country_code": airport.country.code,
        }
        for airport in queryset[:limit]
    ]


def _lookup_cities(term: str, limit: int) -> list[dict]:
    queryset = City.objects.select_related("country").prefetch_related("airports")
    if term:
        queryset = queryset.filter(
            Q(name__icontains=term) | Q(country__name__icontains=term)
        )

    return [
        {
            "name": city.name,
            "country": city.country.name,
            "country_code": city.country.code,
            "airports": sorted(airport.code for airport in city.airports.all()),
        }
        for city in queryset[:limit]
    ]


def _lookup_countries(term: str, limit: int) -> list[dict]:
    queryset = Country.objects.all()
    if term:
        queryset = queryset.filter(
            Q(name__icontains=term) | Q(code__iexact=term)
        )

    return [
        {"name": country.name, "code": country.code}
        for country in queryset[:limit]
    ]


def _lookup_airlines(term: str, limit: int) -> list[dict]:
    queryset = Airline.objects.select_related("country").prefetch_related("airport")
    if term:
        queryset = queryset.filter(
            Q(name__icontains=term)
            | Q(country__name__icontains=term)
            | Q(headquarters__icontains=term)
        )

    return [
        {
            "name": airline.name,
            "country": airline.country.name if airline.country_id else None,
            "founded_year": airline.founded_year,
            "headquarters": airline.headquarters,
            "airports": sorted(airport.code for airport in airline.airport.all()),
        }
        for airline in queryset[:limit]
    ]


def _lookup_airplanes(term: str, limit: int) -> list[dict]:
    queryset = Airplane.objects.select_related("airline").annotate(
        seat_count=Count("seats")
    )
    if term:
        queryset = queryset.filter(
            Q(model__icontains=term)
            | Q(reg_number__iexact=term)
            | Q(airline__name__icontains=term)
        )

    return [
        {
            "model": airplane.model,
            "reg_number": airplane.reg_number,
            "airline": airplane.airline.name,
            "seats": airplane.seat_count,
        }
        for airplane in queryset[:limit]
    ]


def lookup_reference(entity=None, query=None, limit=None) -> dict:
    """Look up airports, cities, countries, airlines or airplanes by name or code."""
    key = str(entity or "").strip().lower()
    term = str(query).strip() if query else ""
    row_limit = clamp_limit(limit)

    if key == "airport":
        rows = _lookup_airports(term, row_limit)
    elif key == "city":
        rows = _lookup_cities(term, row_limit)
    elif key == "country":
        rows = _lookup_countries(term, row_limit)
    elif key == "airline":
        rows = _lookup_airlines(term, row_limit)
    elif key == "airplane":
        rows = _lookup_airplanes(term, row_limit)
    else:
        return {
            "error": (
                f"Unknown entity {entity!r}. "
                "Use one of: airline, airplane, airport, city, country."
            )
        }

    if not rows:
        return {
            "entity": key,
            "results": [],
            "detail": f"Nothing matching {query!r} in {key}s.",
        }

    return {"entity": key, "results": rows}
