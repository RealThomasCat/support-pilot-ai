from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.models.message import Message, MessageRole
from app.db.models.tool_call import ToolCall
from app.tools.types import (
    ToolExecutionStatus,
    ToolFailureType,
    ToolValidationStatus,
)


def create_conversation_and_message(
    db: Session,
) -> tuple[Conversation, Message]:
    conversation = Conversation(
        title="Tool-call inspection",
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Inspect ticket 15.",
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return conversation, message


def create_tool_call(
    *,
    db: Session,
    conversation_id: int,
    message_id: int,
    tool_name: str,
    started_at: datetime,
    status: ToolExecutionStatus = ToolExecutionStatus.SUCCESS,
    failure_type: ToolFailureType | None = None,
) -> ToolCall:
    tool_call = ToolCall(
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name=tool_name,
        requested_arguments={
            "ticket_id": 15,
        },
        validated_arguments={
            "ticket_id": 15,
        },
        result=(
            {
                "id": 15,
                "subject": "Duplicate payment",
            }
            if status == ToolExecutionStatus.SUCCESS
            else None
        ),
        status=status,
        validation_status=ToolValidationStatus.PASSED,
        failure_type=failure_type,
        error_message=(
            None
            if failure_type is None
            else "Ticket with ID 15 was not found."
        ),
        started_at=started_at,
        completed_at=started_at + timedelta(milliseconds=10),
    )

    db.add(tool_call)
    db.commit()
    db.refresh(tool_call)

    return tool_call


def test_list_tool_calls_for_conversation_in_execution_order(
    client: TestClient,
    db_session: Session,
) -> None:
    conversation, message = create_conversation_and_message(
        db_session
    )

    base_time = datetime.now(timezone.utc)

    second_tool_call = create_tool_call(
        db=db_session,
        conversation_id=conversation.id,
        message_id=message.id,
        tool_name="get_ticket",
        started_at=base_time + timedelta(seconds=1),
    )

    first_tool_call = create_tool_call(
        db=db_session,
        conversation_id=conversation.id,
        message_id=message.id,
        tool_name="list_tickets",
        started_at=base_time,
    )

    response = client.get(
        f"/conversations/{conversation.id}/tool-calls",
    )

    assert response.status_code == 200

    tool_calls = response.json()

    assert len(tool_calls) == 2

    assert [tool_call["id"] for tool_call in tool_calls] == [
        first_tool_call.id,
        second_tool_call.id,
    ]

    assert [tool_call["tool_name"] for tool_call in tool_calls] == [
        "list_tickets",
        "get_ticket",
    ]


def test_existing_conversation_without_tool_calls_returns_empty_list(
    client: TestClient,
    db_session: Session,
) -> None:
    conversation = Conversation(
        title="No tool calls",
    )

    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    response = client.get(
        f"/conversations/{conversation.id}/tool-calls",
    )

    assert response.status_code == 200
    assert response.json() == []


def test_missing_conversation_tool_calls_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/conversations/999999/tool-calls",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Conversation not found"
    }


def test_get_tool_call_by_id(
    client: TestClient,
    db_session: Session,
) -> None:
    conversation, message = create_conversation_and_message(
        db_session
    )

    started_at = datetime.now(timezone.utc)

    tool_call = create_tool_call(
        db=db_session,
        conversation_id=conversation.id,
        message_id=message.id,
        tool_name="get_ticket",
        started_at=started_at,
    )

    response = client.get(
        f"/tool-calls/{tool_call.id}",
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["id"] == tool_call.id
    assert response_data["conversation_id"] == conversation.id
    assert response_data["message_id"] == message.id
    assert response_data["tool_name"] == "get_ticket"
    assert response_data["requested_arguments"] == {
        "ticket_id": 15,
    }
    assert response_data["validated_arguments"] == {
        "ticket_id": 15,
    }
    assert response_data["status"] == "success"
    assert response_data["validation_status"] == "passed"
    assert response_data["failure_type"] is None
    assert response_data["error_message"] is None
    assert response_data["started_at"] is not None
    assert response_data["completed_at"] is not None


def test_get_failed_tool_call_by_id(
    client: TestClient,
    db_session: Session,
) -> None:
    conversation, message = create_conversation_and_message(
        db_session
    )

    tool_call = create_tool_call(
        db=db_session,
        conversation_id=conversation.id,
        message_id=message.id,
        tool_name="get_ticket",
        started_at=datetime.now(timezone.utc),
        status=ToolExecutionStatus.FAILED,
        failure_type=ToolFailureType.NOT_FOUND,
    )

    response = client.get(
        f"/tool-calls/{tool_call.id}",
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["status"] == "failed"
    assert response_data["result"] is None
    assert response_data["failure_type"] == "not_found"
    assert response_data["error_message"] == (
        "Ticket with ID 15 was not found."
    )


def test_get_missing_tool_call_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/tool-calls/999999",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Tool call not found"
    }