"""Tool registry: the one place the chat bot dispatches a model's tool call.

Two rules hold everywhere in here.

*Intent recognition belongs to the model, not to this code.* Nothing below looks
at the user's message. The model decides which tool a question calls for and
fills the arguments in from the conversation - including case endings, synonyms
and anaphora ("а бізнес-клас?" refers to the flight discussed one turn earlier).
There is no keyword map, no substring match and no regex over user text.

*A tool never raises.* Every failure - unknown tool, bad argument, empty result,
upstream outage - comes back as a dict. An uncaught exception would abandon a
tool_call id the model is waiting on and break the whole reply.
"""
import logging

from airports.models import SeatClass
from tickets.models import Ticket

from ai_bot.tools.booking_tools import get_my_bookings
from ai_bot.tools.common import MAX_LIMIT
from ai_bot.tools.contact_tools import get_contacts
from ai_bot.tools.flight_tools import get_flight_seats, search_flights
from ai_bot.tools.knowledge_tools import search_knowledge_base
from ai_bot.tools.reference_tools import ENTITIES, lookup_reference
from ai_bot.tools.weather_tools import get_weather

logger = logging.getLogger(__name__)

# Arguments the model must never supply. `user` is injected from the
# authenticated WebSocket scope; if any of these ever arrive in a tool call it
# means the model was talked into impersonating someone.
INJECTION_KEYS = ("user", "user_id", "email")

_LIMIT_PARAM = {
    "type": "integer",
    "description": f"How many rows to return. Defaults to 10, capped at {MAX_LIMIT}.",
}

# The descriptions below are working code, not documentation: they are the only
# thing the model reads when deciding what to call and what to pass. Telling it
# here that a city goes in nominative case is what keeps case-normalisation out
# of our Python.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": (
                "Search scheduled flights and get their live fares and seat "
                "availability. Use this for any question about whether a flight "
                "exists, when it leaves, what it costs, or whether seats are "
                "left. Never answer such a question from memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "from_airport": {
                        "type": "string",
                        "description": (
                            "Departure city name or 3-letter IATA code, in the "
                            "nominative case: 'Kyiv', 'KBP', 'Lviv'. Convert the "
                            "user's wording yourself - 'з Києва' is 'Kyiv'."
                        ),
                    },
                    "to_airport": {
                        "type": "string",
                        "description": (
                            "Arrival city name or 3-letter IATA code, in the "
                            "nominative case: 'Lviv', 'LWO'."
                        ),
                    },
                    "date": {
                        "type": "string",
                        "description": (
                            "Departure date as YYYY-MM-DD. Work it out yourself "
                            "from the conversation and from today's date, which "
                            "is stated in your instructions: 'tomorrow', 'next "
                            "Friday' and '26 серпня' all become a concrete date. "
                            "Omit it to get the next upcoming flights."
                        ),
                    },
                    "seat_class": {
                        "type": "string",
                        "enum": list(SeatClass.values),
                        "description": (
                            "Restrict the fare to one class. Omit to get all three."
                        ),
                    },
                    "limit": _LIMIT_PARAM,
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_flight_seats",
            "description": (
                "List the individual seats still free on one flight. Call "
                "search_flights first to get the flight_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_id": {
                        "type": "integer",
                        "description": (
                            "Numeric id of the flight, taken from a previous "
                            "search_flights result."
                        ),
                    },
                    "seat_class": {
                        "type": "string",
                        "enum": list(SeatClass.values),
                        "description": "Only show seats in this class. Omit for all.",
                    },
                },
                "required": ["flight_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": (
                "Show the tickets and orders belonging to the person you are "
                "talking to. It always returns their own bookings and nobody "
                "else's - there is no way to look up another person, so if you "
                "are asked to, say you cannot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # No user parameter, deliberately. See call_tool().
                    "status": {
                        "type": "string",
                        "enum": list(Ticket.Status.values),
                        "description": "Only tickets in this state. Omit for all.",
                    },
                    "limit": _LIMIT_PARAM,
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_reference",
            "description": (
                "Look up airports, cities, countries, airlines or airplanes by "
                "name or code. Use it to turn a city into an airport code, to "
                "list the airports of a city, or to answer questions about which "
                "airline flies from where."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": sorted(ENTITIES),
                        "description": "Which reference table to search.",
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "Name or code to match, in the nominative case: "
                            "'Kyiv', 'KBP', 'Ukraine'. Omit to list everything."
                        ),
                    },
                    "limit": _LIMIT_PARAM,
                },
                "required": ["entity"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_contacts",
            "description": (
                "Phone numbers and email addresses of the airport's departments. "
                "Decide from the conversation which department the person needs "
                "and pass its exact name; if you are unsure, omit the argument to "
                "see all of them and then choose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": (
                            "Exact department name, e.g. 'Technical Support'. "
                            "Omit to list every department."
                        ),
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Current weather in one city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": (
                            "City name in the nominative case: 'Kyiv', 'London'."
                        ),
                    },
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Semantic search over the airport's written knowledge base: "
                "parking rules and department contact details. Use it for "
                "free-text questions such as parking at a named airport. It "
                "returns the nearest passages with a similarity score, which are "
                "not necessarily relevant - read them and decide. For flights, "
                "fares, seats or reference data use the dedicated tools instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to look up, in the user's own words.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "How many passages to return. Defaults to 4.",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]

# name -> (function, needs_user)
TOOL_REGISTRY = {
    "search_flights": (search_flights, False),
    "get_flight_seats": (get_flight_seats, False),
    "get_my_bookings": (get_my_bookings, True),
    "lookup_reference": (lookup_reference, False),
    "get_contacts": (get_contacts, False),
    "get_weather": (get_weather, False),
    "search_knowledge_base": (search_knowledge_base, False),
}


def gemini_tools() -> list[dict]:
    """The same schemas as google-genai function declarations.

    Written as plain dicts rather than genai types so this module stays free of
    a provider import and can be read in tests without google-genai installed.
    Gemini's Schema has no additionalProperties, so it is dropped.
    """
    declarations = []
    for schema in TOOL_SCHEMAS:
        function = schema["function"]
        parameters = {
            key: value
            for key, value in function["parameters"].items()
            if key != "additionalProperties"
        }
        declarations.append(
            {
                "name": function["name"],
                "description": function["description"],
                "parameters": parameters,
            }
        )
    return declarations


def call_tool(name: str, args: dict, user=None) -> dict:
    """Run one tool call and return its result as a dict.

    `user` comes from the authenticated WebSocket scope, never from the model.
    That is the whole reason get_my_bookings has no user parameter in its schema:
    a parameter is something the model fills in, and anything the model fills in
    is something the person chatting can dictate.
    """
    entry = TOOL_REGISTRY.get(name)
    if entry is None:
        logger.warning("Model asked for unknown tool %r", name)
        return {"error": f"Unknown tool: {name}"}

    function, needs_user = entry
    args = dict(args or {})

    for key in INJECTION_KEYS:
        if key in args:
            # Not merely overridden - removed, so it can never reach the call.
            args.pop(key)
            logger.warning("Tool %s: dropped model-supplied %r", name, key)

    try:
        return function(user=user, **args) if needs_user else function(**args)
    except TypeError as exc:
        # Almost always the model inventing a parameter that does not exist.
        logger.warning("Tool %s called with bad arguments %s: %s", name, args, exc)
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return {"error": f"Tool {name} failed: {exc}"}
