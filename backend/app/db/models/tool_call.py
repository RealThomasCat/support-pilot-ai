from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.tools.types import (
    ToolExecutionStatus,
    ToolFailureType,
    ToolValidationStatus,
)

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.message import Message



class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True)

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    requested_arguments: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    validated_arguments: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    result: Mapped[dict[str, Any] | list[dict[str, Any]] | None] = (
        mapped_column(
            JSONB,
            nullable=True,
        )
    )

    status: Mapped[ToolExecutionStatus] = mapped_column(
        Enum(
            ToolExecutionStatus,
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
            length=20,
        ),
        nullable=False,
    )

    validation_status: Mapped[ToolValidationStatus] = mapped_column(
        Enum(
            ToolValidationStatus,
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
            length=20,
        ),
        nullable=False,
    )

    failure_type: Mapped[ToolFailureType | None] = mapped_column(
        Enum(
            ToolFailureType,
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
            length=30,
        ),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="tool_calls",
    )

    message: Mapped["Message"] = relationship(
        back_populates="tool_calls",
    )