import os

import requests


API_KEY = os.getenv("WEATHER_API_KEY", "")
CITY = os.getenv("WEATHER_CITY", "Paris")
AIR_QUALITY = os.getenv("WEATHER_AQI", "yes")


def get_weather(city: str = CITY, api_key: str | None = None) -> dict:
    key = api_key or API_KEY
    if not key:
        raise ValueError("WEATHER_API_KEY is not set")

    response = requests.get(
        f"http://api.weatherapi.com/v1/current.json?key={key}&q={city}&aqi={AIR_QUALITY}",
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    return {
        "city": data["location"]["name"],
        "temperature_c": data["current"]["temp_c"],
        "condition": data["current"]["condition"]["text"],
    }


if __name__ == "__main__":
    weather = get_weather()
    print(f"Weather: {weather['city']}, {weather['temperature_c']}°C, {weather['condition']}")
