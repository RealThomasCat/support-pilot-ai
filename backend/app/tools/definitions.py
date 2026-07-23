from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.db.models.ticket import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
)

# We define separate argument schemas instead of reusing API schemas such as TicketCreate, TicketFilters,
# or TicketUpdate because the API contract and the tool contract are related but not identical.
#
# Tool-specific schemas (for example, UpdateTicketStatusArguments) limit the LLM's authority by exposing only
# the fields that a tool is allowed to modify, instead of accepting a broader schema like TicketUpdate.
#
# These schemas also serve as the tool's documentation.
# Their field descriptions are included in the JSON Schema provided to Gemini.

class ListTicketsArguments(BaseModel):
    """
    Arguments accepted by the list_tickets tool.
    """

    status: TicketStatus | None = Field(
        default=None,
        description="Filter tickets by their current status.",
    )
    category: TicketCategory | None = Field(
        default=None,
        description="Filter tickets by their support category.",
    )
    priority: TicketPriority | None = Field(
        default=None,
        description="Filter tickets by priority.",
    )
    search: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Case-insensitive search across customer name, customer email, "
            "ticket subject, and ticket description."
        ),
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of tickets to return.",
    )

    @field_validator("search", mode="before")
    @classmethod
    def normalize_search(cls, value: object) -> object:
        """
        Remove surrounding whitespace from search text.

        Treat an empty or whitespace-only search value as no search filter.
        """
        if isinstance(value, str):
            stripped_value = value.strip()

            if not stripped_value:
                return None

            return stripped_value

        return value


class GetTicketArguments(BaseModel):
    """
    Arguments accepted by the get_ticket tool.
    """

    ticket_id: int = Field(
        ge=1,
        description="Database ID of the ticket to retrieve.",
    )


class CreateTicketArguments(BaseModel):
    """
    Arguments accepted by the create_ticket tool.
    """

    customer_name: str = Field(
        min_length=1,
        max_length=120,
        description="Full name of the customer reporting the issue.",
    )
    customer_email: EmailStr = Field(
        description="Valid email address of the customer.",
    )
    subject: str = Field(
        min_length=1,
        max_length=200,
        description="Short title summarizing the support issue.",
    )
    description: str = Field(
        min_length=1,
        description="Detailed description of the support issue.",
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        description="Priority of the new ticket.",
    )

    @field_validator(
        "customer_name",
        "subject",
        "description",
        mode="before",
    )
    @classmethod
    def reject_blank_strings(cls, value: object) -> object:
        """
        Reject strings containing only whitespace.
        """
        if isinstance(value, str) and not value.strip():
            raise ValueError("Value must not be blank.")

        return value


class UpdateTicketStatusArguments(BaseModel):
    """
    Arguments accepted by the update_ticket_status tool.
    """

    ticket_id: int = Field(
        ge=1,
        description="Database ID of the ticket to update.",
    )
    status: TicketStatus = Field(
        description="New status to assign to the ticket.",
    )


class UpdateTicketClassificationArguments(BaseModel):
    """
    Arguments accepted by the update_ticket_classification tool.

    At least one of category or priority must be provided.
    """

    ticket_id: int = Field(
        ge=1,
        description="Database ID of the ticket to classify.",
    )
    category: TicketCategory | None = Field(
        default=None,
        description="Support category to assign to the ticket.",
    )
    priority: TicketPriority | None = Field(
        default=None,
        description="Priority to assign to the ticket.",
    )

    @model_validator(mode="after")
    def require_classification_value(
        self,
    ) -> "UpdateTicketClassificationArguments":
        """
        Require at least one classification field.
        """
        if self.category is None and self.priority is None:
            raise ValueError(
                "At least one of category or priority must be provided."
            )

        return self