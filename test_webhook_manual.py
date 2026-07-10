import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tickets.models import Order, Payment

order_id = 13

try:
    order = Order.objects.get(id=order_id)
    payment = order.payments.first()

    if payment:
        print(f"Payment : ID={payment.id}, status={payment.status}")
        print(f"Session ID: {payment.stripe_session_id}")

)
        payment.status = Payment.Status.SUCCEEDED
        payment.save()

        order.status = Order.Status.COMPLETED
        order.save()

        print(f"Status update!")
        print(f"Payment: {payment.status}")
        print(f"Order: {order.status}")
    else:
        print(f"Payment not found {order_id}")

except Order.DoesNotExist:
    print(f"Order {order_id} do not exist")
