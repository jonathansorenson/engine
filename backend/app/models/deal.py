from sqlalchemy import Column, String, JSON, Text, Index
from app.models.base import BaseModel


class Deal(BaseModel):
    """Deal model for CRE underwriting."""
    __tablename__ = "deals"

    name = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="uploading")  # uploading, parsing, parsed, error
    parsed_data = Column(JSON, nullable=True)  # Full parsed OM structure
    parsing_report = Column(JSON, nullable=True)  # warnings, errors, quality_score
    assumptions = Column(JSON, nullable=True)  # User-adjustable assumptions
    original_filename = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)

    # Index for common queries
    __table_args__ = (
        Index("ix_deal_fund_id", "fund_id"),
        Index("ix_deal_status", "status"),
    )
