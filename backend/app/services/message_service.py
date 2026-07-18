from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.models.message import Message, MessageRole


def create_message(
    *,
    db: Session,
    conversation: Conversation,
    role: MessageRole,
    content: str,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
    )

    conversation.updated_at = datetime.now(timezone.utc)

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def list_messages(
    *,
    db: Session,
    conversation_id: int,
) -> list[Message]:
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(
            Message.created_at.asc(),
            Message.id.asc(),
        )
    )

    return list(db.scalars(statement).all())