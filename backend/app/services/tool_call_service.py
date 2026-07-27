import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.tool_call import ToolCall
from app.services.tool_execution_service import ToolExecutionResult


logger = logging.getLogger(__name__)


class ToolCallLoggingError(RuntimeError):
    """
    Raised when a completed tool execution cannot be persisted.
    """


_REDACTED_VALUE = "[REDACTED]"

# These values are unnecessary or unsafe in execution logs.
_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "customer_email",
    "password",
    "secret",
    "token",
}


def _sanitize_log_data(
    value: Any,
) -> Any:
    """
    Recursively redact sensitive values before persistence.

    Tool arguments and results originate partly from model-generated
    data and must not be written blindly into the database.
    """
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}

        for key, nested_value in value.items():
            normalized_key = str(key).strip().lower()

            if normalized_key in _SENSITIVE_KEYS:
                sanitized[str(key)] = _REDACTED_VALUE
            else:
                sanitized[str(key)] = _sanitize_log_data(
                    nested_value
                )

        return sanitized

    if isinstance(value, list):
        return [
            _sanitize_log_data(item)
            for item in value
        ]

    return value


def create_tool_call_log(
    *,
    db: Session,
    conversation_id: int,
    message_id: int,
    execution: ToolExecutionResult,
) -> ToolCall:
    """
    Persist one completed tool-execution attempt.

    Every success and failure is stored using the same execution
    result contract produced by execute_tool().
    """
    # Pydantic converts nested enums and other supported values into JSON-compatible Python data.
    execution_data = execution.model_dump(
        mode="json",
    )

    tool_call = ToolCall(
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name=execution.tool_name,
        requested_arguments=_sanitize_log_data(
            execution_data["requested_arguments"]
        ),
        validated_arguments=_sanitize_log_data(
            execution_data["validated_arguments"]
        ),
        result=_sanitize_log_data(
            execution_data["result"]
        ),
        status=execution.status,
        validation_status=execution.validation_status,
        failure_type=execution.failure_type,
        error_message=execution.error_message,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
    )

    try:
        db.add(tool_call)
        db.commit()
        db.refresh(tool_call)
    except SQLAlchemyError as exc:
        db.rollback()

        logger.exception(
            "Failed to persist tool-call log for "
            "conversation_id=%s message_id=%s tool=%s",
            conversation_id,
            message_id,
            execution.tool_name,
        )

        raise ToolCallLoggingError(
            "The tool execution log could not be saved."
        ) from exc

    return tool_call


def list_tool_calls_for_conversation(
    *,
    db: Session,
    conversation_id: int,
) -> list[ToolCall]:
    """
    Return tool calls for one conversation in execution order.
    """
    statement = (
        select(ToolCall)
        .where(
            ToolCall.conversation_id == conversation_id,
        )
        .order_by(
            ToolCall.started_at.asc(),
            ToolCall.id.asc(),
        )
    )

    return list(db.scalars(statement).all())


def get_tool_call(
    *,
    db: Session,
    tool_call_id: int,
) -> ToolCall | None:
    """
    Return one tool-call log by ID.
    """
    return db.get(ToolCall, tool_call_id)