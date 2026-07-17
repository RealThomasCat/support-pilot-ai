from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.models.ticket import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
)


class TicketBase(BaseModel):
    """
    Fields shared by ticket creation and ticket responses.
    """

    customer_name: str = Field(min_length=1, max_length=120)
    customer_email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)


class TicketCreate(TicketBase):
    """
    Input accepted when creating a ticket.

    Status and category are not supplied during normal creation.
    New tickets start as open and unclassified.
    """

    priority: TicketPriority = TicketPriority.MEDIUM


class TicketUpdate(BaseModel):
    """
    Input accepted when partially updating a ticket.

    Every field is optional because PATCH should update only
    the fields supplied by the caller.
    """

    customer_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )
    customer_email: EmailStr | None = None
    subject: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    description: str | None = Field(
        default=None,
        min_length=1,
    )
    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None

    # Apply field validator to the following fields: customer_name, subject, description.
    @field_validator(
        "customer_name",
        "subject",
        "description",
        mode="before", # Run this function before Pydantic performs its normal type and field validation.
    )
    @classmethod
    def reject_blank_strings(cls, value: object) -> object:
        # If the value is a string and becomes empty after removing surrounding whitespace, reject it.
        if isinstance(value, str) and not value.strip():
            raise ValueError("Value must not be blank.")

        # Else return the value unchanged. This validator only checks the value. It does not change it.
        # A Pydantic validator must return the value that should continue through validation.
        return value


class TicketResponse(TicketBase):
    """
    Ticket data returned by the API.
    """

    # By default, Pydantic models only accept data that is passed in as a dictionary or keyword arguments.
    # But the service returns a SQLAlchemy object.
    # So from_attributes=True allows Pydantic to accept data from an object with attributes, like a SQLAlchemy model.
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TicketStatus
    category: TicketCategory
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime


class TicketFilters(BaseModel):
    """
    Optional filters accepted by the ticket-list service.
    """

    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    search: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
    )

    # Apply a field validator to the optional search field.
    @field_validator("search", mode="before")
    @classmethod
    def normalize_search(cls, value: object) -> object:
        if isinstance(value, str):
            stripped_value = value.strip()

            # If the stripped value is empty, return None to indicate that no search filter should be applied.
            if not stripped_value:
                return None

            return stripped_value

        return value