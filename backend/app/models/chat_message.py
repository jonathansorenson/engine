from sqlalchemy import Column, String, Text, Integer
from app.models.base import BaseModel


class ChatMessage(BaseModel):
    """Chat message model for deal discussions."""
    __tablename__ = "chat_messages"

    # deal_id and fund_id are already indexed (via index=True here and on BaseModel).
    deal_id = Column(String(36), nullable=False, index=True)  # UUID as string for FK
    role = Column(String(50), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=True)
