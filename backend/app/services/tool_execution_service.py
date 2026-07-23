from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
import logging

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.ticket_service import TicketNotFoundError
from app.tools.registry import get_tool_registration


logger = logging.getLogger(__name__)


class ToolExecutionStatus(StrEnum):
    """
    Overall outcome of one attempted tool execution.
    """

    SUCCESS = "success"
    FAILED = "failed"


class ToolValidationStatus(StrEnum):
    """
    Outcome of argument validation.

    NOT_ATTEMPTED:
        Validation did not run because the tool name was unsupported.

    PASSED:
        Raw arguments were successfully converted into the registered
        Pydantic argument model.

    FAILED:
        Pydantic rejected the raw arguments.
    """

    NOT_ATTEMPTED = "not_attempted"
    PASSED = "passed"
    FAILED = "failed"


class ToolFailureType(StrEnum):
    """
    Known categories of tool-execution failure.
    """

    UNSUPPORTED_TOOL = "unsupported_tool"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    DATABASE_ERROR = "database_error"
    EXECUTION_ERROR = "execution_error"


# A structured and detailed result for every attempted tool call.
class ToolExecutionResult(BaseModel):
    """
    Structured outcome produced for every attempted tool call.

    This object is currently returned in memory. Phase 5 can persist
    its fields without redesigning the execution flow.
    """

    tool_name: str

    requested_arguments: dict[str, Any]
    validated_arguments: dict[str, Any] | None

    status: ToolExecutionStatus
    validation_status: ToolValidationStatus

    result: dict[str, Any] | list[dict[str, Any]] | None

    failure_type: ToolFailureType | None
    error_message: str | None

    started_at: datetime
    completed_at: datetime


def _utc_now() -> datetime:
    """
    Return the current timezone-aware UTC datetime.
    """
    return datetime.now(timezone.utc)


# Helper function to voncert Pydantic validation error into a concise message.
def _format_validation_error(
    error: ValidationError,
) -> str:
    """
    Convert a Pydantic ValidationError into a concise message.

    Avoid including Pydantic documentation URLs or large representations
    of the original input values.
    """
    messages: list[str] = []

    for error_detail in error.errors(
        include_url=False,
        include_input=False,
    ):
        location = ".".join(
            str(location_part)
            for location_part in error_detail["loc"]
        )

        message = error_detail["msg"]

        if location:
            messages.append(f"{location}: {message}")
        else:
            messages.append(message)

    return "; ".join(messages)


def execute_tool(
    *,
    db: Session,
    tool_name: str,
    raw_arguments: dict[str, Any],
) -> ToolExecutionResult:
    """
    Validate and execute one registered tool.

    The function always returns a ToolExecutionResult, including when:

    - the tool name is unsupported;
    - argument validation fails;
    - a requested ticket does not exist;
    - the database operation fails;
    - an unexpected handler failure occurs.

    The LLM never chooses the Python function directly. The function is
    obtained only from the controlled tool registry.
    """
    started_at = _utc_now()

    # Find the registered tool.
    registration = get_tool_registration(tool_name)

    # Handle unsupported tools.
    if registration is None:
        return ToolExecutionResult(
            tool_name=tool_name,
            requested_arguments=raw_arguments,
            validated_arguments=None,
            status=ToolExecutionStatus.FAILED,
            validation_status=ToolValidationStatus.NOT_ATTEMPTED,
            result=None,
            failure_type=ToolFailureType.UNSUPPORTED_TOOL,
            error_message=f"Unsupported tool: {tool_name}",
            started_at=started_at,
            completed_at=_utc_now(),
        )

    # Validate raw arguments using tool's argument model/schema.
    try:
        validated_model = registration.argument_model.model_validate(
            raw_arguments
        )
    # Handle validation error.
    except ValidationError as exc:
        return ToolExecutionResult(
            tool_name=tool_name,
            requested_arguments=raw_arguments,
            validated_arguments=None,
            status=ToolExecutionStatus.FAILED,
            validation_status=ToolValidationStatus.FAILED,
            result=None,
            failure_type=ToolFailureType.VALIDATION_ERROR,
            error_message=_format_validation_error(exc),
            started_at=started_at,
            completed_at=_utc_now(),
        )

    # Create JSON-compatible validated arguments.
    # That makes the data suitable for: logging, JSON database columns, Gemini function responses, API output, debugging.
    validated_arguments = validated_model.model_dump(
        mode="json",
    )

    # Execute the registered tool handler.
    try:
        result = registration.handler(
            db=db,
            arguments=validated_model,
        )
    # Handle ticket not found error.
    except TicketNotFoundError as exc:
        return ToolExecutionResult(
            tool_name=tool_name,
            requested_arguments=raw_arguments,
            validated_arguments=validated_arguments,
            status=ToolExecutionStatus.FAILED,
            validation_status=ToolValidationStatus.PASSED,
            result=None,
            failure_type=ToolFailureType.NOT_FOUND,
            error_message=str(exc),
            started_at=started_at,
            completed_at=_utc_now(),
        )
    # Handle database-level failures.
    except SQLAlchemyError:
        # NOTE: We are using rollback here because the request don't end and the session don't close after this function is executed.
        # The session remains open, it might be used further for retries or other tool calls.
        # So we rollback here because database transaction/session may have failed, so we need to the session before further usage.
        # The request will finaly end when the create_message_endpoint route finishes and the session will be closed.
        db.rollback()

        logger.exception(
            "Database failure while executing tool=%s",
            tool_name,
        )

        return ToolExecutionResult(
            tool_name=tool_name,
            requested_arguments=raw_arguments,
            validated_arguments=validated_arguments,
            status=ToolExecutionStatus.FAILED,
            validation_status=ToolValidationStatus.PASSED,
            result=None,
            failure_type=ToolFailureType.DATABASE_ERROR,
            error_message="The database operation failed.",
            started_at=started_at,
            completed_at=_utc_now(),
        )
    # Handle generic exception.
    except Exception:
        # We rollback here conservatively because handler progress is unknown.
        db.rollback()

        logger.exception(
            "Unexpected failure while executing tool=%s",
            tool_name,
        )

        return ToolExecutionResult(
            tool_name=tool_name,
            requested_arguments=raw_arguments,
            validated_arguments=validated_arguments,
            status=ToolExecutionStatus.FAILED,
            validation_status=ToolValidationStatus.PASSED,
            result=None,
            failure_type=ToolFailureType.EXECUTION_ERROR,
            error_message="The tool could not be executed.",
            started_at=started_at,
            completed_at=_utc_now(),
        )

    return ToolExecutionResult(
        tool_name=tool_name,
        requested_arguments=raw_arguments,
        validated_arguments=validated_arguments,
        status=ToolExecutionStatus.SUCCESS,
        validation_status=ToolValidationStatus.PASSED,
        result=result,
        failure_type=None,
        error_message=None,
        started_at=started_at,
        completed_at=_utc_now(),
    )