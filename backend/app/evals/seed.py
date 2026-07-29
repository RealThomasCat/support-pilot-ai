from sqlalchemy.orm import Session

from app.db.models.ticket import (
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)


OPEN_BILLING_TICKET_ID = 101
RESOLVED_TECHNICAL_TICKET_ID = 102
OPEN_ACCOUNT_TICKET_ID = 103


def seed_eval_tickets(
    *,
    db: Session,
) -> list[Ticket]:
    """
    Insert a small, fixed ticket dataset.

    Explicit IDs make prompts and expected state checks predictable.
    """
    tickets = [
        Ticket(
            id=OPEN_BILLING_TICKET_ID,
            customer_name="Aarav Mehta",
            customer_email="aarav.eval@example.com",
            subject="Duplicate card charge",
            description=(
                "The customer was charged twice for the same order."
            ),
            status=TicketStatus.OPEN,
            category=TicketCategory.BILLING,
            priority=TicketPriority.HIGH,
        ),
        Ticket(
            id=RESOLVED_TECHNICAL_TICKET_ID,
            customer_name="Diya Rao",
            customer_email="diya.eval@example.com",
            subject="Application login error",
            description=(
                "The customer could not log in after resetting "
                "their password."
            ),
            status=TicketStatus.RESOLVED,
            category=TicketCategory.TECHNICAL,
            priority=TicketPriority.MEDIUM,
        ),
        Ticket(
            id=OPEN_ACCOUNT_TICKET_ID,
            customer_name="Kabir Shah",
            customer_email="kabir.eval@example.com",
            subject="Change registered phone number",
            description=(
                "The customer wants to replace the phone number "
                "registered on the account."
            ),
            status=TicketStatus.OPEN,
            category=TicketCategory.ACCOUNT,
            priority=TicketPriority.LOW,
        ),
    ]

    db.add_all(tickets)
    db.commit()

    for ticket in tickets:
        db.refresh(ticket)

    return tickets