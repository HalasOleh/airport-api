from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework.validators import UniqueTogetherValidator

from tickets.models import Payment, Ticket, Order
from airports.models import Seat, Flight
from rest_framework import serializers


class TicketSerializer(serializers.ModelSerializer):
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
        read_only_fields = ("id",)
        validators = [
            UniqueTogetherValidator(
                queryset=Ticket.objects.all(),
                fields=["seat", "flight"])
        ]

class TicketListSerializer(TicketSerializer):
    seat = serializers.StringRelatedField()
    flight = serializers.StringRelatedField()


class OrderTicketSerializer(serializers.ModelSerializer):
    seat = serializers.PrimaryKeyRelatedField(queryset=Seat.objects.all())
    flight = serializers.PrimaryKeyRelatedField(queryset=Flight.objects.all())

    class Meta:
        model = Ticket
        fields = ("seat", "flight", "status", "price")


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
