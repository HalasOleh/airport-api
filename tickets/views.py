from decimal import Decimal

from rest_framework import viewsets
from tickets.models import Ticket, Order
from tickets.serializers import(
    TicketSerializer,
    OrderSerializer,
    TicketListSerializer,
    OrderRetrieveSerializer,
    PaymentRetrieveSerializer,
)
import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from .models import Payment

import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class  TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
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
    def get(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response({"detail": "Session ID is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        payment = get_object_or_404(Payment, stripe_session_id=session_id)
        serializer = PaymentRetrieveSerializer(payment)
        return Response(serializer.data, status=http_status.HTTP_200_OK)
    

class CheckoutRateThrottle(UserRateThrottle):
    scope = "checkout"


class CreateCheckoutSessionView(APIView):
    throttle_classes = [CheckoutRateThrottle, AnonRateThrottle]

    def post(self, request, order_id):
        order = Order.objects.filter(id=order_id, user=request.user).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=http_status.HTTP_404_NOT_FOUND)

        if order.expire():
            return Response({"detail": "Booking expired. Order was cancelled."}, status=http_status.HTTP_400_BAD_REQUEST)

        if order.status != Order.Status.PENDING:
            return Response({"detail": "Order is no longer pending."}, status=http_status.HTTP_400_BAD_REQUEST)

        tickets = order.tickets.all()
        if not tickets:
            return Response({"detail": "Order has no tickets."}, status=http_status.HTTP_400_BAD_REQUEST)

        line_items = [
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": ticket.price,  # in cents
                    "product_data": {
                        "name": f"Ticket #{ticket.id} -- {ticket.flight}",
                    },
                },
                "quantity": 1,
            }
            for ticket in tickets
        ]

        session = stripe.checkout.Session.create(
            payment_method_types=["card"], # Stripe chose by himself what show but here we can add more payment methods like ["card", "paypal"]
            line_items=line_items, # user itmes data
            mode="payment",# or "subscription" or "setup"
            success_url="http://localhost:8000/tickets/payments/success/?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:8000/tickets/payments/cancel/",# change url to your frontend cancel page
            metadata={"order_id": order.id},# stripe will send this data to webhook we can sand different data
        )

        Payment.objects.create(
            order=order,
            stripe_session_id=session.id,
            stripe_payment_intent=session.payment_intent or "",
            amount=Decimal(order.price) / Decimal(100),  # DecimalField — convert in dollars from cents, Decima is used to avoid floating-point precision issues
            currency="usd",
            status=Payment.Status.PENDING,
        )

        return Response({"checkout_url": session.url}, status=http_status.HTTP_201_CREATED)

#@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):

    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def post(self, request):
        
        payload = request.body # .body - raw request bytes
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE") # cryptographic signature sent by Stripe in the request headers
        # print(payload)
        logger.info(f"Webhook received. Signature present: {bool(sig_header)}")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET) # event - object that represents the event that occurred in Stripe (e.g., a successful payment, a failed payment, etc.)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.error(f"Webhook verification failed: {e}")
            return Response(status=http_status.HTTP_400_BAD_REQUEST)

        logger.info(f"Event type: {event['type']}")

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]

            session
            payment = Payment.objects.filter(stripe_session_id=session["id"]).first()
            print(payment)
            if payment:
                logger.info(f"Payment found (ID: {payment.id}), updating...")
                payment.status = Payment.Status.SUCCEEDED
                payment.stripe_payment_intent = session.get("payment_intent", "")
                payment.save()
                # if the payment is successful, but our program is crushed here, then the user has paid for the order, but the order status will not change to COMPLETED
                payment.order.status = Order.Status.COMPLETED
                payment.order.save()
                logger.info(f"Order {payment.order.id} updated to COMPLETED")
                return Response(status=http_status.HTTP_200_OK)
            else:
                logger.error(f"Payment not found for session: {session['id']}")
                return Response(status=http_status.HTTP_404_NOT_FOUND)

        return Response(status=http_status.HTTP_200_OK) # TODO: handle other event types if needed
