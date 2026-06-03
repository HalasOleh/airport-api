from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=31)
    airports = models.ForeignKey("Airport", on_delete=models.CASCADE)
    visa_required = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Airport(models.Model):
    city = models.CharField(max_length=64)
    name = models.CharField(max_length=63)
    code = models.CharField(max_length=5, unique=True)
    airlines = models.ForeignKey("Airline", on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Airline(models.Model):
    name = models.CharField(max_length=63)
    founded_year = models.IntegerField(null=True, blank=True)

    headquarters = models.CharField(max_length=128)
    airplanes = models.ForeignKey("Airplane", on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Airplane(models.Model):
    model = models.CharField(max_length=63)
    num_seats = models.IntegerField()

    flights = models.ForeignKey("Flight", on_delete=models.CASCADE, related_name="flights")

    def __str__(self):
        return self.namej


class Flight(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled",
        BOARDING = "BOARDING", "Boarding",
        DEPARTED = "DEPARTED", "Departed",
        DELAYED = "SENIOR", "Senior",
        CANCELLED = "CANCELLED", "Cancelled",

    status = models.CharField(
        max_length=9,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )

    source = models.CharField(max_length=63)
    destination = models.CharField(max_length=63)

    departure = models.DateTimeField()
    arrival = models.DateTimeField()

    tickets = models.ForeignKey("Ticket", on_delete=models.CASCADE, related_name="flights")

    def __str__(self):
        return f"{self.name}: {self.status}"


class Ticket(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOOKED", "Booked",
        CANCELLED = "CANCELLED", "Cancelled",
        USED = "USED", "Used",

    status = models.CharField(
        max_length=9,
        choices=Status,
        default=Status.BOOKED,
    )

    seat = models.IntegerField()
    trip = models.CharField(max_length=127)

    def __str__(self):
        return f"{self.name} {self.seat}"
