from django.db import models
from django.conf import settings


class Country(models.Model):
    name = models.CharField(max_length=31)
    code = models.CharField(max_length=2, unique=True) #  UA, US, FR

    def __str__(self):
        return self.name

class City(models.Model):
    name = models.CharField(max_length=63)
    country = models.ForeignKey(
        "Country",
        on_delete=models.CASCADE,
        related_name="cities"
    )

    def __str__(self):
        return f"{self.name} ({self.country})"

class Airport(models.Model):

    code = models.CharField(max_length=5, unique=True)
    city = models.ForeignKey(
    "City",
        on_delete=models.CASCADE,
        related_name="airports"
    )

    def __str__(self):
        return f"{self.city} ({self.code})"


class Airline(models.Model):

    name = models.CharField(max_length=63)
    founded_year = models.IntegerField(null=True, blank=True)
    headquarters = models.CharField(max_length=128)

    country = models.ForeignKey(
        "Country",
        on_delete=models.CASCADE,
        related_name="airlines")

    airport = models.ManyToManyField(
        "Airport",
        related_name="airlines"
    )

    def __str__(self):
        return self.name


class Airplane(models.Model):

    model = models.CharField(max_length=63)
    reg_number = models.CharField(max_length=15, unique=True)

    airline = models.ForeignKey(
        "Airline",
        on_delete=models.CASCADE,
        related_name="airplanes")

    def __str__(self):
        return self.model


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

    from_airport = models.ForeignKey(
        "Airport",
        on_delete=models.CASCADE,
        related_name="from_airport"
    )

    to_airport = models.ForeignKey(
        "Airport",
        on_delete=models.CASCADE,
        related_name="to_airport"
    )

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
        return f"{self.from_airport} - {self.to_airport}: {self.status}"


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


class Seat(models.Model):

    latter = models.CharField(max_length=1)
    num_seat = models.IntegerField()
    seat_in_row = models.IntegerField()
    rows = models.IntegerField()

    class_type = models.CharField(max_length=15)

    airplane = models.ForeignKey(
        "Airplane",
        on_delete=models.CASCADE,
        related_name="seats"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["num_seat", "airplane"],
                name="unique_seat"
            )
        ]

    def __str__(self):
        return f"num_seat {self.num_seat}{self.latter} | {self.airplane}"
