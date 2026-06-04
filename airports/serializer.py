from rest_framework import serializers
from airports.models import Ticket, Country, Airport, Airline, Airplane, Flight
import logging

logger = logging.getLogger(__name__)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "visa_required")
        read_only_fields = ("id",)


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ("id", "city", "code", "country")
        read_only_fields = ("id",)


class AirlineSerializer(serializers.ModelSerializer):

    class Meta:
        model = Airline
        fields = ("id", "name", "founded_year", "headquarters", "airport")
        read_only_fields = ("id",)


class AirplaneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airplane
        fields = ("id", "model", "num_seats", "airline")
        read_only_fields = ("id",)


class FlightSerializer(serializers.ModelSerializer):
    departure = serializers.DateTimeField(
        input_formats=["%d/%m/%Y"]
    )
    arrival = serializers.DateTimeField(
        input_formats=["%d/%m/%Y"]
    )

    class Meta:
        model = Flight
        fields = ("id", "status", "trip", "departure", "arrival", "airplane")
        read_only_fields = ("id",)

    def validate(self, data):
        departure = data.get("departure")
        arrival = data.get("arrival")

        if arrival <= departure:
            logger.warning(
                f"Invalid flight dates. "
                f"Departure={departure}, Arrival={arrival}"
            )
            raise serializers.ValidationError("Date entered incorrectly")

        return data


class TicketSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ticket
        fields = ("id", "status", "seat", "flight", "user")
        read_only_fields = ("id", "status")
