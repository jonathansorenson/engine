from sqlalchemy import Column, String, Text, Integer, Index
from app.models.base import BaseModel


class ChatMessage(BaseModel):
    """Chat message model for deal discussions."""
    __tablename__ = "chat_messages"

    deal_id = Column(String(36), nullable=False, index=True)  # UUID as string for FK
    role = Column(String(50), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=True)

    # Index for common queries
    __table_args__ = (
        Index("ix_chat_deal_id", "deal_id"),
        Index("ix_chat_fund_id", "fund_id"),
    )
