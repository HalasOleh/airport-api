from django.db import models
from django.conf import settings


class Country(models.Model):
    name = models.CharField(max_length=31)
    visa_required = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Airport(models.Model):
    city = models.CharField(max_length=63)
    code = models.CharField(max_length=5, unique=True)

    country = models.ForeignKey(
    "Country",
        on_delete=models.CASCADE,
        related_name="airports"
    )

    def __str__(self):
        return f"{self.city} ({self.code})"


class Airline(models.Model):

    name = models.CharField(max_length=63)
    founded_year = models.IntegerField(null=True, blank=True)
    headquarters = models.CharField(max_length=128)

    airport = models.ForeignKey(
        "Airport",
        on_delete=models.CASCADE,
        related_name="airlines")

    def __str__(self):
        return self.name


class Airplane(models.Model):
    model = models.CharField(max_length=63)
    num_seats = models.IntegerField()

    airline = models.ForeignKey(
        "Airline",
        on_delete=models.CASCADE,
        related_name="airplanes")

    def __str__(self):
        return f"{self.model} ({self.num_seats} seats)"


class Flight(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        BOARDING = "BOARDING", "Boarding"
        DEPARTED = "DEPARTED", "Departed"
        DELAYED = "DELAYED", "Delayed"
        CANCELLED = "CANCELLED", "Cancelled"

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )

    trip = models.CharField(max_length=63)

    departure = models.DateTimeField()
    arrival = models.DateTimeField()

    airplane = models.ForeignKey(
        "Airplane",
        on_delete=models.CASCADE,
        related_name="flights",
        null = True,
        blank = True,
    )

    def __str__(self):
        return f"{self.trip}: {self.status}"


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

    seat = models.IntegerField(unique=True)

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
        return f"Flight {self.flight.trip} | Seat {self.seat} | {self.status}"
