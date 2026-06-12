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
    country = models.ForeignKey(
        "Country",
        on_delete=models.CASCADE,
        related_name="airports"
    )

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


class SeatClass(models.TextChoices):

    ECONOMY = "ECONOMY", "Economy"
    BUSINESS = "BUSINESS", "Business"
    FIRST = "FIRST", "First"


class SeatType(models.Model):
    seat_class = models.CharField(
        max_length=15,
        choices=SeatClass.choices,
        default=SeatClass.ECONOMY,
    )
    
    num_seats = models.IntegerField()
    num_rows = models.IntegerField()
    seats_in_row = models.IntegerField()


    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.create_seats()

    def create_seats(self):
        for i in range(1, self.num_seats + 1):
            Seat.objects.create(
                seat_number=str(i),
                row=(i - 1) // self.seats_in_row + 1,
                seat_class=self.seat_class,
                airplane=self
            )
    def __str__(self):
        return f"Class type {self.seat_class}| numbers of seats {self.num_seats}"


class Airplane(models.Model):

    model = models.CharField(max_length=63)
    reg_number = models.CharField(max_length=15, unique=True)


    seat_type = models.ForeignKey(
        "SeatType",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )


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
        null=True,
        blank=True,
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

    seat_number = models.CharField(max_length=5)
    row = models.IntegerField()

    seat_class = models.CharField(
        max_length=15,
        choices=SeatClass.choices,
        default=SeatClass.ECONOMY,
    )

    airplane = models.ForeignKey(
        "Airplane",
        on_delete=models.CASCADE,
        related_name="seats"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seat_number", "airplane"],
                name="unique_seat"
            )
        ]

    def __str__(self):
        return f"Seat {self.seat_number} (row {self.row}) | {self.airplane}"
