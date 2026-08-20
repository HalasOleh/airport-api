import asyncio
import json
import logging
import os

import requests
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI

from airports.models import Flight
from ai_bot.models import ChatDialog, ChatMessage
from ai_bot.rag import retrieval

logger = logging.getLogger(__name__)


KNOWLEDGE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": (
            "Search the airport knowledge base for parking information, "
            "department phone numbers and email addresses, airports, cities, "
            "countries, airlines and airplanes. Use it whenever the answer "
            "should come from airport reference data rather than from memory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to look up, in the user's own words, "
                        "for example 'parking at Boryspil' or 'technical support phone'."
                    ),
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
}

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a given city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, for example Kyiv, London, New York.",
                }
            },
            "required": ["city"],
            "additionalProperties": False,
        },
    },
}

FLIGHT_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_flight_status",
        "description": "Get flight status and details by searching for flights between airports or by route.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_airport": {
                    "type": "string",
                    "description": "Departure airport code (3 letters, e.g., KBP, JFK, LWO) or city name.",
                },
                "to_airport": {
                    "type": "string",
                    "description": "Arrival airport code (3 letters) or city name.",
                }
            },
            "required": ["from_airport", "to_airport"],
            "additionalProperties": False,
        },
    },
}


def get_weather(city: str) -> dict:
    api_key = os.getenv("WEATHER_API_KEY", "")
    if not api_key:
        return {
            "error": "WEATHER_API_KEY is not set",
            "city": city,
        }

    try:
        response = requests.get(
            f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={city}&aqi=yes",
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        return {
            "city": data["location"]["name"],
            "temperature_c": data["current"]["temp_c"],
            "condition": data["current"]["condition"]["text"],
        }
    except Exception as e:
        return {
            "error": f"Failed to get weather: {str(e)}",
            "city": city,
        }


@database_sync_to_async
def get_flight_status(from_airport: str, to_airport: str) -> dict: #Query database for flights between airports"
    try:
        # Search by airport code or city name
        flights = Flight.objects.filter(
            from_airport__code__icontains=from_airport.upper()
        ).filter(
            to_airport__code__icontains=to_airport.upper()
        )

        if not flights:
            return {
                "message": f"No flights found from {from_airport} to {to_airport}",
                "flights": []
            }

        flight_list = []
        for flight in flights:
            flight_list.append({
                "from": str(flight.from_airport),
                "to": str(flight.to_airport),
                "departure": flight.departure.strftime("%Y-%m-%d %H:%M"),
                "arrival": flight.arrival.strftime("%Y-%m-%d %H:%M"),
                "status": flight.status,
                "airplane": str(flight.airplane) if flight.airplane else "Not assigned",
            })

        return {
            "message": f"Found {len(flight_list)} flight(s)",
            "flights": flight_list
        }
    except Exception as e:
        return {
            "error": f"Failed to get flight status: {str(e)}",
            "flights": []
        }


@database_sync_to_async
def get_dialog_for_connection(user, dialog_id=None):
    if not user or not user.is_authenticated:
        return None

    if dialog_id:
        return ChatDialog.objects.filter(id=dialog_id, user=user).first()

    return ChatDialog.objects.create(user=user)


@database_sync_to_async
def load_dialog_messages(dialog_id):
    return list(
        ChatMessage.objects.filter(dialog_id=dialog_id)
        .order_by("created_at")
        .values("role", "content")
    )


@database_sync_to_async
def save_chat_message(dialog_id, role, content):
    if not dialog_id or not content:
        return None

    return ChatMessage.objects.create(
        dialog_id=dialog_id,
        role=role,
        content=content,
    )
        

# Both providers get the same instructions. Keeping one copy is what stops
# the two branches from drifting into two different products - the Gemini
# path used to have no system prompt at all, so it answered anything.
SYSTEM_PROMPT = (
    "You are an airport assistant. You answer only questions about airports "
    "and air travel: parking, terminals, airport department contacts, "
    "airports, cities, countries, airlines, airplanes, flights and flight "
    "status, and the weather in a city you were asked about. "
    #
    # Without this paragraph the model treats its role as a description of
    # itself rather than a limit, and happily explains what a burger is.
    "Everything else is out of scope: recipes, general knowledge, coding, "
    "personal advice, news, maths. Refuse it with exactly this sentence, "
    "translated into the language the user wrote in and with nothing else "
    "added before or after it: \"Sorry, I can't answer that - I'm an "
    "airport assistant.\" Do not answer partially, do not give a general "
    "overview first, and do not ask a clarifying question to check whether "
    "an off-topic subject was secretly about the airport - refuse "
    "immediately instead. A subject does not become in scope just because "
    "it could exist at an airport, or because the user says 'in general' "
    "or insists after a refusal - burgers in general are off topic even "
    "though airports sell them, and a second refusal looks exactly like "
    "the first. "
    #
    "Available tools: "
    "- search_knowledge_base: parking information, department phone "
    "numbers and emails, airports, cities, countries, airlines, airplanes "
    "- get_weather: current weather "
    "- get_flight_status: flight information between airports. "
    "For anything about airport reference data, call search_knowledge_base "
    "first and answer only from the passages it returns. Those passages are "
    "the nearest matches, not necessarily relevant ones: each carries a "
    "similarity score, and a search always returns something. Read them and "
    "decide. If none of them actually answers the question, say you do not "
    "have that information rather than stretching an unrelated passage into "
    "an answer."
)


@database_sync_to_async
def search_knowledge_base(query: str, top_k: int = retrieval.DEFAULT_TOP_K) -> dict:
    """Vector search over the knowledge base.

    Wrapped because it both queries the database and runs the embedding model,
    neither of which belongs on the event loop.
    """
    return retrieval.search_knowledge_base(query, top_k)


FUNCTIONS = {
    "get_weather": get_weather,
    "get_flight_status": get_flight_status,
    "search_knowledge_base": search_knowledge_base,
}

# Already awaitable; everything else is handed to a worker thread.
ASYNC_FUNCTIONS = {"get_flight_status", "search_knowledge_base"}


class TestConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        dialog_id = self.scope.get("url_route", {}).get("kwargs", {}).get("dialog_id")
        self.dialog = await get_dialog_for_connection(self.user, dialog_id)
        if dialog_id and self.dialog is None:
            await self.close()
            return

        await self.accept()

        self.provider = None
        # conversation memory lives here, for the life of this connection

        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        if self.dialog:
            saved_messages = await load_dialog_messages(self.dialog.id)
            self.messages.extend(saved_messages)
            await self.send(text_data=json.dumps({
                "dialog_id": self.dialog.id,
                "history": saved_messages,
            }))

    async def receive(self, text_data):
        # A malformed frame must not tear down the whole connection.
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send(text_data=json.dumps({"error": "Invalid JSON payload"}))
            return

        if not isinstance(data, dict):
            await self.send(text_data=json.dumps({"error": "Payload must be a JSON object"}))
            return

        if "provider" in data:
            chosen = data["provider"]
            if chosen not in ("gemini", "openai"):
                await self.send(text_data=json.dumps({"error": "Incorrect provider"}))
                self.provider = None
                return
            self.provider = chosen
            logger.info("Client selected provider %s", self.provider)
            await self.send(text_data=json.dumps({"status": f"using {self.provider}"}))
            return

        user_message = (data.get("message") or "").strip()
        if not user_message:
            await self.send(text_data=json.dumps({"error": "Empty message"}))
            return

        if self.provider not in ("gemini", "openai"):
            await self.send(text_data=json.dumps({"error": "Incorrect provider"}))
            self.provider = None
            return

        self.messages.append({"role": "user", "content": user_message})
        if self.dialog:
            await save_chat_message(
                self.dialog.id,
                ChatMessage.Role.USER,
                user_message,
            )

        try:
            reply_text = await self.generate_reply(user_message)
        except Exception:
            # An upstream/model failure should surface as an error frame,
            # not kill the socket and lose the conversation.
            logger.exception("Failed to generate a reply via %s", self.provider)
            await self.send(text_data=json.dumps({"error": "Failed to generate a reply"}))
            return

        await self.send(text_data=json.dumps({"reply": reply_text}))
        if self.dialog and reply_text:
            await save_chat_message(
                self.dialog.id,
                ChatMessage.Role.ASSISTANT,
                reply_text,
            )

    async def generate_reply(self, user_message):
        if self.provider == "gemini":
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            response = await client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=user_message,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            reply_text = response.text
            self.messages.append({"role": "assistant", "content": reply_text})
            return reply_text

        else:
            # No pre-retrieval: the model decides when to search, so a greeting
            # never costs an embedding call.
            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            response = await client.chat.completions.create(
                model="gpt-5.4-nano",
                messages=self.messages,
                tools=[KNOWLEDGE_TOOL, WEATHER_TOOL, FLIGHT_STATUS_TOOL],
            )

            message = response.choices[0].message
            reply_text = message.content
            self.messages.append(message)

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    function_response = await self.call_tool(tool_call)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(function_response),
                    })

                second_response = await client.chat.completions.create(
                    model="gpt-5.4-nano",
                    messages=self.messages,
                )
                reply_text = second_response.choices[0].message.content
                self.messages.append(second_response.choices[0].message)

            return reply_text

    async def call_tool(self, tool_call):
        # Every failure here must come back as a tool result, otherwise the
        # conversation is left with an unanswered tool_call id.
        function_name = tool_call.function.name
        function = FUNCTIONS.get(function_name)
        if function is None:
            return {"error": f"unknown function {function_name}"}

        try:
            function_args = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            return {"error": f"invalid arguments for {function_name}"}

        logger.info("Tool call %s(%s)", function_name, function_args)

        try:
            # Two kinds of tools live in FUNCTIONS. The ones in ASYNC_FUNCTIONS
            # are already wrapped in database_sync_to_async, so they are awaited
            # directly. The rest are plain blocking functions (HTTP calls, file
            # reads) and must go to a worker thread, or they would freeze the
            # event loop and stall every other WebSocket connection.
            if function_name in ASYNC_FUNCTIONS:
                return await function(**function_args)
            # Synchronous functions (file I/O, HTTP requests) go to a thread
            return await asyncio.to_thread(function, **function_args)
        except TypeError as exc:
            return {"error": f"bad arguments for {function_name}: {exc}"}
        except Exception as exc:
            logger.exception("Tool %s failed", function_name)
            return {"error": f"{function_name} failed: {exc}"}

    async def disconnect(self, close_code):
        pass
