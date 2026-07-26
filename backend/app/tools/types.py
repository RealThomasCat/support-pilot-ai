from enum import StrEnum


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