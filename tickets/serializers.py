from tickets.models import Ticket
from rest_framework import serializers

class TicketSerializer(serializers.ModelSerializer):
    seat = serializers.SlugRelatedField(
        slug_field="seat_number",
        queryset=Ticket.objects.all(),
    )
    flight = serializers.SlugRelatedField(
        slug_field="reg_number",
        queryset=Ticket.objects.all(),
    )
    user = serializers.SlugRelatedField(
        slug_field="username",
        queryset=Ticket.objects.all(),
    )

    class Meta:
        model = Ticket
        fields = ("id", "status", "created_at", "seat", "flight", "user")
        read_only_fields = ("id", "status")
