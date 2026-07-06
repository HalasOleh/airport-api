from django.urls import path, include
from requests import Response
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
router.register('payments/success', SuccessView, basename='payments-success')
urlpatterns = [
    path('', include(router.urls)),
    path("order/<int:order_id>/checkout/", CreateCheckoutSessionView.as_view(), name="create-checkout-session"),
    path("payments/success/", StripeWebhookView.as_view(), name="stripe-webhook"),
    ]
#evenly-jolly-feat-free
#acct_1Tnkk0PZ1F8IHooI
#whsec_9d776091cd236d50b7c7e5b47c0308d2ac298efa5bc78f32f7d3e0bedfe26679