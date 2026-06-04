
from rest_framework import mixins, viewsets, status, generics

from airports.models import Country, Airport, Airline, Airplane, Flight, Ticket
from airports.serializer import CountrySerializer, AirportSerializer, AirlineSerializer, AirplaneSerializer, FlightSerializer, TicketSerializer

import logging

logger = logging.getLogger(__name__)


class CountryViewSet(
    viewsets.ModelViewSet,
):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer

    def perform_create(self, serializer):
        country = serializer.save()

        logger.info(
            f"Country created: id={country.id}, name={country.name}"
        )

class AirportViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer

    def perform_create(self, serializer):
        airport = serializer.save()
        logger.info(f"Airport created: id={airport.id}, code={airport.code}")

    def perform_destroy(self, instance):
        logger.warning(f"Airport deleted: id={instance.id}, code={instance.code}")
        instance.delete()

class AirlineViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airline.objects.all()
    serializer_class = AirlineSerializer

    def perform_create(self, serializer):
        airline = serializer.save()
        logger.info(f"Airline created: id={airline.id}, name={airline.name}")

    def perform_destroy(self, instance):
        logger.warning(f"Airline deleted: id={instance.id}, name={instance.name}")
        instance.delete()


class AirplaneViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airplane.objects.all()
    serializer_class = AirplaneSerializer

    def perform_create(self, serializer):
        airplane = serializer.save()
        logger.info(f"Airplane created: id={airplane.id}, model={airplane.model}")

    def perform_destroy(self, instance):
        logger.warning(f"Airplane deleted: id={instance.id}, model={instance.model}")
        instance.delete()

class FlightViewSet(
    viewsets.ModelViewSet,
):
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer

    def perform_create(self, serializer):
        flight = serializer.save()
        logger.info(f"Flight created: id={flight.id}, trip={flight.trip}")

    def perform_update(self, serializer):
        old_status = self.get_object().status
        flight = serializer.save()

    def perform_destroy(self, instance):
        logger.warning(f"Flight deleted: id={instance.id}, trip={instance.trip}")
        instance.delete()


class TicketViewSet(
    viewsets.ModelViewSet,
):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer

    def perform_create(self, serializer):
        ticket = serializer.save()

        logger.info(
            f"Ticket created: id={ticket.id}, flight={ticket.flight_id}, user={ticket.user_id}"
        )

    def perform_update(self, serializer):
        ticket = serializer.save()

        logger.info(f"Ticket updated: id={ticket.id}")

    def perform_destroy(self, instance):
        logger.info(f"Ticket deleted: id={instance.id}")

        instance.delete()
