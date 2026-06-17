# Airport Project - Models Diagram

```mermaid
erDiagram
    COUNTRY ||--o{ CITY : "has"
    COUNTRY ||--o{ AIRPORT : "located_in"
    COUNTRY ||--o{ AIRLINE : "based_in"

    CITY ||--o{ AIRPORT : "has"

    AIRPORT }o--o{ AIRLINE : "serves"
    AIRLINE ||--o{ AIRPLANE : "owns"

    SEATTYPE }o--o{ AIRPLANE : "configured_for"
    AIRPLANE ||--o{ SEAT : "contains"
    AIRPLANE ||--o{ FLIGHT : "used_for"

    AIRPORT ||--o{ FLIGHT : "departure_airport"
    AIRPORT ||--o{ FLIGHT : "arrival_airport"

    FLIGHT ||--o{ TICKET : "has"
    SEAT ||--o{ TICKET : "assigned_to"
    USER ||--o{ TICKET : "buys"

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
        string seat_number
        int row
        string seat_class
        int airplane_id
    }

    FLIGHT {
        int id
        string status
        datetime departure
        datetime arrival
        int from_airport_id
        int to_airport_id
        int airplane_id
    }

    TICKET {
        int id
        string status
        datetime created_at
        int seat_id
        int flight_id
        int user_id
    }

    USER {
        int id
        string username
        string role
    }
```

## Changes from previous version:
- `SeatType` response to manage seat class, create seat
- `Airport` add FK to `Country`
- `Airplane` references `SeatType` own seat fields
