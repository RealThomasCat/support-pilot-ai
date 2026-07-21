from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.message import Message
from app.db.session import get_db
from app.schemas.chat import ChatResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.services.chat_service import send_chat_message
from app.services.conversation_service import get_conversation
from app.services.message_service import list_messages


router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["messages"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message_endpoint(
    conversation_id: int,
    payload: MessageCreate,
    db: DbSession,
) -> ChatResponse:
    conversation = get_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Use the chat service to persist the user message, generate a Gemini response, and persist the assistant message.
    result = send_chat_message(
        db=db,
        conversation=conversation,
        content=payload.content,
    )

    # Return a ChatResponse containing the persisted user and assistant messages.
    return ChatResponse(
        # result.user_message and result.assistant_message are SQLAlchemy model objects,
        # so we use Pydantic's model_validate to convert them into Pydantic models for the response.
        user_message=MessageResponse.model_validate(
            result.user_message,
        ),
        assistant_message=MessageResponse.model_validate(
            result.assistant_message,
        ),
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