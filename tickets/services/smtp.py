from django.core.mail import send_mail
from django.conf import settings

def send_payment_confirmation_email(payment):
    order = payment.order

    send_mail(
        subject="Payment Confirmation",
        message=(
            f"Your payment for order {order.id} has been successfully processed.\n",
            f"Number of order: {order.id}\n",
            f"Total amount: ${payment.amount / 100:.2f}\n",
            f"Payment ID: {payment.id}\n",
            f"Number of tickets: {order.tickets.count()}\n",
            f"Thank you for your purchase!"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.user.email],
        fail_silently=False,
    )
