from django.contrib import admin
from airports.models import Country, Airport, Airline, Airplane, Ticket

admin.site.register(Country)
admin.site.register(Airport)
admin.site.register(Airline)
admin.site.register(Airplane)
admin.site.register(Ticket)
