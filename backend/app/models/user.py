"""User model for authentication."""

from sqlalchemy import Column, String, Boolean
from app.models.base import BaseModel


class User(BaseModel):
    """User model — admin-created accounts."""
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="analyst")  # admin, analyst, viewer
    is_active = Column(Boolean, nullable=False, default=True)
