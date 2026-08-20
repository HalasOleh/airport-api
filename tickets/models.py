from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, UniqueConstraint
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
                UniqueConstraint(
                    fields=["seat", "flight"],
                    condition=Q(status__in=["BOOKED", "USED"]),
                    name="unique_active_ticket",
                )
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
        """Rules the database cannot express, because they span two tables."""
        if self.flight_id and not self.flight.base_price:
            # default=0 on a new column would otherwise mean every existing
            # flight silently sells free tickets. Refuse instead of guessing.
            raise ValidationError(
                {"flight": "This flight has no fare set (base_price is 0)."}
            )

        if self.seat_id and self.flight_id:
            if self.flight.airplane_id is None:
                raise ValidationError(
                    {"flight": "This flight has no airplane assigned, so it has no seats to sell."}
                )
            if self.seat.airplane_id != self.flight.airplane_id:
                raise ValidationError(
                    {"seat": "This seat does not belong to the flight's airplane."}
                )

        if self._state.adding and self.flight_id and self.flight.airplane_id:
            # The unique constraint stops the same seat being sold twice, but
            # it cannot count: seat is nullable, and NULL never collides with
            # NULL in a unique index, so seatless tickets were unlimited.
            # Capacity is the invariant that actually matters.
            #
            
            # transaction commits (see save() below). A second request for the
            # same flight blocks right here instead of reading a stale count -
            # by the time it gets the lock, the first ticket is already
            # counted. Without this, two concurrent requests can both read
            # "1 of 1 taken" as false and both insert.
            flight = Flight.objects.select_for_update().get(pk=self.flight_id) # select_for_update() locks the Flight row until the enclosing
            capacity = flight.airplane.seats.count()
            sold = Ticket.objects.filter(
                flight_id=self.flight_id,
                status__in=(Ticket.Status.BOOKED, Ticket.Status.USED),
            ).count()
            if sold >= capacity:
                raise ValidationError(
                    {
                        "flight": (
                            f"This flight is fully booked: {sold} of {capacity} "
                            "seats are already taken."
                        )
                    }
                )

    def _seat_class(self) -> str:
        from airports.models import SeatClass

        return self.seat.seat_class if self.seat_id else SeatClass.ECONOMY

    def save(self, *args, **kwargs):
        """Derive the price and enforce the rules on every write path.

        Putting this in a serializer alone would leave objects.create(), the
        admin, fixtures and shell scripts free to write whatever they like -
        which is exactly how 88 tickets ended up holding seats from other
        airplanes at prices their buyers chose themselves.
        """
        if self._state.adding:
            # atomic() nests as a savepoint when the caller already opened a
            # transaction (OrderSerializer.create() does) or starts a fresh one
            # otherwise (a direct POST to /api/ticket/, the admin, a shell).
            # Either way the select_for_update() lock inside clean() is always
            # valid, so the capacity check can never be skipped by a caller that
            # forgot to wrap this in @transaction.atomic - and it always covers
            # both the check and the insert that follows it.
            with transaction.atomic():
                # Captured once, at purchase time: a later fare change must
                # never rewrite what somebody already paid.
                self.price = self.flight.price_for(self._seat_class())
                # Nothing else calls clean(); full_clean() also checks the
                # unique constraint before the database has to reject the insert.
                self.full_clean()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
    status = models.CharField(
        max_length=10,
        default=Status.PENDING,
        choices=Status.choices,
    )
        
    created_at = models.DateTimeField(auto_now_add=True)
    booked_until = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

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
        
    status = models.CharField(
        max_length=9,
        default=Status.PENDING,
        choices=Status.choices,
    )

    order = models.ForeignKey(Order, related_name='payments', on_delete=models.CASCADE)
    stripe_session_id = models.CharField(max_length=255)  # with Stripe Checkout
    stripe_payment_intent = models.CharField(max_length=255)  # for webhook
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")

    created_at = models.DateTimeField(auto_now_add=True)
