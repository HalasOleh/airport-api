from django.urls import path, include
from airports.views import TicketViewSet
from rest_framework import routers

app_name = 'airports'

router = routers.DefaultRouter()

router.register('ticket', TicketViewSet)

urlpatterns = [
    path('', include(router.urls)),
]