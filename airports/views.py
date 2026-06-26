from rest_framework import viewsets
from rest_framework_simplejwt.authentication import JWTAuthentication


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
from airports.permissions import IsAdminAllORIsAuthenticatedReadOnly
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
    filterset_fields = ["name", "code"]


class AirportViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer
    filterset_fields = ["code", "city", "country"]


class AirlineViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airline.objects.all()
    serializer_class = AirlineSerializer
    filterset_fields = ["name", "country", "airport"]


class AirplaneViewSet(
    viewsets.ModelViewSet,
):
    queryset = Airplane.objects.all()
    serializer_class = AirplaneSerializer
    permission_classes = (IsAdminAllORIsAuthenticatedReadOnly,)
    search_fields = ['model', 'reg_number', 'airline__name', 'seat_type__num_seats']

    # permission_classes = (IsAdminUser,)# if staff true we can do (list, retrieve, create, update, delete)
    #
    # def get_permissions(self):# DRF trigger this def before every requeste to filter premission for every user/staff
    #     if self.action in ("list", "retrieve"):# self.action - action() - (list, retrieve..)
    #         return (IsAuthenticated(),)
    #     return super().get_permissions()# return what writen in permission_classes upper

    @staticmethod
    def _params_to_ints(query_string):
        """Converts a string of format '1,2,3' to a list of integers [1, 2, 3]"""
        return [int(str_id) for str_id in query_string.split(",")]

    def get_serializer_class(self):
        if self.action == "list":
            return AirplaneListSerializer
        if self.action == "retrieve":
            return AirplaneRetrieveSerializer
        return AirplaneSerializer
    
    def get_queryset(self):
        queryset = self.queryset

        seat_type = self.request.query_params.get("seat_type")
        seat_class = self.request.query_params.get("seat_class")
        if seat_class:
            seat_class_list = seat_class.split(",")
            queryset = queryset.filter(seat_type__seat_class__in=seat_class_list)
        if seat_type:
            seat_type = self._params_to_ints(seat_type)
            queryset = queryset.filter(seat_type__id__in=seat_type)

        if self.action in ("list", "retrieve"):
            return queryset.prefetch_related("seat_type")

        return queryset


class FlightViewSet(
    viewsets.ModelViewSet,
):
    
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer
    pagination_class = FlightPagination
    filterset_fields = ["status", "from_airport", "to_airport", "airplane"]


    def get_serializer_class(self):
        if self.action == "retrieve":
            return FlightRetrieveSerializer
        return FlightSerializer


class SeatTypeViewSet(
    viewsets.ModelViewSet,
):
    queryset = SeatType.objects.all()
    serializer_class = SeatTypeSerializer
    filterset_fields = ["seat_class", "airplane"]


class SeatViewSet(
    viewsets.ModelViewSet,
):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    filterset_fields = ["seat_class", "airplane", "row"]


class CityViewSet(
    viewsets.ModelViewSet,
):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    filterset_fields = ["name", "country"]


