from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=31)
    airports = models.ForeignKey("Airport", on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Airport(models.Model):
    name = models.CharField(max_length=63)
    airlines = models.ForeignKey("Airline", on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Airline(models.Model):
    name = models.CharField(max_length=63)
    airplanes = models.ForeignKey("Airplane", on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Airplane(models.Model):
    name = models.CharField(max_length=63)
    flights = models.ForeignKey("Flight", on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Flight(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCH", "Scheduled",
        BOARDING = "BOA", "Boarding",
        DEPARTED = "DEP", "Departed",
        DELAYED = "DEL", "Senior",
        CANCELLED = "CAN", "Cancelled",


    name = models.CharField(max_length=63)
    status = models.CharField(
        max_length=3,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    tickets = models.ForeignKey("Ticket", on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}: {self.status}"


class Ticket(models.Model):
    class Status(models.TextChoices):
        BOOKED = "BOO", "Booked",
        CANCELLED = "CAN", "Cancelled",
        USED = "USE", "Used",


    status = models.CharField(
        max_length=3,
        choices=Status,
        default=Status.BOOKED,
    )
    seat = models.IntegerField()
    trip = models.CharField(max_length=127)

    def __str__(self):
        return f"{self.name} {self.seat}"
