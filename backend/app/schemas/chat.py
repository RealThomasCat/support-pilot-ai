from pydantic import BaseModel

from app.schemas.message import MessageResponse


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse