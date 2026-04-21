"""Feedback model — first-deal (and admin-triggered) feedback submissions."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from app.models.base import BaseModel


class Feedback(BaseModel):
    """User feedback captured after their first deal (or admin-prompted)."""
    __tablename__ = "feedback"

    deal_id = Column(String(36), nullable=True, index=True)  # deal the feedback is about (nullable)
    nps = Column(Integer, nullable=True)  # 0–10
    wishlist = Column(Text, nullable=True)  # free-text
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_feedback_fund_id", "fund_id"),
        Index("ix_feedback_submitted_at", "submitted_at"),
    )
