from django.urls import path, include
from django.views.generic import TemplateView
from airports.views import (
    CountryViewSet,
    AirportViewSet, 
    AirlineViewSet, 
    AirplaneViewSet, 
    FlightViewSet, 
    SeatTypeViewSet,
    SeatViewSet,
    CityViewSet,
)
from rest_framework import routers

app_name = 'airports'

router = routers.DefaultRouter()


router.register('country', CountryViewSet)
router.register('city', CityViewSet)
router.register('airport', AirportViewSet)
router.register('airline', AirlineViewSet)
router.register('airplane', AirplaneViewSet)
router.register('flight', FlightViewSet)
router.register('seat-type', SeatTypeViewSet)
router.register('seat', SeatViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
