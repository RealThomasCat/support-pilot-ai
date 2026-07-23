from sqlalchemy.orm import Session

from app.db.models.ticket import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import create_ticket
from app.services.tool_execution_service import (
    ToolExecutionStatus,
    ToolFailureType,
    ToolValidationStatus,
    execute_tool,
)


def create_test_ticket(
    db: Session,
):
    """
    Create one predictable ticket for service tests.
    """
    return create_ticket(
        db=db,
        ticket_data=TicketCreate(
            customer_name="Aarav Sharma",
            customer_email="aarav@example.com",
            subject="Duplicate payment",
            description="The same payment appears twice.",
            priority=TicketPriority.HIGH,
        ),
    )


def test_execute_get_ticket_successfully(
    db_session: Session,
) -> None:
    ticket = create_test_ticket(db_session)

    execution = execute_tool(
        db=db_session,
        tool_name="get_ticket",
        raw_arguments={
            "ticket_id": ticket.id,
        },
    )

    assert execution.status == ToolExecutionStatus.SUCCESS
    assert (
        execution.validation_status
        == ToolValidationStatus.PASSED
    )
    assert execution.failure_type is None
    assert execution.error_message is None
    assert execution.validated_arguments == {
        "ticket_id": ticket.id,
    }

    assert isinstance(execution.result, dict)
    assert execution.result["id"] == ticket.id
    assert execution.result["subject"] == "Duplicate payment"


def test_execute_tool_rejects_unsupported_name(
    db_session: Session,
) -> None:
    execution = execute_tool(
        db=db_session,
        tool_name="delete_ticket",
        raw_arguments={
            "ticket_id": 1,
        },
    )

    assert execution.status == ToolExecutionStatus.FAILED
    assert (
        execution.validation_status
        == ToolValidationStatus.NOT_ATTEMPTED
    )
    assert (
        execution.failure_type
        == ToolFailureType.UNSUPPORTED_TOOL
    )
    assert execution.validated_arguments is None
    assert execution.result is None


def test_execute_tool_returns_validation_error(
    db_session: Session,
) -> None:
    execution = execute_tool(
        db=db_session,
        tool_name="update_ticket_status",
        raw_arguments={
            "ticket_id": 1,
            "status": "done",
        },
    )

    assert execution.status == ToolExecutionStatus.FAILED
    assert (
        execution.validation_status
        == ToolValidationStatus.FAILED
    )
    assert (
        execution.failure_type
        == ToolFailureType.VALIDATION_ERROR
    )
    assert execution.validated_arguments is None
    assert execution.result is None
    assert execution.error_message is not None
    assert "status" in execution.error_message


def test_execute_get_ticket_returns_not_found(
    db_session: Session,
) -> None:
    execution = execute_tool(
        db=db_session,
        tool_name="get_ticket",
        raw_arguments={
            "ticket_id": 999999,
        },
    )

    assert execution.status == ToolExecutionStatus.FAILED
    assert (
        execution.validation_status
        == ToolValidationStatus.PASSED
    )
    assert execution.failure_type == ToolFailureType.NOT_FOUND
    assert execution.validated_arguments == {
        "ticket_id": 999999,
    }
    assert execution.result is None
    assert execution.error_message is not None


def test_execute_update_ticket_status(
    db_session: Session,
) -> None:
    ticket = create_test_ticket(db_session)

    execution = execute_tool(
        db=db_session,
        tool_name="update_ticket_status",
        raw_arguments={
            "ticket_id": ticket.id,
            "status": TicketStatus.RESOLVED.value,
        },
    )

    assert execution.status == ToolExecutionStatus.SUCCESS
    assert isinstance(execution.result, dict)
    assert (
        execution.result["status"]
        == TicketStatus.RESOLVED.value
    )

    db_session.refresh(ticket)

    assert ticket.status == TicketStatus.RESOLVED


def test_execute_update_ticket_classification(
    db_session: Session,
) -> None:
    ticket = create_test_ticket(db_session)

    execution = execute_tool(
        db=db_session,
        tool_name="update_ticket_classification",
        raw_arguments={
            "ticket_id": ticket.id,
            "category": TicketCategory.BILLING.value,
            "priority": TicketPriority.URGENT.value,
        },
    )

    assert execution.status == ToolExecutionStatus.SUCCESS
    assert isinstance(execution.result, dict)
    assert (
        execution.result["category"]
        == TicketCategory.BILLING.value
    )
    assert (
        execution.result["priority"]
        == TicketPriority.URGENT.value
    )

    db_session.refresh(ticket)

    assert ticket.category == TicketCategory.BILLING
    assert ticket.priority == TicketPriority.URGENT


def test_classification_requires_category_or_priority(
    db_session: Session,
) -> None:
    execution = execute_tool(
        db=db_session,
        tool_name="update_ticket_classification",
        raw_arguments={
            "ticket_id": 1,
        },
    )

    assert execution.status == ToolExecutionStatus.FAILED
    assert (
        execution.failure_type
        == ToolFailureType.VALIDATION_ERROR
    )
    assert execution.result is None