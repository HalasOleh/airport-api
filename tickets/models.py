from django.db import models

from django.conf import settings
from django.db import models


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

    created_at = models.DateTimeField(auto_now_add=True)

    seat = models.ForeignKey(
        "Seat",
        on_delete=models.CASCADE,
        related_name="tickets",
        null=True,
        blank=True,
    )

    flight = models.ForeignKey(
        "Flight",
        on_delete=models.CASCADE,
        related_name="tickets")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets"
    )


    def __str__(self):
        return f"Ticket #{self.id}| {self.flight} | {self.status}"