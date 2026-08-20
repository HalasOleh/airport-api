from django.urls import path, include
from tickets.views import (
    TicketViewSet,
    OrderViewSet,
    CreateCheckoutSessionView,
    StripeWebhookView,
    SuccessView,
)
from rest_framework import routers

app_name = 'tickets'

router = routers.DefaultRouter()

router.register('ticket', TicketViewSet)
router.register('order', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path("checkout/", CreateCheckoutSessionView.as_view(), name="create-checkout-session"),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("payments/success/", SuccessView.as_view(), name="payments-success"),
    ]
