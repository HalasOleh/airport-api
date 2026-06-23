
from rest_framework import mixins, viewsets, status, generics

from airports.models import (
    Country,
    Airport,
    Airline,
    Airplane,
    Flight,
    Seat,
    SeatType,
    City,
)
from airports.serializer import (
    AirplaneListSerializer,
    CitySerializer,
    CountrySerializer,
    AirportSerializer,
    AirlineSerializer, 
    AirplaneSerializer, 
    FlightSerializer,
    SeatSerializer,
    SeatTypeSerializer,
    AirplaneRetrieveSerializer,
    FlightRetrieveSerializer,
)
from rest_framework.pagination import PageNumberPagination


class FlightPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 50


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

    def get_serializer_class(self):
        if self.action == "list":
            return AirplaneListSerializer
        if self.action == "retrieve":
            return AirplaneRetrieveSerializer
        return AirplaneSerializer
    
    def get_queryset(self):
        queryset = self.queryset

        if self.action in ("list", "retrieve"):
            return queryset.prefetch_related("seat_type")
        return queryset


class FlightViewSet(
    viewsets.ModelViewSet,
):
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer
    pagination_class = FlightPagination

    
    def get_serializer_class(self):
        if self.action == "retrieve":
            return FlightRetrieveSerializer
        return FlightSerializer


class SeatTypeViewSet(
    viewsets.ModelViewSet,
):
    queryset = SeatType.objects.all()
    serializer_class = SeatTypeSerializer


class SeatViewSet(
    viewsets.ModelViewSet,
):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer


class CityViewSet(
    viewsets.ModelViewSet,
):
    queryset = City.objects.all()
    serializer_class = CitySerializer

