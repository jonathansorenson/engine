from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ChatMessageCreate(BaseModel):
    """Request schema for creating a chat message."""
    message: str


class ChatMessageResponse(BaseModel):
    """Response schema for a chat message."""
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
