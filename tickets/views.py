from rest_framework import viewsets
from tickets.models import Ticket, Order
from tickets.serializers import TicketSerializer, OrderSerializer, TicketListSerializer, OrderRetrieveSerializer


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    filterset_fields = ["status", "seat", "flight", "user"]
    
    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return TicketListSerializer
        return TicketSerializer
    
    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user)
    
    
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    filterset_fields = ["user"]

#    def get_queryset(self):
#        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == "retrieve":
            return OrderRetrieveSerializer  ####
        return OrderSerializer
    
    