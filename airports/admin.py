from django.contrib import admin
from airports.models import Country, Airport, Airline, Airplane, SeatType, Ticket, Flight, City


class TicketInLine(admin.TabularInline):
    model = Ticket
    extra = 1


class FlightAdmin(admin.ModelAdmin):
    inlines = [TicketInLine]


admin.site.register(Country)
admin.site.register(Airport)
admin.site.register(Airline)
admin.site.register(Airplane)
admin.site.register(Flight, FlightAdmin)
admin.site.register(Ticket)
admin.site.register(SeatType)
admin.site.register(City)