from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
)
from app.services.conversation_service import (
    create_conversation,
    get_conversation,
    list_conversations,
)

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_endpoint(
    payload: ConversationCreate,
    db: DbSession,
) -> Conversation:
    return create_conversation(
        db=db,
        title=payload.title,
    )


@router.get(
    "",
    response_model=list[ConversationResponse],
)
def list_conversations_endpoint(
    db: DbSession,
) -> list[Conversation]:
    return list_conversations(db=db)


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation_endpoint(
    conversation_id: int,
    db: DbSession,
) -> Conversation:
    conversation = get_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation