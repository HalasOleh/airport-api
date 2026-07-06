"""
Скрипт для ручного тестування webhook без Stripe CLI
Запусти: python test_webhook_manual.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tickets.models import Order, Payment

# Знайди order який ти щойно оплатив
order_id = 13  # ← ЗМІНИ НА СВІЙ ID

try:
    order = Order.objects.get(id=order_id)
    payment = order.payments.first()

    if payment:
        print(f"✅ Payment знайдено: ID={payment.id}, status={payment.status}")
        print(f"   Session ID: {payment.stripe_session_id}")

        # Вручну оновлюємо статуси (симулюємо webhook)
        payment.status = Payment.Status.SUCCEEDED
        payment.save()

        order.status = Order.Status.COMPLETED
        order.save()

        print(f"✅ Статуси оновлено!")
        print(f"   Payment: {payment.status}")
        print(f"   Order: {order.status}")
    else:
        print(f"❌ Payment не знайдено для Order {order_id}")

except Order.DoesNotExist:
    print(f"❌ Order {order_id} не існує")
