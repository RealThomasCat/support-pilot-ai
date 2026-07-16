from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"


class TicketCategory(StrEnum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"
    UNKNOWN = "unknown"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# Function which takes an enum class and returns a list of its string values.
# We need this because SQLAlchemy's Enum type by default stores the enum member names (e.g., "OPEN") in the database,
# but we want to store the enum values (e.g., "open") instead.
def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """
    Tell SQLAlchemy to store enum values such as "open",
    rather than Python member names such as "OPEN".
    """
    return [member.value for member in enum_class]


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)

    customer_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    customer_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            native_enum=False, # Store enum values as strings in the database.
            values_callable=enum_values, # Use the enum_values function to get the string values of the enum members.
            length=30,
        ),
        nullable=False,
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
    )

    category: Mapped[TicketCategory] = mapped_column(
        Enum(
            TicketCategory,
            native_enum=False,
            values_callable=enum_values,
            length=30,
        ),
        nullable=False,
        default=TicketCategory.UNKNOWN,
        server_default=TicketCategory.UNKNOWN.value,
    )

    priority: Mapped[TicketPriority] = mapped_column(
        Enum(
            TicketPriority,
            native_enum=False,
            values_callable=enum_values,
            length=20,
        ),
        nullable=False,
        default=TicketPriority.MEDIUM,
        server_default=TicketPriority.MEDIUM.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )