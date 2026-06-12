from rest_framework import serializers
from airports.models import SeatType, Ticket, Country, Airport, Airline, Airplane, Flight, City
import logging

logger = logging.getLogger(__name__)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "code")
        read_only_fields = ("id",)


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "name", "country")
        read_only_fields = ("id",)


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ("id", "city", "code", "country")
        read_only_fields = ("id",)


class AirlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airline
        fields = ("id", "name", "founded_year", "headquarters", "airport", "country")
        read_only_fields = ("id",)


class SeatTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatType
        fields = ("id", "seat_class", "num_seats", "num_rows", "seats_in_row")
        read_only_fields = ("id",)

    def validate(self, data):
        if data["num_seats"] != data["num_rows"] * data["seats_in_row"]:
            raise serializers.ValidationError("Incorrect number of seats")
        return data


class AirplaneSerializer(serializers.ModelSerializer):
    # nested read representation
    seat_type = SeatTypeSerializer(read_only=True)
    # writable reference for creating/updating
    seat_type_id = serializers.PrimaryKeyRelatedField(
        queryset=SeatType.objects.all(), write_only=True, source='seat_type', allow_null=True, required=False
    )

    class Meta:
        model = Airplane
        fields = ("id", "model", "reg_number", "seat_type", "seat_type_id", "airline")
        read_only_fields = ("id",)

    def create(self, validated_data):
        # `seat_type` will be set by `seat_type_id` via source mapping
        return Airplane.objects.create(**validated_data)

    
class FlightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flight
        fields = ("id", "status", "from_airport", "to_airport", "departure", "arrival", "airplane")
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
        fields = ("id", "status", "created_at", "seat", "flight", "user")
        read_only_fields = ("id", "status")
