
from rest_framework import mixins, viewsets, status, generics

from airports.models import Country, Airport, Airline, Airplane, Flight, Ticket
from airports.serializer import CountrySerializer, AirportSerializer, AirlineSerializer, AirplaneSerializer, FlightSerializer, TicketSerializer



class CountryViewSet(
    viewsets.ModelViewSet,
):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer


class AirportViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer


class AirlineViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airline.objects.all()
    serializer_class = AirlineSerializer


class AirplaneViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airplane.objects.all()
    serializer_class = AirplaneSerializer


class FlightViewSet(
    viewsets.ModelViewSet,
):
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer


class TicketViewSet(
    viewsets.ModelViewSet,
):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer

