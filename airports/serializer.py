from rest_framework import serializers
from airports.models import Ticket, Country, Airport, Airline, Airplane, Flight, City
import logging

logger = logging.getLogger(__name__)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "code")
        read_only_fields = ("id",)


class City(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "name", "country")
        read_only_fields = ("id",)


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ("id", "city", "code")
        read_only_fields = ("id",)


class AirlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airline
        fields = ("id", "name", "founded_year", "headquarters", "airport", "country")
        read_only_fields = ("id",)


class AirplaneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airplane
        fields = ("id", "model", "airline", "reg_number" ,"seats")
        read_only_fields = ("id",)


class FlightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flight
        fields = ("id", "status", "from_airport", "to_airport","departure", "arrival", "airplane")
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
        fields = ("id", "status", "flight", "user")
        read_only_fields = ("id", "status")
