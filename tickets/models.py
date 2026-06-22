from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint

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
        self.validate_seat(
        self.seat,
        self.airplane.seat_type.num_seats
        )

class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return str(self.created_at)
