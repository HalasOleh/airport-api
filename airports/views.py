from rest_framework import mixins, viewsets, status, generics

from airports.models import Ticket
from airports.serializer import Ticket, TicketSerializer


class TicketViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
