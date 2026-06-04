from django.urls import path, include
from airports.views import CountryViewSet, AirportViewSet, AirlineViewSet, AirplaneViewSet, FlightViewSet, TicketViewSet
from rest_framework import routers

app_name = 'airports'

router = routers.DefaultRouter()


router.register('country', CountryViewSet)
router.register('airport', AirportViewSet)
router.register('airline', AirlineViewSet)
router.register('airplane', AirplaneViewSet)
router.register('flight', FlightViewSet)
router.register('ticket', TicketViewSet)

urlpatterns = [
    path('', include(router.urls)),

]