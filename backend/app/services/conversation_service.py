import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.services.errors import DatabaseWriteError


logger = logging.getLogger(__name__)


def create_conversation(
    *,
    db: Session,
    title: str,
) -> Conversation:
    conversation = Conversation(title=title)

    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to create conversation.")
        raise DatabaseWriteError(
            "The conversation could not be saved."
        ) from exc

    return conversation


def list_conversations(
    *,
    db: Session,
) -> list[Conversation]:
    statement = select(Conversation).order_by(
        Conversation.created_at.desc(),
        Conversation.id.desc(),
    )

    return list(db.scalars(statement).all())


def get_conversation(
    *,
    db: Session,
    conversation_id: int,
) -> Conversation | None:
    return db.get(Conversation, conversation_id)
