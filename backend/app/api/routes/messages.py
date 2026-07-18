from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.message import Message, MessageRole
from app.db.session import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.services.conversation_service import get_conversation
from app.services.message_service import create_message, list_messages

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["messages"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message_endpoint(
    conversation_id: int,
    payload: MessageCreate,
    db: DbSession,
) -> Message:
    conversation = get_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return create_message(
        db=db,
        conversation=conversation,
        role=MessageRole.USER,
        content=payload.content,
    )


@router.get(
    "",
    response_model=list[MessageResponse],
)
def list_messages_endpoint(
    conversation_id: int,
    db: DbSession,
) -> list[Message]:
    conversation = get_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return list_messages(
        db=db,
        conversation_id=conversation_id,
    )