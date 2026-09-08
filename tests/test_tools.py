"""The tools the chat bot calls against the live database.

Two groups of tests live here. The first is the threat model: the bot talks to
whoever holds the socket, and the model that drives it is steered by their text,
so anything user-scoped has to be proved unreachable from the model's side. The
second is the behaviour that used to be wrong or missing - past flights coming
back as results, city names never matching, no prices, no seat counts.

No LLM is involved: the tools are plain synchronous functions, and the point of
that design is that they can be called directly.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from airports.models import Flight, SeatClass, SeatType
from tickets.models import Ticket

from ai_bot.consumers import trim_history
from ai_bot.tools import TOOL_SCHEMAS, call_tool
from ai_bot.tools.booking_tools import get_my_bookings
from ai_bot.tools.common import clamp_limit
from ai_bot.tools.contact_tools import get_contacts
from ai_bot.tools.flight_tools import get_flight_seats, search_flights
from ai_bot.tools.reference_tools import lookup_reference


def _schema(name):
    for schema in TOOL_SCHEMAS:
        if schema["function"]["name"] == name:
            return schema["function"]
    raise AssertionError(f"{name} is not in TOOL_SCHEMAS")


# --------------------------------------------------------------------------
# Security: the model must have no way to reach another person's data.
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_bookings_are_scoped_to_the_connected_user(user, other_user, flight, airplane):
    seats = list(airplane.seats.all())
    Ticket(user=user, flight=flight, seat=seats[0]).save()
    Ticket(user=other_user, flight=flight, seat=seats[1]).save()

    result = get_my_bookings(user=user)

    assert len(result["bookings"]) == 1
    assert result["bookings"][0]["seat_number"] == seats[0].seat_number


@pytest.mark.django_db
def test_model_supplied_user_id_is_dropped_not_honoured(user, other_user, flight, airplane):
    """The core of the threat model.

    "Show me the bookings of user 5" must not work. call_tool is the only place
    a user reaches a tool, and it takes that user from the WebSocket scope.
    """
    seats = list(airplane.seats.all())
    Ticket(user=user, flight=flight, seat=seats[0]).save()
    Ticket(user=other_user, flight=flight, seat=seats[1]).save()

    result = call_tool("get_my_bookings", {"user_id": other_user.id}, user=user)

    assert len(result["bookings"]) == 1
    assert result["bookings"][0]["seat_number"] == seats[0].seat_number


@pytest.mark.django_db
def test_get_my_bookings_refuses_an_anonymous_caller():
    assert "error" in get_my_bookings(user=None)


def test_no_tool_schema_exposes_a_user_parameter():
    """A parameter is something the model fills in, and anything the model fills
    in is something the person chatting can dictate."""
    for schema in TOOL_SCHEMAS:
        properties = schema["function"]["parameters"]["properties"]
        assert not {"user", "user_id", "email"} & set(properties), schema["function"]["name"]


@pytest.mark.django_db
def test_bookings_never_leak_payment_identifiers(user, flight, airplane):
    Ticket(user=user, flight=flight, seat=airplane.seats.first()).save()

    serialised = str(get_my_bookings(user=user))

    assert "stripe" not in serialised.lower()
    assert user.email not in serialised


# --------------------------------------------------------------------------
# Flight search
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_excludes_flights_that_already_left(airports, airplane, flight):
    departed = timezone.now() - timedelta(days=2)
    Flight.objects.create(
        from_airport=airports[0], to_airport=airports[1],
        departure=departed, arrival=departed + timedelta(hours=2),
        airplane=airplane, base_price=12000,
    )

    result = search_flights(from_airport="KBP", to_airport="LWO")

    # Only the fixture flight, which departs tomorrow.
    assert [f["flight_id"] for f in result["flights"]] == [flight.pk]


@pytest.mark.django_db
def test_search_matches_a_city_name_not_only_a_code(flight):
    """The previous implementation uppercased the token before comparing, which
    turned "Kyiv" into "KYIV" and could never match a city."""
    result = search_flights(from_airport="Kyiv", to_airport="Lviv")

    assert [f["flight_id"] for f in result["flights"]] == [flight.pk]


@pytest.mark.django_db
def test_search_by_date_finds_the_flight(flight):
    """localdate(), not .date(): a date coming from the model means a local
    calendar day, and day_range() builds its window in Europe/Kyiv. Comparing
    against the UTC date passes for most of the day and fails after 21:00 Kyiv
    time, which is exactly the kind of test that fails only in the evening."""
    local_day = timezone.localdate(flight.departure)

    result = search_flights(date=local_day.isoformat())

    assert [f["flight_id"] for f in result["flights"]] == [flight.pk]


@pytest.mark.django_db
def test_unreadable_date_is_an_error_not_a_crash(flight):
    assert "error" in search_flights(date="next tuesday")


@pytest.mark.django_db
def test_no_match_is_an_answer_not_an_error(flight):
    result = search_flights(from_airport="ZZZ")

    assert result["flights"] == []
    assert "error" not in result


@pytest.mark.django_db
def test_fare_multiplier_reaches_the_model(flight):
    result = search_flights(from_airport="KBP", seat_class="BUSINESS")
    prices = result["flights"][0]["prices"]

    # Same 2.5x rule that test_ticket_pricing pins on the model.
    assert prices["BUSINESS"]["amount_cents"] == 30000
    assert prices["BUSINESS"]["amount"] == "$300.00"


@pytest.mark.django_db
def test_unknown_seat_class_is_rejected(flight):
    assert "error" in search_flights(seat_class="LUXURY")


@pytest.mark.django_db
def test_flight_without_a_fare_is_flagged_not_free(flight):
    flight.base_price = 0
    flight.save(update_fields=["base_price"])

    result = search_flights(from_airport="KBP")

    assert result["flights"][0]["on_sale"] is False


# --------------------------------------------------------------------------
# Availability - must agree with Ticket.clean(), which is what actually sells.
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_availability_follows_booked_and_cancelled(user, flight, airplane):
    def free():
        return search_flights(from_airport="KBP")["flights"][0]["seats_available"]

    assert free() == 2

    ticket = Ticket(user=user, flight=flight, seat=airplane.seats.first())
    ticket.save()
    assert free() == 1

    ticket.status = Ticket.Status.CANCELLED
    ticket.save()
    # Ticket.clean() counts BOOKED and USED only, so the seat is back on sale.
    assert free() == 2


@pytest.mark.django_db
def test_availability_breaks_down_by_class(user, flight, airplane):
    SeatType.objects.create(
        seat_class=SeatClass.BUSINESS, airplane=airplane,
        num_seats=1, num_rows=1, seats_in_row=1,
    )

    result = search_flights(from_airport="KBP")["flights"][0]

    assert result["by_class"] == {"ECONOMY": 2, "BUSINESS": 1}


@pytest.mark.django_db
def test_flight_without_an_airplane_reports_no_capacity(airports):
    departure = timezone.now() + timedelta(days=1)
    Flight.objects.create(
        from_airport=airports[0], to_airport=airports[1],
        departure=departure, arrival=departure + timedelta(hours=2),
        airplane=None, base_price=12000,
    )

    result = search_flights(from_airport="KBP")["flights"][0]

    assert result["capacity"] == 0
    assert result["seats_available"] == 0


# --------------------------------------------------------------------------
# Seat maps
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_seat_map_marks_the_sold_seat_taken(user, flight, airplane):
    sold = airplane.seats.order_by("seat_number").first()
    Ticket(user=user, flight=flight, seat=sold).save()

    result = get_flight_seats(flight_id=flight.pk)

    numbers = [seat["seat_number"] for seat in result["free_seats"]]
    assert sold.seat_number not in numbers
    assert result["free_seat_count"] == 1


@pytest.mark.django_db
def test_seat_map_for_a_missing_flight_is_an_error(flight):
    assert "error" in get_flight_seats(flight_id=999999)
    assert "error" in get_flight_seats(flight_id="not a number")


# --------------------------------------------------------------------------
# Reference lookups - what moved out of the vector index.
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_lookup_airport_by_code(airports):
    result = lookup_reference(entity="airport", query="KBP")

    assert [row["code"] for row in result["results"]] == ["KBP"]
    assert result["results"][0]["city"] == "Kyiv"


@pytest.mark.django_db
def test_lookup_city_lists_its_airports(airports):
    result = lookup_reference(entity="city", query="Kyiv")

    assert result["results"][0]["airports"] == ["KBP"]


@pytest.mark.django_db
def test_unknown_entity_is_an_error(airports):
    assert "error" in lookup_reference(entity="spaceport", query="KBP")


# --------------------------------------------------------------------------
# Contacts
# --------------------------------------------------------------------------


def test_contacts_by_exact_department_name():
    result = get_contacts(department="Technical Support")

    assert result["department"] == "Technical Support"
    assert "Phone" in result


def test_unknown_department_returns_the_list_to_choose_from():
    """No substring guessing: the model gets the options and picks."""
    result = get_contacts(department="the people who fix things")

    assert "departments" in result
    assert len(result["departments"]) == 4


def test_contacts_without_an_argument_lists_everything():
    assert len(get_contacts()["departments"]) == 4


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_unknown_tool_is_reported_as_data(user):
    result = call_tool("drop_all_tables", {}, user=user)

    assert "error" in result


@pytest.mark.django_db
def test_invented_parameter_does_not_raise(user, flight):
    result = call_tool("search_flights", {"colour": "blue"}, user=user)

    assert "error" in result


@pytest.mark.parametrize(
    "supplied,expected",
    [(9999, 50), (None, 10), ("abc", 10), (0, 1), (-5, 1), ("3", 3)],
)
def test_limit_is_clamped(supplied, expected):
    assert clamp_limit(supplied) == expected


# --------------------------------------------------------------------------
# History trimming
# --------------------------------------------------------------------------


def test_trim_never_orphans_a_tool_result():
    """A tool message whose assistant message was trimmed away is rejected
    outright by the API, so the window has to start on a user message."""
    history = [{"role": "system", "content": "prompt"}]
    for turn in range(30):
        history.append({"role": "user", "content": f"q{turn}"})
        history.append({"role": "assistant", "tool_calls": [{"id": f"c{turn}"}]})
        history.append({"role": "tool", "tool_call_id": f"c{turn}", "content": "{}"})
        history.append({"role": "assistant", "content": f"a{turn}"})

    trimmed = trim_history(history, limit=10)

    assert trimmed[0]["role"] == "system"
    assert trimmed[1]["role"] == "user"
    open_calls = set()
    for message in trimmed[1:]:
        if message.get("tool_calls"):
            open_calls.update(call["id"] for call in message["tool_calls"])
        if message["role"] == "tool":
            assert message["tool_call_id"] in open_calls


def test_short_history_is_left_alone():
    history = [{"role": "system", "content": "p"}, {"role": "user", "content": "hi"}]

    assert trim_history(history, limit=10) is history


# --------------------------------------------------------------------------
# The tool-calling loop. No real model: what is under test is that a second
# round happens at all, that it still carries the tools, and that each call is
# answered by a tool message with the matching id.
# --------------------------------------------------------------------------


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=False):
        dumped = {"role": "assistant"}
        if self.content is not None:
            dumped["content"] = self.content
        if self.tool_calls:
            dumped["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ]
        return dumped


def _fake_openai_client(scripted_messages, calls_seen):
    """A stand-in for AsyncOpenAI that replays scripted responses."""

    async def create(**kwargs):
        calls_seen.append(kwargs)
        message = scripted_messages[len(calls_seen) - 1]
        return type(
            "Response", (), {"choices": [type("Choice", (), {"message": message})()]}
        )()

    completions = type("Completions", (), {"create": staticmethod(create)})()
    chat = type("Chat", (), {"completions": completions})()
    return type("Client", (), {"chat": chat})()


def _consumer(user, messages):
    from ai_bot.consumers import TestConsumer

    consumer = TestConsumer()
    consumer.user = user
    consumer.provider = "openai"
    consumer.dialog = None
    consumer.system_prompt = "test prompt"
    consumer.messages = messages
    return consumer


@pytest.mark.django_db(transaction=True)
async def test_loop_runs_a_second_round_with_tools_still_attached(user, flight, monkeypatch):
    import ai_bot.consumers as consumers

    scripted = [
        _FakeMessage(tool_calls=[
            _FakeToolCall("call_1", "search_flights", '{"from_airport": "Kyiv"}')
        ]),
        _FakeMessage(content="There is one flight to Lviv."),
    ]
    calls_seen = []
    monkeypatch.setattr(
        consumers, "AsyncOpenAI", lambda **_: _fake_openai_client(scripted, calls_seen)
    )

    consumer = _consumer(user, [{"role": "system", "content": "p"},
                                {"role": "user", "content": "flights from Kyiv?"}])
    reply = await consumer.generate_reply_openai()

    assert reply == "There is one flight to Lviv."
    # Two rounds, and the second one still offered the tools - without that the
    # model could never act on what the first call returned.
    assert len(calls_seen) == 2
    assert all("tools" in call for call in calls_seen)

    tool_message = consumer.messages[-2]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_1"
    assert str(flight.pk) in tool_message["content"]


@pytest.mark.django_db(transaction=True)
async def test_two_tool_calls_in_one_round_are_answered_separately(user, flight, monkeypatch):
    import ai_bot.consumers as consumers

    scripted = [
        _FakeMessage(tool_calls=[
            _FakeToolCall("call_a", "lookup_reference", '{"entity": "airport", "query": "KBP"}'),
            _FakeToolCall("call_b", "get_my_bookings", "{}"),
        ]),
        _FakeMessage(content="done"),
    ]
    monkeypatch.setattr(
        consumers, "AsyncOpenAI", lambda **_: _fake_openai_client(scripted, [])
    )

    consumer = _consumer(user, [{"role": "system", "content": "p"},
                                {"role": "user", "content": "codes and my bookings"}])
    await consumer.generate_reply_openai()

    tool_messages = [m for m in consumer.messages if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["call_a", "call_b"]


@pytest.mark.django_db(transaction=True)
async def test_unreadable_tool_arguments_do_not_break_the_reply(user, monkeypatch):
    import ai_bot.consumers as consumers

    scripted = [
        _FakeMessage(tool_calls=[_FakeToolCall("call_1", "search_flights", "{not json")]),
        _FakeMessage(content="Sorry, I could not look that up."),
    ]
    monkeypatch.setattr(
        consumers, "AsyncOpenAI", lambda **_: _fake_openai_client(scripted, [])
    )

    consumer = _consumer(user, [{"role": "system", "content": "p"},
                                {"role": "user", "content": "?"}])
    reply = await consumer.generate_reply_openai()

    # The tool_call id still gets an answer, so the conversation stays valid.
    assert reply == "Sorry, I could not look that up."
    assert "error" in consumer.messages[-2]["content"]
