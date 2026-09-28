from rest_framework import viewsets
from tickets.models import Ticket, Order
from tickets.serializers import(
    TicketSerializer,
    OrderSerializer,
    TicketListSerializer,
    OrderRetrieveSerializer,
    PaymentRetrieveSerializer,
    OrderIDSerializer,
)
import stripe
from config import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from django.db import transaction

from tickets.services.smtp import send_payment_confirmation_email
from tickets.services.checkout import CheckoutError, create_checkout_session
from .models import Payment

import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    # Without this the project-wide default (admin writes, everyone else reads)
    # applies and no ordinary user can book anything.
    permission_classes = (IsAuthenticated,)
    filterset_fields = ["status", "seat", "flight", "price"]
    
    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return TicketListSerializer
        return TicketSerializer
    
    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ["user"]

#    def get_queryset(self):
#        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == "retrieve":
            return OrderRetrieveSerializer
        return OrderSerializer


class SuccessView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response({"detail": "Session ID is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        # Scoped to the buyer: a leaked session id must not expose someone
        # else's order.
        payment = get_object_or_404(
            Payment, stripe_session_id=session_id, order__user=request.user
        )
        serializer = PaymentRetrieveSerializer(payment)
        return Response(serializer.data, status=http_status.HTTP_200_OK)
    

class CheckoutRateThrottle(UserRateThrottle):
    scope = "checkout"


class CreateCheckoutSessionView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = [CheckoutRateThrottle, AnonRateThrottle]

    
    def post(self, request):
        
        serializer = OrderIDSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]
        
        order = Order.objects.filter(id=order_id, user=request.user).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=http_status.HTTP_404_NOT_FOUND)

        try:
            checkout = create_checkout_session(order)
        except CheckoutError as exc:
            return Response(
                {"detail": str(exc)},
                status=exc.status_code,
            )

        return Response(
            {"checkout_url": checkout["checkout_url"]},
            status=http_status.HTTP_201_CREATED,
        )


class StripeWebhookView(APIView):

    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def post(self, request):
        
        payload = request.body # .body - raw request bytes
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE") # cryptographic signature sent by Stripe in the request headers 
        logger.info(f"Webhook received. Signature present: {bool(sig_header)}")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET) # event - object that represents the event that occurred in Stripe (e.g., a successful payment, a failed payment, etc.)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.error(f"Webhook verification failed: {e}")
            return Response(status=http_status.HTTP_400_BAD_REQUEST)

        logger.info(f"Event type: {event['type']}")

        if event["type"] == "checkout.session.completed":
            handle_checkout_session(
                event,
                payment_status=Payment.Status.SUCCEEDED,
                order_status=Order.Status.COMPLETED,
            )
        elif event["type"] == "checkout.session.expired":
            handle_checkout_session(
                event,
                payment_status=Payment.Status.FAILED,
                order_status=Order.Status.CANCELLED,
            )
        else:
            # Stripe retries every non-2xx response with backoff for days, so an
            # event type we simply do not handle still has to be acknowledged.
            logger.info("Ignoring unhandled event type: %s", event["type"])

        return Response(status=http_status.HTTP_200_OK)

def handle_checkout_session(event, payment_status, order_status):
    session = event["data"]["object"]
    payment = Payment.objects.filter(stripe_session_id=session["id"]).first()

    if not payment:
        logger.error("No payment recorded for Stripe session %s", session["id"])
        return

    with transaction.atomic():
        payment.status = payment_status
        # The payment intent does not exist yet when the checkout session is
        # created, so this is the only place it can be recorded.
        payment.stripe_payment_intent = (
            session.get("payment_intent") or payment.stripe_payment_intent
        )
        payment.save(update_fields=["status", "stripe_payment_intent"])

        payment.order.status = order_status
        payment.order.save(update_fields=["status"])
        logger.info("Order %s updated to %s", payment.order.id, order_status)

    if payment_status == Payment.Status.SUCCEEDED:
        try:
            send_payment_confirmation_email(payment)
        except Exception:
            # Mail must never fail the webhook: a non-2xx makes Stripe replay a
            # payment that has already been applied.
            logger.exception(
                "Confirmation email failed for payment %s", payment.id
            )
