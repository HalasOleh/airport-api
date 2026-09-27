from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework.validators import UniqueTogetherValidator

from tickets.models import Payment, Ticket, Order
from airports.models import Seat, Flight
from rest_framework import serializers


class SeatBelongsToFlightMixin:
    """Same rule as Ticket.clean(), restated for the API layer.

    Ticket.save() is the guarantee - it cannot be bypassed. This exists so a
    bad request comes back as 400 with a field name attached, instead of a
    model-level ValidationError surfacing as a 500.
    """

    def validate(self, attrs):
        seat = attrs.get("seat")
        flight = attrs.get("flight")
        if seat and flight:
            if flight.airplane_id is None:
                raise serializers.ValidationError(
                    {"flight": "This flight has no airplane assigned, so it has no seats to sell."}
                )
            if seat.airplane_id != flight.airplane_id:
                raise serializers.ValidationError(
                    {"seat": "This seat does not belong to the flight's airplane."}
                )
        return attrs

class TicketSerializer(SeatBelongsToFlightMixin, serializers.ModelSerializer):
    seat = serializers.PrimaryKeyRelatedField(
        queryset=Seat.objects.all(),
        required=False,
        allow_null=True,
    )
    flight = serializers.PrimaryKeyRelatedField(
        queryset=Flight.objects.all()
    )

    class Meta:
        model = Ticket
        fields = ("id", "status", "seat", "flight", "price")
        # price is computed from Flight.base_price; never taken from input.
        read_only_fields = ("id", "status", "price")
        validators = [
            UniqueTogetherValidator(
                queryset=Ticket.objects.filter(
                    status__in=[Ticket.Status.BOOKED, Ticket.Status.USED],
                ),
                fields=["seat", "flight"]
                )
        ]

class TicketListSerializer(TicketSerializer):
    seat = serializers.StringRelatedField()
    flight = serializers.StringRelatedField()


class OrderTicketSerializer(SeatBelongsToFlightMixin, serializers.ModelSerializer):
    seat = serializers.PrimaryKeyRelatedField(queryset=Seat.objects.all())
    flight = serializers.PrimaryKeyRelatedField(queryset=Flight.objects.all())

    class Meta:
        model = Ticket
        fields = ("id", "status", "seat", "flight", "price")
        # price is computed from Flight.base_price; never taken from input.
        read_only_fields = ("id", "status", "price")
        validators = [
            UniqueTogetherValidator(
                queryset=Ticket.objects.filter(
                    status__in=[Ticket.Status.BOOKED, Ticket.Status.USED],
                ),
                fields=["seat", "flight"]
                )
        ]

class OrderSerializer(serializers.ModelSerializer):
    tickets = OrderTicketSerializer(many=True, read_only=False, allow_empty=False)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = ("id", "created_at", "user", "tickets", "status")
        read_only_fields = ("id", "created_at", "user", "status")

    @transaction.atomic()        # do all or nothing
    def create(self, validated_data):

        tickets_data = validated_data.pop("tickets")
        order = Order.objects.create(**validated_data)
        order.set_booked_until()
        order.save()
#
        for ticket_data in tickets_data:
            Ticket.objects.create(
                order=order,
                user=order.user,
                **ticket_data
            )
        return order


class OrderRetrieveSerializer(OrderSerializer):
    tickets = TicketListSerializer(many=True)# many=True


class PaymentRetrieveSerializer(serializers.ModelSerializer):
    order = OrderRetrieveSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "order", "stripe_session_id", "stripe_payment_intent", "amount", "currency", "status", "created_at")
        read_only_fields = ("id", "order", "stripe_session_id", "stripe_payment_intent", "amount", "currency", "status", "created_at")

class OrderIDSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(write_only=True)
    