from django.core.mail import send_mail
from django.conf import settings


def send_payment_confirmation_email(payment):
    order = payment.order

    message = (
        f"Your payment for order {order.id} has been successfully processed.\n"
        f"Total amount: ${payment.amount:.2f}\n"
        f"Payment ID: {payment.id}\n"
        f"Number of tickets: {order.tickets.count()}\n"
        f"Thank you for your purchase!"
    )

    send_mail(
        subject="Payment Confirmation",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.user.email],
        fail_silently=False,
    )