from unittest import TestCase
from unittest.mock import Mock, patch

from airports.services.weather import get_weather


class WeatherServiceTests(TestCase):
    @patch("airports.services.weather.requests.get")
    def test_get_weather_returns_expected_summary(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "location": {"name": "Kyiv"},
            "current": {
                "temp_c": 21.5,
                "condition": {"text": "Sunny"},
            },
        }
        mock_get.return_value = mock_response

        result = get_weather("Kyiv", "fake-key")

        self.assertEqual(result["city"], "Kyiv")
        self.assertEqual(result["temperature_c"], 21.5)
        self.assertEqual(result["condition"], "Sunny")
