from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.genai import types
from pydantic import BaseModel

from app.tools.definitions import (
    CreateTicketArguments,
    GetTicketArguments,
    ListTicketsArguments,
    UpdateTicketClassificationArguments,
    UpdateTicketStatusArguments,
)
from app.tools.ticket_tools import (
    create_ticket_tool,
    get_ticket_tool,
    list_tickets_tool,
    update_ticket_classification_tool,
    update_ticket_status_tool,
)


ToolHandler = Callable[..., dict[str, Any] | list[dict[str, Any]]]


# dataclass to create a tool object.
# frozen=True ensures that a registered tool definition is fixed after application startup.
@dataclass(frozen=True)
class ToolRegistration:
    """
    Complete backend registration for one allowed tool.

    argument_model:
        Pydantic model used to validate model-generated arguments.

    handler:
        Python function allowed to execute the tool.

    description:
        Instructions that help Gemini decide when to use the tool.
    """

    name: str # Tool name that gemini will request
    description: str # Tool description for gemini
    argument_model: type[BaseModel] # Pydantic model class to validate arguments - from definitions.py
    handler: ToolHandler # Executable python function permited to execute the tool - ticket_tools.py

    # Method to converts the internal registration into the format Gemini needs.
    # Gemini only needs name, description and argument JSON schema.
    def to_function_declaration(
        self,
    ) -> types.FunctionDeclaration:
        """
        Convert this registration into a Gemini function declaration.
        """
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self.argument_model.model_json_schema(),
        )


# Dictionary containing every allowed tool.
# We need a string to tool object mapping because Gemini returns the tool name as a string.
TOOL_REGISTRY: dict[str, ToolRegistration] = {
    "list_tickets": ToolRegistration(
        name="list_tickets",
        description=(
            "Search, filter, or review multiple support tickets. "
            "Use this when the support agent wants to find tickets but "
            "does not already have one specific ticket ID."
        ),
        argument_model=ListTicketsArguments,
        handler=list_tickets_tool,
    ),
    "get_ticket": ToolRegistration(
        name="get_ticket",
        description=(
            "Retrieve complete information for one support ticket by its "
            "database ID. Use this when the support agent refers to a "
            "specific known ticket ID."
        ),
        argument_model=GetTicketArguments,
        handler=get_ticket_tool,
    ),
    "create_ticket": ToolRegistration(
        name="create_ticket",
        description=(
            "Create a new customer-support ticket. Use this only when the "
            "support agent clearly asks to create or open a new ticket and "
            "provides the required customer and issue information."
        ),
        argument_model=CreateTicketArguments,
        handler=create_ticket_tool,
    ),
    "update_ticket_status": ToolRegistration(
        name="update_ticket_status",
        description=(
            "Update the status of one existing support ticket. Use this only "
            "when the support agent clearly requests a status change for a "
            "specific ticket."
        ),
        argument_model=UpdateTicketStatusArguments,
        handler=update_ticket_status_tool,
    ),
    "update_ticket_classification": ToolRegistration(
        name="update_ticket_classification",
        description=(
            "Persist a category, priority, or both for an existing support "
            "ticket. Use this only when the support agent clearly asks to "
            "classify or reclassify a specific ticket."
        ),
        argument_model=UpdateTicketClassificationArguments,
        handler=update_ticket_classification_tool,
    ),
}


# Helper function for looking up a tool by name.
def get_tool_registration(
    tool_name: str,
) -> ToolRegistration | None:
    """
    Return the registered tool matching the exact name.

    Return None when the tool is unsupported.
    """
    return TOOL_REGISTRY.get(tool_name)


# Gemini needs to know all available tools. This function builds the collection of tool declarations.
# Gemini’s SDK expects function declarations grouped inside a Tool object.
def get_gemini_tool() -> types.Tool:
    """
    Build the Gemini tool containing all allowed function declarations.
    """
    declarations = [
        registration.to_function_declaration()
        for registration in TOOL_REGISTRY.values()
    ]

    return types.Tool(
        function_declarations=declarations,
    )