from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models.ticket import (
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.db.session import get_db
from app.schemas.ticket import (
    TicketCreate,
    TicketFilters,
    TicketResponse,
    TicketUpdate,
)
from app.services.ticket_service import (
    TicketNotFoundError,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket,
)


router = APIRouter(
    prefix="/tickets",
    tags=["tickets"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


# Create ticket endpoint.
@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket_endpoint(
    ticket_data: TicketCreate,
    db: DatabaseSession,
) -> Ticket:
    return create_ticket(
        ticket_data=ticket_data,
        db=db,
    )


# List tickets endpoint with filtering and pagination.
@router.get(
    "",
    response_model=list[TicketResponse],
)
def list_tickets_endpoint(
    db: DatabaseSession,
    ticket_status: Annotated[
        TicketStatus | None,
        Query(alias="status"),
    ] = None,
    category: TicketCategory | None = None,
    priority: TicketPriority | None = None,
    search: Annotated[
        str | None,
        Query(min_length=1, max_length=200),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
) -> list[Ticket]:
    filters = TicketFilters(
        status=ticket_status,
        category=category,
        priority=priority,
        search=search,
        limit=limit,
    )

    return list_tickets(
        filters=filters,
        db=db,
    )


# Get ticket by ID endpoint.
@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
)
def get_ticket_endpoint(
    ticket_id: int,
    db: DatabaseSession,
) -> Ticket:
    try:
        return get_ticket(
            ticket_id=ticket_id,
            db=db,
        )
    except TicketNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


# Update ticket endpoint.
@router.patch(
    "/{ticket_id}",
    response_model=TicketResponse,
)
def update_ticket_endpoint(
    ticket_id: int,
    ticket_data: TicketUpdate,
    db: DatabaseSession,
) -> Ticket:
    try:
        return update_ticket(
            ticket_id=ticket_id,
            ticket_data=ticket_data,
            db=db,
        )
    except TicketNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error