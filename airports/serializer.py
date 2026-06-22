from rest_framework import serializers
from airports.models import Seat, SeatType, Country, Airport, Airline, Airplane, Flight, City
import logging
from django.db import transaction
from tickets.models import Ticket
from tickets.serializers import TicketSerializer
logger = logging.getLogger(__name__)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "code")
        read_only_fields = ("id",)


class CitySerializer(serializers.ModelSerializer):
    country = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Country.objects.all(),
    )

    class Meta:
        model = City
        fields = ("id", "name", "country")
        read_only_fields = ("id",)


class AirportSerializer(serializers.ModelSerializer):

    city = serializers.SlugRelatedField(
        slug_field="name",
        queryset=City.objects.all(),
    )

    country = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Country.objects.all(),
    )

    class Meta:
        model = Airport
        fields = ("id", "city", "code", "country")
        read_only_fields = ("id",)


class AirlineSerializer(serializers.ModelSerializer):
    airport = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Airport.objects.all(),
        many=True,
    )

    country = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Country.objects.all(),
    )

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
        num_seats = data.get("num_seats")
        num_rows = data.get("num_rows")
        seats_in_row = data.get("seats_in_row")

        if num_seats != seats_in_row * num_rows:
            raise serializers.ValidationError(
                f"Number of seats {num_seats} must be equal to number of rows * seats in row"
            )
        return data


class ShortSeatTypeSerializer(SeatTypeSerializer):
    class Meta:
        model = SeatType
        fields = ("seat_class", "num_seats")
        read_only_fields = ("id",)


class AirplaneSerializer(serializers.ModelSerializer):
#    airline = serializers.StringRelatedField(read_only=True)
#    airline_name = serializers.PrimaryKeyRelatedField(
#        queryset=Airline.objects.all(),
#        source="airline",
#        write_only=True,
#
#    )
    airline = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Airline.objects.all(),
    )
    seat_type = SeatTypeSerializer(many=True, read_only=False, allow_empty=False)

    class Meta:
        model = Airplane
        fields = ("id", "model", "airline", "reg_number", "seat_type")
        read_only_fields = ("id",)

    @transaction.atomic
    def create(self, validated_data):
        seat_types = validated_data.pop("seat_type")
        airplane = Airplane.objects.create(**validated_data)
        for seat_type in seat_types:
            SeatType.objects.create(airplane=airplane, **seat_type)
        return airplane


class AirplaneRetrieveSerializer(AirplaneSerializer):
    seat_type = SeatTypeSerializer(many=True, read_only=True)


class AirplaneListSerializer(AirplaneSerializer):
    seat_type = ShortSeatTypeSerializer(many=True, read_only=True)

 
class FlightSerializer(serializers.ModelSerializer):
    from_airport = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Airport.objects.all(),
    )
    to_airport = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Airport.objects.all(),
    )
    airplane = serializers.SlugRelatedField(
        slug_field="reg_number",
        queryset=Airplane.objects.all(),
    )

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


class FlightRetrieveSerializer(FlightSerializer):
    airplane = AirplaneRetrieveSerializer(read_only=True)
    taken_seats = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field="seat_number",
        source="tickets",
    )

    class Meta:
        model = Flight
        fields = (
            "id",
            "status",
            "from_airport",
            "to_airport",
            "departure",
            "arrival",
            "airplane",
            "taken_seats",
        )
        read_only_fields = ("id",)



class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ("id", "seat_number", "row", "seat_class", "airplane")
        read_only_fields = ("id",)


