from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.db.models import Sum
from django.utils import timezone

from airports.models import Flight, Seat


class Ticket(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        CANCELLED = "CANCELLED", "Cancelled"
        USED = "USED", "Used"

    status = models.CharField(
        max_length=15,
        default=Status.BOOKED,
        choices=Status.choices,

    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE,
        related_name="tickets",
        null=True,
        blank=True,
    )

    flight = models.ForeignKey(
        Flight,
        on_delete=models.CASCADE,
        related_name="tickets")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets"
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        related_name="tickets",
        null=True, blank=True
    )

    price = models.PositiveIntegerField(help_text="Price in cents (e.g. 2000 = $20.00)")
    
    class Meta:
        constraints = [
            UniqueConstraint(fields=["seat", "flight"], name="unique_ticket")
        ]
        ordering = ("seat",)

    def __str__(self):
        return f"Ticket #{self.id}| {self.flight} | {self.status}"

    @property
    def seat_number(self):
        if self.seat is None:
            return None
        return self.seat.seat_number

    def clean(self):
        """Validate that the seat belongs to the flight's airplane."""
        if self.seat and self.flight and self.flight.airplane:
            if self.seat.airplane != self.flight.airplane:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    {"seat": "This seat does not belong to the flight's airplane."}
                )


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        
    created_at = models.DateTimeField(auto_now_add=True)
    booked_until = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=10,
        default=Status.PENDING,
        choices=Status.choices,
    )
    class Meta:
        ordering = ['-created_at']


    @property
    def price(self):
        return self.tickets.aggregate(total=Sum("price"))["total"] or 0

    def set_booked_until(self, minutes: int = 10):
        self.booked_until = timezone.now() + timedelta(minutes=minutes)
        return self.booked_until

    def expire(self):
        if self.status != self.Status.PENDING:
            return False

        if self.booked_until and timezone.now() > self.booked_until:
            self.status = self.Status.CANCELLED
            self.save(update_fields=["status"])
            self.tickets.update(status=Ticket.Status.CANCELLED)
            return True

        return False

    def __str__(self):
        return str(self.created_at)


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"


    order = models.ForeignKey(Order, related_name='payments', on_delete=models.CASCADE)
    stripe_session_id = models.CharField(max_length=255)  # with Stripe Checkout
    stripe_payment_intent = models.CharField(max_length=255)  # for webhook
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency= models.CharField(max_length=3, default="usd")
    status = models.CharField(
        max_length=9,
        default=Status.PENDING,
        choices=Status.choices,
    )  # pending / succeeded / failed
    created_at = models.DateTimeField(auto_now_add=True)
