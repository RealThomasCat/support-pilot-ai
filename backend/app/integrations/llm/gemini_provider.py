from collections.abc import Sequence

from google import genai
from google.genai import types, errors

from app.core.config import settings
from app.db.models.message import Message, MessageRole


SYSTEM_INSTRUCTION = """
You are SupportPilot AI, an internal copilot for customer-support agents.

You are speaking to a support agent, not directly to a customer.

Respond clearly, concisely, and professionally.

You do not currently have access to ticket tools or the ticket database.
Do not claim that you inspected, created, classified, or updated a ticket
unless that information was explicitly provided in the conversation.

Do not claim that a customer reply was saved or sent.
""".strip()


class GeminiProviderError(RuntimeError):
    """Base exception for failures inside the Gemini integration."""


class GeminiConfigurationError(GeminiProviderError):
    """Raised when Gemini configuration is missing or invalid."""


class GeminiRequestError(GeminiProviderError):
    """Raised when a request to Gemini cannot be completed."""


class GeminiResponseError(GeminiProviderError):
    """Raised when Gemini returns no usable assistant text."""


def _get_api_key() -> str:
    """
    Return the configured Gemini API key.

    The key is retrieved only when Gemini is called, so database commands,
    health checks, and deterministic tests can run without Gemini credentials.
    """
    if settings.gemini_api_key is None:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured."
        )

    api_key = settings.gemini_api_key.get_secret_value().strip()

    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is empty."
        )

    return api_key


# Helper function to convert SupportPilot messages into Gemini content objects
def _to_gemini_contents(
    messages: Sequence[Message],
) -> list[types.Content]:
    """
    Convert persisted SupportPilot messages into Gemini content objects.

    SupportPilot role:
        user       -> Gemini role: user
        assistant  -> Gemini role: model
    """
    contents: list[types.Content] = []

    for message in messages:
        # Convert SupportPilot message role to Gemini role.
        gemini_role = (
            "user"
            if message.role == MessageRole.USER
            else "model"
        )

        # Create a Gemini content object with the message text.
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[
                    types.Part.from_text(
                        text=message.content,
                    )
                ],
            )
        )

    # Return the list of Gemini content objects.
    return contents


# Public function to generate an assistant response using Gemini.
def generate_assistant_response(
    *,
    messages: Sequence[Message],
) -> str:
    """
    Send ordered conversation history to Gemini and return assistant text.

    This function does not:
    - query the database;
    - save messages;
    - execute ticket tools;
    - handle FastAPI responses.
    """
    if not messages:
        raise GeminiProviderError(
            "At least one conversation message is required."
        )

    api_key = _get_api_key()
    contents = _to_gemini_contents(messages)

    try:
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                ),
            )
    except errors.APIError as exc:
        raise GeminiRequestError(
            "Gemini request failed."
        ) from exc
    except (TimeoutError, ConnectionError, OSError) as exc:
        raise GeminiRequestError(
            "Gemini could not be reached."
        ) from exc

    response_text = response.text

    if response_text is None or not response_text.strip():
        raise GeminiResponseError(
            "Gemini returned an empty response."
        )

    return response_text.strip()