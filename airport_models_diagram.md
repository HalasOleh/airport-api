# Airport Project - Models Diagram

```mermaid
erDiagram
    COUNTRY ||--o{ CITY : has
    COUNTRY ||--o{ AIRPORT : has
    COUNTRY |o--o{ AIRLINE : based_in

    CITY ||--o{ AIRPORT : has

    AIRPORT }o--o{ AIRLINE : serves
    AIRLINE ||--o{ AIRPLANE : owns

    AIRPLANE ||--o{ SEATTYPE : configured_by
    AIRPLANE ||--o{ SEAT : contains
    AIRPLANE |o--o{ FLIGHT : assigned_to

    AIRPORT ||--o{ FLIGHT : departure_airport
    AIRPORT ||--o{ FLIGHT : arrival_airport

    FLIGHT ||--o{ TICKET : has
    SEAT |o--o{ TICKET : assigned_to
    USER ||--o{ TICKET : owns
    USER ||--o{ ORDER : places
    ORDER |o--o{ TICKET : groups
    ORDER ||--o{ PAYMENT : paid_by

    COUNTRY {
        int id
        string name
        string code
    }

    CITY {
        int id
        string name
        int country_id
    }

    AIRPORT {
        int id
        string code
        int country_id
        int city_id
    }

    AIRLINE {
        int id
        string name
        int founded_year
        string headquarters
        int country_id
    }

    SEATTYPE {
        int id
        string seat_class
        int airplane_id
        int num_seats
        int num_rows
        int seats_in_row
    }

    AIRPLANE {
        int id
        string model
        string reg_number
        int airline_id
    }

    SEAT {
        int id
        int seat_number
        int row
        string seat_class
        int airplane_id
    }

    FLIGHT {
        int id
        string status
        int from_airport_id
        int to_airport_id
        datetime departure
        datetime arrival
        int airplane_id
    }

    TICKET {
        int id
        string status
        int seat_id
        int flight_id
        int user_id
        int order_id
        int price
    }

    ORDER {
        int id
        string status
        datetime created_at
        datetime booked_until
        int user_id
    }

    PAYMENT {
        int id
        string status
        int order_id
        string stripe_session_id
        string stripe_payment_intent
        decimal amount
        string currency
        datetime created_at
    }

    USER {
        int id
        string email
        string role
        bool is_staff
        bool is_superuser
    }
```

## Notes

- `Airline.airport` is a `ManyToManyField`, so the diagram shows `AIRPORT }o--o{ AIRLINE`.
- `SeatType.airplane` is a `ForeignKey`; new `SeatType` records generate `Seat` rows for the linked airplane.
- `Ticket` connects `User`, `Flight`, `Seat`, and optionally `Order`.
- `Payment` belongs to an `Order`; one order can have multiple payment records.
- Nullable relationships are shown with optional cardinality, including `Airline.country`, `Flight.airplane`, `Ticket.seat`, and `Ticket.order`.
