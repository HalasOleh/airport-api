from django.db import models
from django.core.validators import RegexValidator

class Country(models.Model):
    name = models.CharField(max_length=31, unique=True)
    code = models.CharField(
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{2}$",
                message="Country code must be a two-letter uppercase code UA, US, FR",
            )
        ]
    )

    def __str__(self):
        return self.name

class City(models.Model):
    name = models.CharField(max_length=63, unique=True)
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
                message="Airport code must be a three-letter uppercase code LAX, JFK, CDG",
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

    name = models.CharField(max_length=63, unique=True)
    founded_year = models.IntegerField(null=True, blank=True)
    headquarters = models.CharField(max_length=128)

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

    num_seats = models.IntegerField()
    num_rows = models.IntegerField()
    seats_in_row = models.IntegerField()

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

# При створенні замовлення(Order) вказуєш яке місце він займає/
class Airplane(models.Model):

    model = models.CharField(max_length=63)
    reg_number = models.CharField(max_length=15, unique=True)

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
        self.airplane.seat_type.num_seats)


    def __str__(self):
        return f"Seat {self.seat_number} (row {self.row}) | {self.airplane}"
# в order буде сидіння і order має зберігати ці дані


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


