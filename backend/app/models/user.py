"""User model for authentication and subscriptions."""

from sqlalchemy import Column, String, Boolean, JSON, DateTime
from app.models.base import BaseModel


class User(BaseModel):
    """User model — admin-created or self-service signup accounts."""
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="analyst")  # admin, analyst, viewer
    is_active = Column(Boolean, nullable=False, default=True)

    # Subscription fields
    company_name = Column(String(255), nullable=True)
    subscription_tier = Column(String(50), nullable=True, default=None)  # starter, pro, enterprise, admin
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(String(50), nullable=True, default=None)  # active, canceled, past_due, trialing

    # User-level investment preferences (hurdle metrics + MLA defaults)
    user_preferences = Column(JSON, nullable=True)

    # First-deal feedback lifecycle
    first_deal_at = Column(DateTime, nullable=True)
    feedback_email_sent_at = Column(DateTime, nullable=True)
