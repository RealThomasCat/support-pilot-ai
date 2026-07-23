from typing import Any

from sqlalchemy.orm import Session

from app.schemas.ticket import (
    TicketCreate,
    TicketFilters,
    TicketResponse,
    TicketUpdate,
)
from app.services import ticket_service
from app.tools.definitions import (
    CreateTicketArguments,
    GetTicketArguments,
    ListTicketsArguments,
    UpdateTicketClassificationArguments,
    UpdateTicketStatusArguments,
)


ToolResult = dict[str, Any] | list[dict[str, Any]]


# All ticket tools return the same JSON representation.
# This helper centralizes serialization so every tool produces a consistent response format.
def serialize_ticket(ticket: object) -> dict[str, Any]:
    """
    Convert a SQLAlchemy Ticket object into JSON-compatible data.
    """
    return (
        TicketResponse.model_validate(ticket)
        .model_dump(mode="json")
    )


# Tool adapters that bridge the LLM-facing tool layer and the service layer.
# They convert tool arguments into service schemas, call the appropriate service function, and serialize the returned models.


def list_tickets_tool(
    *,
    db: Session,
    arguments: ListTicketsArguments,
) -> list[dict[str, Any]]:
    """
    Execute the list_tickets capability through ticket_service.
    """
    filters = TicketFilters(
        status=arguments.status,
        category=arguments.category,
        priority=arguments.priority,
        search=arguments.search,
        limit=arguments.limit,
    )

    tickets = ticket_service.list_tickets(
        filters=filters,
        db=db,
    )

    return [
        serialize_ticket(ticket)
        for ticket in tickets
    ]


def get_ticket_tool(
    *,
    db: Session,
    arguments: GetTicketArguments,
) -> dict[str, Any]:
    """
    Execute the get_ticket capability through ticket_service.
    """
    ticket = ticket_service.get_ticket(
        ticket_id=arguments.ticket_id,
        db=db,
    )

    return serialize_ticket(ticket)


def create_ticket_tool(
    *,
    db: Session,
    arguments: CreateTicketArguments,
) -> dict[str, Any]:
    """
    Execute the create_ticket capability through ticket_service.
    """
    ticket_data = TicketCreate(
        customer_name=arguments.customer_name,
        customer_email=arguments.customer_email,
        subject=arguments.subject,
        description=arguments.description,
        priority=arguments.priority,
    )

    ticket = ticket_service.create_ticket(
        ticket_data=ticket_data,
        db=db,
    )

    return serialize_ticket(ticket)


def update_ticket_status_tool(
    *,
    db: Session,
    arguments: UpdateTicketStatusArguments,
) -> dict[str, Any]:
    """
    Update only the status of an existing ticket.
    """
    ticket_data = TicketUpdate(
        status=arguments.status,
    )

    ticket = ticket_service.update_ticket(
        ticket_id=arguments.ticket_id,
        ticket_data=ticket_data,
        db=db,
    )

    return serialize_ticket(ticket)


def update_ticket_classification_tool(
    *,
    db: Session,
    arguments: UpdateTicketClassificationArguments,
) -> dict[str, Any]:
    """
    Update the category, priority, or both for an existing ticket.
    """
    ticket_data = TicketUpdate(
        category=arguments.category,
        priority=arguments.priority,
    )

    ticket = ticket_service.update_ticket(
        ticket_id=arguments.ticket_id,
        ticket_data=ticket_data,
        db=db,
    )

    return serialize_ticket(ticket)