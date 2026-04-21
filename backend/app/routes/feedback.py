"""Feedback routes — user submission + admin review + admin manual resend."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel as PydanticBaseModel, Field
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deal, Feedback, User
from app.services.email import send_first_deal_feedback_email

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback"])

MAX_WISHLIST_CHARS = 4000


# ── Schemas ──

class FeedbackCreate(PydanticBaseModel):
    nps: Optional[int] = Field(default=None, ge=0, le=10)
    wishlist: Optional[str] = None
    deal_id: Optional[str] = None


class FeedbackResponse(PydanticBaseModel):
    id: str
    fund_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    deal_id: Optional[str] = None
    deal_name: Optional[str] = None
    nps: Optional[int] = None
    wishlist: Optional[str] = None
    submitted_at: datetime

    class Config:
        from_attributes = True


class ManualSendResponse(PydanticBaseModel):
    sent: bool
    to: str


class FeedbackAnalytics(PydanticBaseModel):
    total_responses: int
    responses_last_7d: int
    responses_last_30d: int
    nps_respondents: int
    avg_nps: Optional[float] = None
    promoters: int
    passives: int
    detractors: int
    nps_score: Optional[float] = None  # classic NPS: %promoters - %detractors
    users_with_first_deal: int
    emails_sent: int
    unique_responders: int
    response_rate_pct: Optional[float] = None
    wishlist_count: int


# ── User-facing route ──

@router.post("/api/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submit feedback about the first-deal experience."""
    fund_id = getattr(request.state, "fund_id", None)
    user_email = getattr(request.state, "user_email", None)
    if not fund_id or not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    if payload.nps is None and not (payload.wishlist or "").strip():
        raise HTTPException(status_code=400, detail="Provide an NPS score or wishlist note.")

    wishlist = (payload.wishlist or "").strip()
    if len(wishlist) > MAX_WISHLIST_CHARS:
        raise HTTPException(status_code=400, detail=f"Wishlist too long (max {MAX_WISHLIST_CHARS} chars).")

    # Only accept deal_id if it belongs to this fund
    deal_id = None
    if payload.deal_id:
        deal = db.query(Deal).filter(Deal.id == payload.deal_id, Deal.fund_id == fund_id).first()
        if deal:
            deal_id = deal.id

    feedback = Feedback(
        fund_id=fund_id,
        deal_id=deal_id,
        nps=payload.nps,
        wishlist=wishlist or None,
        submitted_at=datetime.utcnow(),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    user = db.query(User).filter(User.email == user_email).first()
    deal_name = None
    if deal_id:
        d = db.query(Deal).filter(Deal.id == deal_id).first()
        deal_name = d.name if d else None

    return FeedbackResponse(
        id=feedback.id,
        fund_id=feedback.fund_id,
        user_email=user.email if user else user_email,
        user_name=user.name if user else None,
        deal_id=feedback.deal_id,
        deal_name=deal_name,
        nps=feedback.nps,
        wishlist=feedback.wishlist,
        submitted_at=feedback.submitted_at,
    )


# ── Admin routes (gated by middleware — path contains /api/v1/admin) ──

@router.get("/api/v1/admin/feedback", response_model=List[FeedbackResponse])
async def list_feedback(
    request: Request,
    db: Session = Depends(get_db),
    min_nps: Optional[int] = None,
    max_nps: Optional[int] = None,
):
    """List all feedback submissions (admin only)."""
    query = db.query(Feedback).order_by(Feedback.submitted_at.desc())
    if min_nps is not None:
        query = query.filter(Feedback.nps >= min_nps)
    if max_nps is not None:
        query = query.filter(Feedback.nps <= max_nps)
    rows = query.all()

    # Batch-load referenced users and deals to avoid N+1
    fund_ids = {r.fund_id for r in rows if r.fund_id}
    deal_ids = {r.deal_id for r in rows if r.deal_id}

    users_by_email = {
        u.email: u
        for u in (db.query(User).filter(User.email.in_(fund_ids)).all() if fund_ids else [])
    }
    deals_by_id = {
        d.id: d
        for d in (db.query(Deal).filter(Deal.id.in_(deal_ids)).all() if deal_ids else [])
    }

    result = []
    for r in rows:
        user = users_by_email.get(r.fund_id)
        deal = deals_by_id.get(r.deal_id) if r.deal_id else None
        result.append(FeedbackResponse(
            id=r.id,
            fund_id=r.fund_id,
            user_email=user.email if user else r.fund_id,
            user_name=user.name if user else None,
            deal_id=r.deal_id,
            deal_name=deal.name if deal else None,
            nps=r.nps,
            wishlist=r.wishlist,
            submitted_at=r.submitted_at,
        ))
    return result


@router.get("/api/v1/admin/feedback/analytics", response_model=FeedbackAnalytics)
async def feedback_analytics(
    request: Request,
    db: Session = Depends(get_db),
):
    """Aggregate NPS + response-rate metrics for the admin dashboard."""
    now = datetime.utcnow()
    window_7d = now - timedelta(days=7)
    window_30d = now - timedelta(days=30)

    rows = db.query(Feedback).all()
    total = len(rows)

    nps_rows = [r for r in rows if r.nps is not None]
    nps_count = len(nps_rows)
    avg_nps = round(sum(r.nps for r in nps_rows) / nps_count, 2) if nps_count else None

    promoters = sum(1 for r in nps_rows if r.nps >= 9)
    passives = sum(1 for r in nps_rows if 7 <= r.nps <= 8)
    detractors = sum(1 for r in nps_rows if r.nps <= 6)
    nps_score = round((promoters - detractors) / nps_count * 100, 1) if nps_count else None

    responses_7d = sum(1 for r in rows if r.submitted_at and r.submitted_at >= window_7d)
    responses_30d = sum(1 for r in rows if r.submitted_at and r.submitted_at >= window_30d)

    users_first_deal = db.query(func.count(User.id)).filter(User.first_deal_at.isnot(None)).scalar() or 0
    emails_sent = db.query(func.count(User.id)).filter(User.feedback_email_sent_at.isnot(None)).scalar() or 0
    unique_responders = db.query(func.count(distinct(Feedback.fund_id))).scalar() or 0
    response_rate = round(unique_responders / emails_sent * 100, 1) if emails_sent else None

    wishlist_count = sum(1 for r in rows if (r.wishlist or "").strip())

    return FeedbackAnalytics(
        total_responses=total,
        responses_last_7d=responses_7d,
        responses_last_30d=responses_30d,
        nps_respondents=nps_count,
        avg_nps=avg_nps,
        promoters=promoters,
        passives=passives,
        detractors=detractors,
        nps_score=nps_score,
        users_with_first_deal=users_first_deal,
        emails_sent=emails_sent,
        unique_responders=unique_responders,
        response_rate_pct=response_rate,
        wishlist_count=wishlist_count,
    )


@router.post("/api/v1/admin/feedback/send/{user_id}", response_model=ManualSendResponse)
async def admin_send_feedback_email(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Admin-triggered manual send of the feedback email to a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use their most recent parsed deal for personalization, if any
    recent_deal = (
        db.query(Deal)
        .filter(Deal.fund_id == user.email, Deal.status == "parsed")
        .order_by(Deal.created_at.desc())
        .first()
    )

    sent = send_first_deal_feedback_email(user, recent_deal)
    user.feedback_email_sent_at = datetime.utcnow()
    if user.first_deal_at is None and recent_deal is not None:
        user.first_deal_at = recent_deal.created_at
    db.commit()

    return ManualSendResponse(sent=bool(sent), to=user.email)
