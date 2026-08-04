import json
import os
from datetime import datetime

import requests
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from google import genai
from openai import OpenAI, AsyncOpenAI

from .models import Flight


def load_documents():
    docs = []
    docs_folder = "airports/knowledge_base"

    try:
        if not os.path.exists(docs_folder):
            print(f"Warning: {docs_folder} does not exist")
            return docs

        for filename in os.listdir(docs_folder):
            if filename.endswith('.txt'):
                try:
                    with open(os.path.join(docs_folder, filename), 'r', encoding='utf-8') as f:
                        content = f.read()
                        docs.append({
                            'filename': filename,
                            'content': content
                        })
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

        print(f"Loaded {len(docs)} documents")
    except Exception as e:
        print(f"Error loading documents: {e}")

    return docs


def search_documents(documents, query): # Improved keyword search with scoring
    query_lower = query.lower()
    query_words = [word for word in query_lower.split() if len(word) > 2]  # Ignore short words

    if not query_words:
        return ""

    scored_docs = []

    for doc in documents:
        content_lower = doc['content'].lower()
        score = 0

        # Count words in the document
        for word in query_words:
            if word in content_lower:
                # Give higher score if word appears multiple times
                score += content_lower.count(word)

        if score > 0:
            scored_docs.append((score, doc))

    # Sort by score (highest first) and take top 2 most relevant
    scored_docs.sort(reverse=True, key=lambda x: x[0])
    relevant = [doc['content'] for score, doc in scored_docs[:2]]

    return "\n\n".join(relevant) if relevant else ""

PHONE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_phone_number",
        "description": "Get the phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "airport": {
                    "type": "string",
                    "description": "Airport name, for example Heathrow, JFK, Boryspil.",
                }
            },
            "required": ["airport"],
            "additionalProperties": False,
        },
    },
}

PARKING_TOOL = {
    "type": "function",
    "function": {
        "name": "get_place",
        "description": "Get the parking place for a given airport.",
        "parameters": {
            "type": "object",
            "properties": {
                "airport": {
                    "type": "string",
                    "description": "Airport name, for example Heathrow, JFK, Boryspil.",
                }
            },
            "required": ["airport"],
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


def get_place(airport: str) -> dict:
    parking_file = os.path.join("airports", "knowledge_base", "parking_info.txt")
    try:
        with open(parking_file, "r", encoding="utf-8") as f:
            parking_text = f.read()
    except FileNotFoundError:
        return {
            "airport": airport,
            "place": "Parking information file not found",
            "condition": "unknown",
        }
    except Exception as exc:
        return {
            "airport": airport,
            "place": f"Error reading parking info: {exc}",
            "condition": "unknown",
        }

    airport_query = (airport or "").strip().lower()
    for block in [block.strip() for block in parking_text.split("\n\n") if block.strip()]:
        if airport_query and airport_query in block.lower():
            return {
                "airport": airport,
                "place": block,
                "condition": "available",
                "source": "airports/knowledge_base/parking_info.txt",
            }

    return {
        "airport": airport,
        "place": "No parking information found for this airport",
        "condition": "unknown",
        "source": "airports/knowledge_base/parking_info.txt",
    }

def get_phone_number(user_message: str) -> dict:
    try:
        with open("airports/knowledge_base/phone_numbers.txt", "r", encoding="utf-8") as f:
            phone_data = json.load(f)
    except FileNotFoundError:
        Response = {f"message": user_message, "phone_number": "Phone numbers file not found", "condition": "unknown"}
        return Response
    message_lower = user_message.lower()
    for department, info in phone_data.items():
        if department.lower() in message_lower:
            return {
                "department": department,
                "contact_data": info,
                "condition": "available",
            }
    return {"message": user_message, "phone_number": "No phone number found for this department", "condition": "unknown"}

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
        

FUNCTIONS = {
    "get_place": get_place,
    "get_weather": get_weather,
    "get_flight_status": get_flight_status,
    "get_phone_number": get_phone_number,
}


class TestConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        self.provider = None
        self.documents = load_documents()
        # conversation memory lives here, for the life of this connection

        self.messages = [
            {
                "role": "system",
                "content": (
                    "You are an airport assistant. "
                    "Use available tools and document context to answer user questions. "
                    "Available tools: "
                    "- get_place: parking locations "
                    "- get_phone_number: phone numbers "
                    "- get_weather: current weather "
                    "- get_flight_status: flight information between airports"
                ),
            }
        ]


    async def receive(self, text_data):
        data = json.loads(text_data)

        if "provider" in data:
            chosen = data["provider"]
            if chosen not in ("gemini", "openai"):
                await self.send(text_data=json.dumps({"error": "Incorrect provider"}))
                self.provider = None
                return
            self.provider = chosen
            print(f"Client connected. Using {self.provider} as provider.")
            await self.send(text_data=json.dumps({"status": f"using {self.provider}"}))
            return

        user_message = data.get("message", "")
        self.messages.append({"role": "user", "content": user_message})

        if self.provider == "gemini":
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            response = await client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=user_message,
            )
            reply_text = response.text
            self.messages.append({"role": "assistant", "content": reply_text})

        elif self.provider == "openai":
            context = search_documents(self.documents, user_message)
            print(f"Context: {context}")
            self.messages[0]["content"] = f"""You are an airport assistant.

            Available information:
            {context}

            Use the tools when appropriate."""

            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            response = await client.chat.completions.create(
                model="gpt-5.4-nano",
                messages=self.messages,
                tools=[PARKING_TOOL, WEATHER_TOOL, FLIGHT_STATUS_TOOL],
            )

            message = response.choices[0].message
            reply_text = message.content
            self.messages.append(message)

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    function = FUNCTIONS.get(function_name)

                    print(f"Function: {function_name}")
                    print(f"Arguments: {function_args}")

                    if function:
                        # Check if function is async (like get_flight_status)
                        if function_name == "get_flight_status":
                            function_response = await function(**function_args)
                        else:
                            function_response = function(**function_args)
                    else:
                        function_response = {"error": f"unknown function {function_name}"}

                    print(f"Function result: {function_response}")

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

        else:
            await self.send(text_data=json.dumps({"error": "Incorrect provider"}))
            self.provider = None
            return

        await self.send(text_data=json.dumps({
            "reply": reply_text,
        }))

    async def disconnect(self, close_code):
        pass
