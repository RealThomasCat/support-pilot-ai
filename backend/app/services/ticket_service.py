from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.db.models.ticket import Ticket
from app.schemas.ticket import (
    TicketCreate,
    TicketFilters,
    TicketUpdate,
)


# Custom exception for when a ticket is not found in the database.
class TicketNotFoundError(Exception):
    """
    Raised when a requested ticket does not exist.
    """

    # Constructor that takes the ticket ID,
    # store the ticket ID for reference and call the base class (Exception) constructor with a formatted message.
    def __init__(self, ticket_id: int) -> None:

        self.ticket_id = ticket_id
        super().__init__(f"Ticket with ID {ticket_id} was not found.")


def create_ticket(
    ticket_data: TicketCreate,
    db: Session,
) -> Ticket:
    """
    Create and persist a new ticket.
    """

    ticket = Ticket(
        customer_name=ticket_data.customer_name,
        customer_email=str(ticket_data.customer_email),
        subject=ticket_data.subject,
        description=ticket_data.description,
        priority=ticket_data.priority,
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return ticket


def build_ticket_list_statement(
    filters: TicketFilters,
) -> Select[tuple[Ticket]]:
    """
    Build the SQL query used to list and filter tickets.

    This function only builds the statement. It does not execute it.
    """

    # sqlalchemy.select is used to create a SQL SELECT statement for the Ticket model.
    statement = select(Ticket)

    if filters.status is not None:
        statement = statement.where(
            Ticket.status == filters.status,
        )

    if filters.category is not None:
        statement = statement.where(
            Ticket.category == filters.category,
        )

    if filters.priority is not None:
        statement = statement.where(
            Ticket.priority == filters.priority,
        )

    if filters.search is not None:
        search_pattern = f"%{filters.search}%"

        # Filter tickets where any of the specified fields contain the search term (case-insensitive).
        statement = statement.where(
            or_(
                Ticket.customer_name.ilike(search_pattern),
                Ticket.customer_email.ilike(search_pattern),
                Ticket.subject.ilike(search_pattern),
                Ticket.description.ilike(search_pattern),
            )
        )

    # Order the results by creation date, and then by ID.
    statement = statement.order_by(
        Ticket.created_at.desc(),
        Ticket.id.desc(),
    )

    # Limit the number of results returned to the specified limit.
    statement = statement.limit(filters.limit)

    return statement


def list_tickets(
    filters: TicketFilters,
    db: Session,
) -> list[Ticket]:
    """
    Return tickets matching the provided filters.
    """

    # Build the SQL statement based on the provided filters.
    statement = build_ticket_list_statement(filters)

    # Execute the statement and return the results as a list of Ticket objects.
    return list(db.scalars(statement).all())


def get_ticket(
    ticket_id: int,
    db: Session,
) -> Ticket:
    """
    Return one ticket or raise TicketNotFoundError.
    """

    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise TicketNotFoundError(ticket_id)

    return ticket


def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    db: Session,
) -> Ticket:
    """
    Partially update an existing ticket.
    """

    # Retrieve the ticket from the database.
    ticket = get_ticket(ticket_id, db)

    # Only update fields that were explicitly set in the update request. This prevents overwriting existing values with defaults or None.
    update_values = ticket_data.model_dump(
        exclude_unset=True,
    )

    # Update the ticket's attributes with the new values.
    for field_name, value in update_values.items():
        # If the customer_email is provided, convert it to a string before updating.
        # Handling email separately because Pydantic gives us an EmailStr object, but the database expects a string.
        if field_name == "customer_email" and value is not None:
            value = str(value)

        setattr(ticket, field_name, value)

    # NOTE: We don't need to call db.add(ticket) here because the ticket is already being tracked by the session.

    db.commit()
    db.refresh(ticket)

    return ticket