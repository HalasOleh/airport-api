"""Current weather, wrapping the existing airports.services.weather client.

The consumer used to carry its own copy of this HTTP call. Reusing the service
keeps one implementation; the only thing added here is the tool contract that
every failure comes back as data rather than an exception.
"""
import logging

from airports.services import weather

logger = logging.getLogger(__name__)


def get_weather(city=None) -> dict:
    """Current weather for one city."""
    if not city:
        return {"error": "Which city should I check the weather for?"}

    try:
        return weather.get_weather(str(city))
    except ValueError as exc:
        # Raised when WEATHER_API_KEY is unset - a deployment problem, not
        # something the user can fix by rephrasing.
        logger.error("Weather lookup unavailable: %s", exc)
        return {"error": "The weather service is not configured on this server."}
    except Exception as exc:
        logger.warning("Weather lookup failed for %r: %s", city, exc)
        return {"error": f"Could not get the weather for {city!r}: {exc}"}
