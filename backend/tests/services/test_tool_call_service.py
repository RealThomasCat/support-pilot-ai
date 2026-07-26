from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.models.message import Message, MessageRole
from app.services.tool_call_service import create_tool_call_log
from app.services.tool_execution_service import ToolExecutionResult
from app.tools.types import (
    ToolExecutionStatus,
    ToolFailureType,
    ToolValidationStatus,
)


def create_conversation_and_message(
    db: Session,
) -> tuple[Conversation, Message]:
    conversation = Conversation(
        title="Tool logging test",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Get ticket 7.",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return conversation, message


def test_create_successful_tool_call_log(
    db_session: Session,
) -> None:
    conversation, message = create_conversation_and_message(
        db_session
    )

    started_at = datetime.now(timezone.utc)
    completed_at = datetime.now(timezone.utc)

    execution = ToolExecutionResult(
        tool_name="get_ticket",
        requested_arguments={
            "ticket_id": 7,
        },
        validated_arguments={
            "ticket_id": 7,
        },
        status=ToolExecutionStatus.SUCCESS,
        validation_status=ToolValidationStatus.PASSED,
        result={
            "id": 7,
            "customer_email": "customer@example.com",
            "subject": "Duplicate payment",
        },
        failure_type=None,
        error_message=None,
        started_at=started_at,
        completed_at=completed_at,
    )

    tool_call = create_tool_call_log(
        db=db_session,
        conversation_id=conversation.id,
        message_id=message.id,
        execution=execution,
    )

    assert tool_call.id is not None
    assert tool_call.conversation_id == conversation.id
    assert tool_call.message_id == message.id
    assert tool_call.tool_name == "get_ticket"
    assert tool_call.status == ToolExecutionStatus.SUCCESS
    assert tool_call.requested_arguments == {
        "ticket_id": 7,
    }
    assert tool_call.validated_arguments == {
        "ticket_id": 7,
    }
    assert tool_call.result == {
        "id": 7,
        "customer_email": "[REDACTED]",
        "subject": "Duplicate payment",
    }
    assert tool_call.failure_type is None
    assert tool_call.error_message is None
    assert tool_call.started_at == started_at
    assert tool_call.completed_at == completed_at


def test_create_failed_tool_call_log(
    db_session: Session,
) -> None:
    conversation, message = create_conversation_and_message(
        db_session
    )

    execution = ToolExecutionResult(
        tool_name="update_ticket_status",
        requested_arguments={
            "ticket_id": 7,
            "status": "done",
        },
        validated_arguments=None,
        status=ToolExecutionStatus.FAILED,
        validation_status=ToolValidationStatus.FAILED,
        result=None,
        failure_type=ToolFailureType.VALIDATION_ERROR,
        error_message="status: Input should be valid.",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )

    tool_call = create_tool_call_log(
        db=db_session,
        conversation_id=conversation.id,
        message_id=message.id,
        execution=execution,
    )

    assert tool_call.status == ToolExecutionStatus.FAILED
    assert (
        tool_call.validation_status
        == ToolValidationStatus.FAILED
    )
    assert (
        tool_call.failure_type
        == ToolFailureType.VALIDATION_ERROR
    )
    assert tool_call.validated_arguments is None
    assert tool_call.result is None
    assert tool_call.error_message == (
        "status: Input should be valid."
    )


def test_tool_call_log_redacts_nested_sensitive_values(
    db_session: Session,
) -> None:
    conversation, message = create_conversation_and_message(
        db_session
    )

    execution = ToolExecutionResult(
        tool_name="create_ticket",
        requested_arguments={
            "customer_email": "customer@example.com",
            "description": "Payment problem",
            "metadata": {
                "token": "secret-token",
            },
        },
        validated_arguments={
            "customer_email": "customer@example.com",
            "description": "Payment problem",
        },
        status=ToolExecutionStatus.SUCCESS,
        validation_status=ToolValidationStatus.PASSED,
        result={
            "id": 10,
            "customer_email": "customer@example.com",
        },
        failure_type=None,
        error_message=None,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )

    tool_call = create_tool_call_log(
        db=db_session,
        conversation_id=conversation.id,
        message_id=message.id,
        execution=execution,
    )

    assert tool_call.requested_arguments == {
        "customer_email": "[REDACTED]",
        "description": "Payment problem",
        "metadata": {
            "token": "[REDACTED]",
        },
    }

    assert tool_call.validated_arguments == {
        "customer_email": "[REDACTED]",
        "description": "Payment problem",
    }

    assert tool_call.result == {
        "id": 10,
        "customer_email": "[REDACTED]",
    }