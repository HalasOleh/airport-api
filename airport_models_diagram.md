# Airport Project - Models Diagram

```mermaid
erDiagram
    COUNTRY ||--o{ CITY : "has"
    COUNTRY ||--o{ AIRLINE : "headquarters"
    COUNTRY ||--o{ AIRPORT : "located_in"
    CITY ||--o{ AIRPORT : "has"
    AIRPORT ||--o{ AIRLINE : "operates_at"
    AIRLINE ||--o{ AIRPLANE : "owns"
    SEATTYPE ||--o{ AIRPLANE : "defines"
    SEATTYPE ||--o{ SEAT : "classifies"
    AIRPLANE ||--o{ SEAT : "contains"
    AIRPLANE ||--o{ FLIGHT : "uses"
    AIRPORT ||--o{ FLIGHT : "departure"
    AIRPORT ||--o{ FLIGHT : "arrival"
    FLIGHT ||--o{ TICKET : "has"
    SEAT ||--o{ TICKET : "assigned"
    USER ||--o{ TICKET : "purchases"

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
        int seat_type_id
        int airline_id
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
    
    SEAT {
        int id
        string seat_number
        int row
        string seat_class
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
    }
```

## Changes from previous version:
- New `SeatType` model to manage seat configurations
- `Airport` now has direct FK to `Country` (in addition to `City`)
- `Airplane` references `SeatType` instead of having its own seat fields
