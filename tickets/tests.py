from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase

from tickets.models import Order


class OrderBookingExpiryTests(SimpleTestCase):
    @patch("tickets.models.timezone.now")
    def test_set_booked_until_sets_future_timestamp(self, mock_now):
        mock_now.return_value = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

        order = Order()
        booked_until = order.set_booked_until()

        self.assertEqual(booked_until, datetime(2026, 1, 1, 12, 10, tzinfo=timezone.utc))
        self.assertEqual(order.booked_until, booked_until)
