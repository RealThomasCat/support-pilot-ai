from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.models.message import Message, MessageRole
from app.integrations.llm.gemini_provider import (
    generate_assistant_response,
)
from app.services.message_service import create_message, list_messages


@dataclass
class ChatResult:
    user_message: Message
    assistant_message: Message


def send_chat_message(
    *,
    db: Session,
    conversation: Conversation,
    content: str,
) -> ChatResult:
    """
    Persist a user message, generate a Gemini response, and persist
    the assistant message.

    If Gemini fails after the user message is saved, the user message
    remains in the conversation and no assistant message is created.
    """
    user_message = create_message(
        db=db,
        conversation=conversation,
        role=MessageRole.USER,
        content=content,
    )

    history = list_messages(
        db=db,
        conversation_id=conversation.id,
    )

    assistant_content = generate_assistant_response(
        messages=history,
    )

    assistant_message = create_message(
        db=db,
        conversation=conversation,
        role=MessageRole.ASSISTANT,
        content=assistant_content,
    )

    return ChatResult(
        user_message=user_message,
        assistant_message=assistant_message,
    )