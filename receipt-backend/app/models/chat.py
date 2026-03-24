from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class ChatMessageRequest(BaseModel):
    session_id: Optional[UUID] = None
    message: str


class ChatSession(BaseModel):
    session_id: UUID
    last_message: Optional[str] = None
    messages_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionsResponse(BaseModel):
    sessions: list[ChatSession]
