import logging
from dataclasses import dataclass, field
from typing import Any

from google.genai import types
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message, MessageRole
from app.integrations.llm.gemini_provider import (
    GeminiProviderError,
    GeminiResponseError,
    create_function_response_part,
    generate_model_turn,
    to_gemini_contents,
)
from app.services.message_service import create_message, list_messages
from app.services.tool_execution_service import (
    ToolExecutionResult,
    execute_tool,
)
from app.tools.types import ToolExecutionStatus


logger = logging.getLogger(__name__)


# This class represents one chat result, with user message, final assistant message and tools executed.
@dataclass
class ChatResult:
    user_message: Message
    assistant_message: Message

    # In memory.
    tool_executions: list[ToolExecutionResult] = field(
        default_factory=list,
    )


# Helper function to convert application result into simple success/error dictionary.
# Used to create response_data of function_response_part.
# Gemini normally only needs: successful output or failure type and message.
# The detailed fields in ToolExecutionResult remain available for logs.
def _build_function_response_data(
    execution: ToolExecutionResult,
) -> dict[str, Any]:
    """
    Convert one backend execution result into Gemini-readable data.
    """
    if execution.status == ToolExecutionStatus.SUCCESS:
        return {
            "output": execution.result,
        }

    return {
        "error": {
            "type": (
                execution.failure_type.value
                if execution.failure_type is not None
                else "unknown_error"
            ),
            "message": (
                execution.error_message
                or "The tool execution failed."
            ),
        }
    }


# Main Gemini turn loop function.
# It returns: 1. Final assistant text, 2. Every tool execution attempted during the loop
def _generate_tool_aware_response(
    *,
    db: Session,
    history: list[Message],
) -> tuple[str, list[ToolExecutionResult]]:
    """
    Run Gemini until it returns final text or reaches the round limit.
    """
    # Collect every attempted tool execution from this chat request.
    contents = to_gemini_contents(history)
    # List to store tool execution results.
    executions: list[ToolExecutionResult] = []

    # Allow Gemini a limited number of turns to request and observe tools.
    for _round_number in range(
        1,
        settings.gemini_max_tool_rounds + 1,
    ):
        # Send the complete in-memory conversation to Gemini once.
        # The returned turn contains either function calls or final text.
        turn = generate_model_turn(
            contents=contents,
        )

        # If no function calls are requested by gemini in current turn.
        if not turn.function_calls:
            # Defensive check: a turn without function calls must contain final text.
            if turn.text is None:
                raise GeminiResponseError(
                    "Gemini returned no final assistant text."
                )

            # Return the text, which is the final response of this chat, loop ends.
            return turn.text, executions

        # Preserve Gemini's complete model turn, including its function calls.
        # The next request must include both the original function call and the matching function response.
        contents.append(turn.content)

        # Collect one Gemini function-response part for every tool call requested in this model turn.
        # All responses from this turn will be returned together in one role="tool" Content object.
        function_response_parts: list[types.Part] = []

        # Validate and execute every function call requested in this Gemini turn.
        for function_call in turn.function_calls:
            # A tool cannot be looked up in the registry without its name.
            if not function_call.name:
                raise GeminiResponseError(
                    "Gemini returned a function call without a name."
                )

            # Convert Gemini's optional arguments into a normal dictionary.
            # Missing arguments become {}, allowing Pydantic to report required fields.
            raw_arguments = dict(
                function_call.args or {}
            )

            # Look up the allowed tool, validate its raw arguments, execute its registered handler, and return a structured result.
            execution = execute_tool(
                db=db,
                tool_name=function_call.name,
                raw_arguments=raw_arguments,
            )

            # Add the tool execution result to executions.
            executions.append(execution)

            # Convert the tool execution result into a Gemini function-response Part.
            # The call ID lets Gemini match this response to the corresponding function call.
            # All response Parts from this model turn are later grouped into one role="tool" Content object.
            function_response_parts.append(
                create_function_response_part(
                    function_call_id=function_call.id,
                    function_name=function_call.name,
                    response_data=_build_function_response_data(
                        execution
                    ),
                )
            )

        # Return all function results from this Gemini turn together.
        # These contents are sent back to Gemini in the next loop iteration.
        contents.append(
            types.Content(
                role="tool",
                parts=function_response_parts,
            )
        )

    # If the function fails to end the loop and return text response, then raise error.
    raise GeminiResponseError(
        "Gemini exceeded the maximum number of tool-call rounds."
    )


# Main send message function.
def send_chat_message(
    *,
    db: Session,
    conversation: Conversation,
    content: str,
) -> ChatResult:
    """
    Persist a user message, execute the bounded Gemini/tool loop,
    and persist the final assistant message.

    If Gemini fails after the user message is saved, the user message
    remains and no assistant message is created.
    """
    user_message = create_message(
        db=db,
        conversation=conversation,
        role=MessageRole.USER,
        content=content,
    )

    history = list_messages(
        db=db,
        conversation_id=conversation.id,
    )

    # Execute Gemini/tool loop.
    try:
        assistant_content, tool_executions = (
            _generate_tool_aware_response(
                db=db,
                history=history,
            )
        )
    except GeminiProviderError:
        logger.exception(
            "Gemini response generation failed for conversation_id=%s "
            "user_message_id=%s",
            conversation.id,
            user_message.id,
        )
        raise

    assistant_message = create_message(
        db=db,
        conversation=conversation,
        role=MessageRole.ASSISTANT,
        content=assistant_content,
    )

    return ChatResult(
        user_message=user_message,
        assistant_message=assistant_message,
        tool_executions=tool_executions,
    )