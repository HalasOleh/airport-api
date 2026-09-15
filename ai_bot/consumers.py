"""WebSocket chat consumer.

The consumer owns three things: the socket, the conversation history, and the
tool-calling loop. It owns no domain knowledge - which tool answers a question,
and with what arguments, is decided by the model and executed by
ai_bot.tools.call_tool. There is no keyword matching over the user's text here.
"""
import json
import logging
import os

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI

from ai_bot.models import ChatDialog, ChatMessage
from ai_bot.prompt import build_system_prompt
from ai_bot.tools import TOOL_SCHEMAS, call_tool, gemini_tools

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# The model may need several passes: look up an airport code, then search
# flights with it, then read the seat map. The ceiling is what stops a model
# that keeps calling the same tool from looping forever.
MAX_TOOL_ROUNDS = 5

# Rough cap on how much conversation goes back to the model. Trimming is done by
# trim_history(), which will not cut a tool result away from its tool call.
MAX_HISTORY_MESSAGES = 40


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


def parse_tool_arguments(raw):
    """Tool arguments arrive as a JSON string the model wrote. Returns None if
    it is not a usable object, which the caller reports back as a tool error."""
    try:
        arguments = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return None
    return arguments if isinstance(arguments, dict) else None


def trim_history(messages, limit=MAX_HISTORY_MESSAGES):
    """Drop the oldest turns, keeping tool calls and their results together.

    A naive "last N messages" cut can leave a tool result whose assistant
    message with the matching tool_call id was trimmed away. The API rejects
    that outright, so the window is advanced to the next user message, which is
    always a safe boundary.
    """
    if len(messages) <= limit:
        return messages

    system, rest = messages[:1], messages[1:]
    window = rest[-(limit - 1):]

    start = 0
    while start < len(window) and window[start].get("role") != "user":
        start += 1

    if start == len(window):
        # The whole window is one long tool exchange. Cutting anywhere inside it
        # would orphan something, so leave the history alone this round.
        return messages

    return system + window[start:]


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
        # Built per connection, not at import: it carries today's date, and a  module-level constant would freeze whichever day the worker booted on.
        self.system_prompt = build_system_prompt()
        self.messages = [{"role": "system", "content": self.system_prompt}]

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
            reply_text = await self.generate_reply()
        except Exception:
            # An upstream/model failure should surface as an error frame, not
            # kill the socket and lose the conversation.
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

    async def generate_reply(self):
        if self.provider == "gemini":
            return await self.generate_reply_gemini()
        return await self.generate_reply_openai()

    async def run_tool_call(self, name, raw_arguments):
        """Execute one tool call and return its result dict.

        call_tool is synchronous and touches the ORM, files and HTTP, so it goes
        to a worker thread - on the event loop it would stall every other
        WebSocket connection on this worker.

        self.user comes from the authenticated scope and is passed positionally.
        The model never supplies it: no tool schema declares a user parameter.
        """
        arguments = parse_tool_arguments(raw_arguments)
        if arguments is None:
            logger.warning("Tool %s: unreadable arguments %r", name, raw_arguments)
            return {"error": f"Could not read the arguments for {name} as JSON."}

        logger.info("Tool call %s(%s)", name, arguments)
        return await database_sync_to_async(call_tool)(name, arguments, self.user)

    async def generate_reply_openai(self):
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        for _ in range(MAX_TOOL_ROUNDS):
            self.messages = trim_history(self.messages)
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=self.messages,
                # Passed on every round, not just the first: without it the model
                # cannot act on what a tool just returned.
                tools=TOOL_SCHEMAS,
            )

            message = response.choices[0].message
            # Normalised to a plain dict so the history stays JSON-serialisable
            # and uniform with the messages loaded from the database.
            self.messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                return message.content

            # A single response can ask for several tools at once. Each gets its
            # own result message carrying its own tool_call_id.
            for tool_call in message.tool_calls:
                result = await self.run_tool_call(
                    tool_call.function.name, tool_call.function.arguments
                )
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        # Out of rounds. Ask once more without tools so the model has to produce
        # an answer instead of reaching for another call.
        logger.warning("Tool loop hit %s rounds; forcing a text answer", MAX_TOOL_ROUNDS)
        self.messages = trim_history(self.messages)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=self.messages,
        )
        message = response.choices[0].message
        self.messages.append(message.model_dump(exclude_none=True))
        return message.content

    def gemini_contents(self):

        contents = []
        for message in self.messages:
            role = message.get("role")
            content = message.get("content")
            if role not in ("user", "assistant") or not content:
                continue
            contents.append(
                genai_types.Content(
                    role="user" if role == "user" else "model",
                    parts=[genai_types.Part.from_text(text=content)],
                )
            )
        return contents

    async def generate_reply_gemini(self):
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        config = genai_types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            tools=[genai_types.Tool(function_declarations=gemini_tools())],
            # The declarations are plain schemas, not Python callables, so the
            # SDK must not try to invoke anything itself.
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        contents = self.gemini_contents()

        for _ in range(MAX_TOOL_ROUNDS):
            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            candidate = response.candidates[0] if response.candidates else None
            if candidate is None or candidate.content is None:
                return response.text

            contents.append(candidate.content)

            function_calls = response.function_calls or []
            if not function_calls:
                reply_text = response.text
                self.messages.append({"role": "assistant", "content": reply_text})
                return reply_text

            parts = []
            for function_call in function_calls:
                logger.info("Tool call %s(%s)", function_call.name, function_call.args)
                result = await database_sync_to_async(call_tool)(
                    function_call.name, dict(function_call.args or {}), self.user
                )
                parts.append(
                    genai_types.Part.from_function_response(
                        name=function_call.name, response=result
                    )
                )
            contents.append(genai_types.Content(role="user", parts=parts))

        logger.warning("Gemini tool loop hit %s rounds; forcing a text answer", MAX_TOOL_ROUNDS)
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(system_instruction=self.system_prompt),
        )
        reply_text = response.text
        self.messages.append({"role": "assistant", "content": reply_text})
        return reply_text

    async def disconnect(self, close_code):
        pass
