from typing import Optional, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class DealAssumptionsUpdate(BaseModel):
    """Schema for updating deal assumptions."""
    exit_cap_rate: Optional[float] = None
    noi_growth: Optional[float] = None
    hold_period: Optional[int] = None
    ltv: Optional[float] = None
    interest_rate: Optional[float] = None
    amortization_years: Optional[int] = None


class DealListItem(BaseModel):
    """Minimal deal info for list endpoints."""
    id: str
    name: Optional[str] = None
    status: str
    property_type: Optional[str] = None
    asking_price: Optional[float] = None
    noi: Optional[float] = None
    cap_rate: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DealResponse(BaseModel):
    """Full deal response with all details."""
    id: str
    name: Optional[str] = None
    status: str
    parsed_data: Optional[dict] = None
    parsing_report: Optional[dict] = None
    assumptions: Optional[dict] = None
    original_filename: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
