from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.models.message import Message, MessageRole
from app.services.errors import DatabaseWriteError


logger = logging.getLogger(__name__)


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

    try:
        db.add(message)
        db.commit()
        db.refresh(message)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "Failed to create %s message for conversation_id=%s.",
            role.value,
            conversation.id,
        )
        raise DatabaseWriteError(
            "The message could not be saved."
        ) from exc

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
