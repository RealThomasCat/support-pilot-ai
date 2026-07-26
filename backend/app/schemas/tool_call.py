from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.tools.types import (
    ToolExecutionStatus,
    ToolFailureType,
    ToolValidationStatus,
)

class ToolCallResponse(BaseModel):
    id: int
    conversation_id: int
    message_id: int
    tool_name: str
    requested_arguments: dict[str, Any]
    validated_arguments: dict[str, Any] | None
    result: dict[str, Any] | list[dict[str, Any]] | None
    status: ToolExecutionStatus
    validation_status: ToolValidationStatus
    failure_type: ToolFailureType | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )