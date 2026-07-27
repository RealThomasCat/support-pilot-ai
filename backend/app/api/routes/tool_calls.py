from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.tool_call import ToolCall
from app.db.session import get_db
from app.schemas.tool_call import ToolCallResponse
from app.services.conversation_service import get_conversation
from app.services.tool_call_service import (
    get_tool_call,
    list_tool_calls_for_conversation,
)


router = APIRouter(
    tags=["tool calls"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/conversations/{conversation_id}/tool-calls",
    response_model=list[ToolCallResponse],
)
def list_conversation_tool_calls_endpoint(
    conversation_id: int,
    db: DbSession,
) -> list[ToolCall]:
    conversation = get_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return list_tool_calls_for_conversation(
        db=db,
        conversation_id=conversation_id,
    )


@router.get(
    "/tool-calls/{tool_call_id}",
    response_model=ToolCallResponse,
)
def get_tool_call_endpoint(
    tool_call_id: int,
    db: DbSession,
) -> ToolCall:
    tool_call = get_tool_call(
        db=db,
        tool_call_id=tool_call_id,
    )

    if tool_call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool call not found",
        )

    return tool_call