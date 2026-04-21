"""Feedback model — first-deal (and admin-triggered) feedback submissions."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime
from app.models.base import BaseModel


class Feedback(BaseModel):
    """User feedback captured after their first deal (or admin-prompted)."""
    __tablename__ = "feedback"

    # fund_id comes from BaseModel with index=True — no explicit Index needed here.
    deal_id = Column(String(36), nullable=True, index=True)
    nps = Column(Integer, nullable=True)
    wishlist = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
