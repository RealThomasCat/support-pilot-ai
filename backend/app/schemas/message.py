from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.message import MessageRole


class MessageCreate(BaseModel):
    content: str = Field(
        min_length=1,
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: MessageRole
    content: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )