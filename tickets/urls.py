from django.urls import path, include
from tickets.views import (
    TicketViewSet,
    OrderViewSet,
)
from rest_framework import routers

app_name = 'tickets'

router = routers.DefaultRouter()

router.register('ticket', TicketViewSet)
router.register('order', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),

]