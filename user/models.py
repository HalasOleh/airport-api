from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'Admin', 'admin'
        USER = 'User', 'user'

    role = models.CharField(
        max_length=15,
        choices=Roles.choices,
        default=Roles.USER
    )


    def __str__(self):
        return self.role
