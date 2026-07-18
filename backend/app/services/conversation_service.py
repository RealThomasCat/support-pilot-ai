from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation


def create_conversation(
    *,
    db: Session,
    title: str,
) -> Conversation:
    conversation = Conversation(title=title)

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

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