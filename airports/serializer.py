from rest_framework import serializers
from airports.models import Ticket

class TicketSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ticket
        fields = ("id", "status", "seat", "trip")
        read_only_fields = ("id", "status")
