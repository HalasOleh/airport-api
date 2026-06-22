from django.conf import settings
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator

class Country(models.Model):
    name = models.CharField(
        max_length=31,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z][A-Za-z\s\-]+$",
                message="Country name must start with a letter and contain only letters, spaces or hyphens.",
            )
        ]
    )
    code = models.CharField(
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{2}$",
                message="Country code must be a two-letter uppercase code UA, US, FR.",
            )
        ]
    )
    def __str__(self):
        return self.name


class City(models.Model):
    name = models.CharField(
        max_length=63,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z][A-Za-z\s\-]+$",
                message="City name must start with a capital letter and contain only letters, spaces or hyphens."
            )
        ]
    )
    country = models.ForeignKey(
        "Country",
        on_delete=models.CASCADE,
        related_name="cities"
    )

    def __str__(self):
        return f"{self.name}"


class Airport(models.Model):
    code = models.CharField(
        max_length=5,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{3}$",
                message="Airport code must be a three-letter uppercase code LAX, JFK, CDG.",
            )
        ]
    )
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
    name = models.CharField(
        max_length=63,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z][A-Za-z\s\-]+$",
                message="Airline name must start with a capital letter and contain only letters, spaces or hyphens."
            )
        ]
    )
    founded_year = models.IntegerField(
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^(19|20)\d{2}$",
                message="Founded year must be a four-digit year starting with 19 or 20."
                )
            ]
        )
    headquarters = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z][A-Za-z\s\-]+$",
                message="Headquarters must start with a capital letter and coniain only letters, spaces or hyphens."
                )
            ]        
        )
    country = models.ForeignKey(
        "Country",
        on_delete=models.CASCADE,
        related_name="airlines",
        null=True,
        blank=True,
    )
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

    airplane = models.ForeignKey(
        "Airplane",
        on_delete=models.CASCADE,
        related_name="seat_type"
    )

    num_seats = models.PositiveIntegerField()
    num_rows = models.PositiveIntegerField()
    seats_in_row = models.PositiveIntegerField()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.create_seats()

    def create_seats(self):
        start_number = self.airplane.seats.count() + 1
        for i in range(start_number, start_number + self.num_seats):
            Seat.objects.create(
                seat_number=i,
                row=(i - start_number) // self.seats_in_row + 1,
                seat_class=self.seat_class,
                airplane=self.airplane
            )
    
    def __str__(self):
        return f"Class type {self.get_seat_class_display()}| numbers of seats {self.num_seats}| id {self.id}"

# When creating an order, you specify what place it occupies/
class Airplane(models.Model):

    model = models.CharField(
        max_length=63,
        validators=[
            RegexValidator(
                regex=r"^[A-Z][A-Za-z0-9\s\-]+$",
                message = "Airplane models must start with a capital letter and contain only letters, numbers, spaces or hypenus"
                )
            ]
        )
    reg_number = models.CharField(
        max_length=15,
        unique=True,
        validators = [
            RegexValidator(
                regex=r"^[A-Z]{2}\d{2}$",
                message="Registration number must start with the two capital letter and two numbers"
                )
            ]
        )

    airline = models.ForeignKey(
        "Airline",
        on_delete=models.CASCADE,
        related_name="airplanes")


    def __str__(self):
        return self.model


class Seat(models.Model):

    seat_number = models.IntegerField()
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

    @staticmethod
    def validate_seat(seat: int, num_seats: int, error_to_raise: Exception = ValueError):
        if not (1 <= seat <= num_seats):
            raise error_to_raise(
                {
                    "seat": f"seat must be in range [1, {num_seats}], not {seat}"
                }
            )

    def clean(self):
        self.validate_seat(
        self.seat_number,
        self.airplane.seat_type.num_seats
        )


    def __str__(self):
        return f"Seat {self.seat_number} (row {self.row}) | {self.airplane}"
# order will have a seat and order should store this data


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


