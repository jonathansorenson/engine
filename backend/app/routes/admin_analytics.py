"""Admin analytics endpoints — READ-ONLY aggregations over deals and users.

Hard constraint: this module MUST NOT contain db.add, db.delete, db.commit,
db.merge, db.flush, INSERT, UPDATE, or DELETE. CI enforces this via grep.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import func, text, case
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBaseModel

from app.config import settings
from app.database import get_db
from app.models.deal import Deal
from app.models.user import User
from app.routes.billing import (
    MONTHLY_LIMITS,
    get_monthly_limit,
    get_monthly_used,
)


router = APIRouter(prefix="/api/v1/admin/analytics", tags=["admin-analytics"])


# Static tier pricing in cents (monthly). NOT queried from Stripe — these are the
# list prices used to estimate MRR. Keep in sync with billing page copy.
TIER_PRICE_CENTS: Dict[str, int] = {
    "starter": 699,
    "pro": 1199,
    "unlimited": 2000,
    "enterprise": 0,
    "free": 0,
    "admin": 0,
}


def _require_admin(request: Request) -> None:
    """Belt-and-suspenders admin check on top of AuthMiddleware."""
    if getattr(request.state, "user_role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _set_read_only(db: Session) -> None:
    """Set the current Postgres transaction to read-only. No-op on SQLite."""
    if "postgresql" in settings.database_url:
        try:
            db.execute(text("SET TRANSACTION READ ONLY"))
        except Exception:
            pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_sqlite() -> bool:
    return "sqlite" in settings.database_url


# ═══════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS — explicit so we never leak hashed_password/stripe IDs/JSON
# ═══════════════════════════════════════════════════════════════════════════


class OverviewResponse(PydanticBaseModel):
    total_deals: int
    total_users: int
    active_users_30d: int
    deals_last_30d: int
    deals_last_7d: int
    parse_success_rate: float
    parse_error_count: int
    generated_at: str


class TimeSeriesPoint(PydanticBaseModel):
    date: str
    count: int
    success: int
    error: int


class TimeSeriesResponse(PydanticBaseModel):
    bucket: str
    days: int
    points: List[TimeSeriesPoint]


class TierBreakdownItem(PydanticBaseModel):
    tier: str
    user_count: int
    deal_count: int
    deals_last_30d: int
    mrr_cents: int


class TierBreakdownResponse(PydanticBaseModel):
    tiers: List[TierBreakdownItem]
    total_mrr_cents: int


class TopUserItem(PydanticBaseModel):
    email: str
    name: Optional[str]
    role: Optional[str]
    subscription_tier: Optional[str]
    subscription_status: Optional[str]
    total_deals: int
    deals_last_30d: int
    last_deal_at: Optional[str]
    monthly_limit: int
    monthly_used: int
    is_at_limit: bool


class TopUsersResponse(PydanticBaseModel):
    users: List[TopUserItem]


class StatusBreakdownResponse(PydanticBaseModel):
    total: int
    by_status: Dict[str, int]
    by_version: Dict[str, int]
    errors_last_7d: int


class RetentionCohort(PydanticBaseModel):
    cohort: str
    signups: int
    active_months: Dict[str, int]


class RetentionResponse(PydanticBaseModel):
    months: int
    cohorts: List[RetentionCohort]


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════


def _bucket_label(bucket: str):
    """Return a SQLAlchemy label expression producing a string bucket key.

    Output format per bucket:
      - day   → 'YYYY-MM-DD'
      - week  → 'YYYY-Www' (ISO week)
      - month → 'YYYY-MM'
    """
    if _is_sqlite():
        fmts = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m"}
        return func.strftime(fmts[bucket], Deal.created_at).label("bucket")
    # Postgres
    pg = {
        "day": ("day", "YYYY-MM-DD"),
        "week": ("week", 'IYYY-"W"IW'),
        "month": ("month", "YYYY-MM"),
    }
    trunc_unit, fmt = pg[bucket]
    return func.to_char(func.date_trunc(trunc_unit, Deal.created_at), fmt).label("bucket")


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS (all GET, all read-only)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(request: Request, db: Session = Depends(get_db)):
    """Headline KPIs for the dashboard top strip."""
    _require_admin(request)
    _set_read_only(db)

    now = _utcnow()
    cutoff_30d = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)

    total_deals = db.query(func.count(Deal.id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0

    active_users_30d = db.query(
        func.count(func.distinct(Deal.fund_id))
    ).filter(Deal.created_at >= cutoff_30d).scalar() or 0

    deals_last_30d = db.query(func.count(Deal.id)).filter(
        Deal.created_at >= cutoff_30d
    ).scalar() or 0

    deals_last_7d = db.query(func.count(Deal.id)).filter(
        Deal.created_at >= cutoff_7d
    ).scalar() or 0

    parsed_count = db.query(func.count(Deal.id)).filter(
        Deal.status == "parsed"
    ).scalar() or 0

    parse_error_count = db.query(func.count(Deal.id)).filter(
        Deal.status == "error"
    ).scalar() or 0

    parse_success_rate = (parsed_count / total_deals) if total_deals > 0 else 0.0

    return OverviewResponse(
        total_deals=total_deals,
        total_users=total_users,
        active_users_30d=active_users_30d,
        deals_last_30d=deals_last_30d,
        deals_last_7d=deals_last_7d,
        parse_success_rate=round(parse_success_rate, 4),
        parse_error_count=parse_error_count,
        generated_at=now.isoformat() + "Z",
    )


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    request: Request,
    bucket: str = Query("day", pattern="^(day|week|month)$"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Deal volume over time, grouped by day/week/month."""
    _require_admin(request)
    _set_read_only(db)

    cutoff = _utcnow() - timedelta(days=days)
    bucket_col = _bucket_label(bucket)

    rows = (
        db.query(
            bucket_col,
            func.count(Deal.id).label("count"),
            func.sum(case((Deal.status == "parsed", 1), else_=0)).label("success"),
            func.sum(case((Deal.status == "error", 1), else_=0)).label("error"),
        )
        .filter(Deal.created_at >= cutoff)
        .group_by(bucket_col)
        .order_by(bucket_col)
        .all()
    )

    points = [
        TimeSeriesPoint(
            date=str(r.bucket) if r.bucket is not None else "",
            count=int(r.count or 0),
            success=int(r.success or 0),
            error=int(r.error or 0),
        )
        for r in rows
    ]

    return TimeSeriesResponse(bucket=bucket, days=days, points=points)


@router.get("/by-tier", response_model=TierBreakdownResponse)
async def get_by_tier(request: Request, db: Session = Depends(get_db)):
    """Users and deals bucketed by subscription_tier. MRR uses static tier prices."""
    _require_admin(request)
    _set_read_only(db)

    now = _utcnow()
    cutoff_30d = now - timedelta(days=30)

    # Users per tier (all users, including inactive — for visibility)
    user_rows = (
        db.query(
            User.subscription_tier,
            User.subscription_status,
            func.count(User.id),
        )
        .group_by(User.subscription_tier, User.subscription_status)
        .all()
    )

    # Build per-tier aggregates
    tier_data: Dict[str, Dict[str, int]] = {}
    for tier, status, count in user_rows:
        key = tier or "unknown"
        bucket = tier_data.setdefault(key, {
            "user_count": 0,
            "active_user_count": 0,
            "deal_count": 0,
            "deals_last_30d": 0,
            "mrr_cents": 0,
        })
        bucket["user_count"] += int(count or 0)
        if status in ("active", "trialing"):
            bucket["active_user_count"] += int(count or 0)
            bucket["mrr_cents"] += int(count or 0) * TIER_PRICE_CENTS.get(key, 0)

    # Join deals to users to attribute per-tier. Left-join so deals from unknown
    # users (e.g. seed admin) still counted under 'admin' bucket fallback.
    deal_rows = (
        db.query(
            User.subscription_tier,
            func.count(Deal.id),
            func.sum(case((Deal.created_at >= cutoff_30d, 1), else_=0)),
        )
        .select_from(Deal)
        .outerjoin(User, User.email == Deal.fund_id)
        .group_by(User.subscription_tier)
        .all()
    )

    for tier, deal_count, deals_30d in deal_rows:
        key = tier or "unknown"
        bucket = tier_data.setdefault(key, {
            "user_count": 0,
            "active_user_count": 0,
            "deal_count": 0,
            "deals_last_30d": 0,
            "mrr_cents": 0,
        })
        bucket["deal_count"] = int(deal_count or 0)
        bucket["deals_last_30d"] = int(deals_30d or 0)

    tiers = [
        TierBreakdownItem(
            tier=tier_name,
            user_count=data["user_count"],
            deal_count=data["deal_count"],
            deals_last_30d=data["deals_last_30d"],
            mrr_cents=data["mrr_cents"],
        )
        for tier_name, data in sorted(tier_data.items(), key=lambda kv: -kv[1]["mrr_cents"])
    ]

    total_mrr = sum(t.mrr_cents for t in tiers)
    return TierBreakdownResponse(tiers=tiers, total_mrr_cents=total_mrr)


@router.get("/top-users", response_model=TopUsersResponse)
async def get_top_users(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Leaderboard of users by total deal volume. Response is explicitly sanitised."""
    _require_admin(request)
    _set_read_only(db)

    cutoff_30d = _utcnow() - timedelta(days=30)

    rows = (
        db.query(
            Deal.fund_id.label("fund_id"),
            func.count(Deal.id).label("total_deals"),
            func.sum(case((Deal.created_at >= cutoff_30d, 1), else_=0)).label("deals_30d"),
            func.max(Deal.created_at).label("last_deal_at"),
        )
        .group_by(Deal.fund_id)
        .order_by(func.count(Deal.id).desc())
        .limit(limit)
        .all()
    )

    if not rows:
        return TopUsersResponse(users=[])

    emails = [r.fund_id for r in rows]
    user_map = {
        u.email: u
        for u in db.query(User).filter(User.email.in_(emails)).all()
    }

    result: List[TopUserItem] = []
    for r in rows:
        user = user_map.get(r.fund_id)
        monthly_limit = get_monthly_limit(user) if user else 0
        monthly_used = get_monthly_used(db, user) if user else 0
        result.append(TopUserItem(
            email=r.fund_id,
            name=user.name if user else None,
            role=user.role if user else None,
            subscription_tier=user.subscription_tier if user else None,
            subscription_status=user.subscription_status if user else None,
            total_deals=int(r.total_deals or 0),
            deals_last_30d=int(r.deals_30d or 0),
            last_deal_at=r.last_deal_at.isoformat() if r.last_deal_at else None,
            monthly_limit=monthly_limit,
            monthly_used=monthly_used,
            is_at_limit=(monthly_limit > 0 and monthly_used >= monthly_limit),
        ))

    return TopUsersResponse(users=result)


@router.get("/status-breakdown", response_model=StatusBreakdownResponse)
async def get_status_breakdown(request: Request, db: Session = Depends(get_db)):
    """Deal pipeline health: counts by status and version."""
    _require_admin(request)
    _set_read_only(db)

    total = db.query(func.count(Deal.id)).scalar() or 0

    status_rows = (
        db.query(Deal.status, func.count(Deal.id))
        .group_by(Deal.status)
        .all()
    )
    by_status = {(s or "unknown"): int(c or 0) for s, c in status_rows}

    version_rows = (
        db.query(Deal.version, func.count(Deal.id))
        .group_by(Deal.version)
        .all()
    )
    by_version = {(v or "1"): int(c or 0) for v, c in version_rows}

    cutoff_7d = _utcnow() - timedelta(days=7)
    errors_last_7d = db.query(func.count(Deal.id)).filter(
        Deal.status == "error",
        Deal.created_at >= cutoff_7d,
    ).scalar() or 0

    return StatusBreakdownResponse(
        total=total,
        by_status=by_status,
        by_version=by_version,
        errors_last_7d=errors_last_7d,
    )


@router.get("/retention", response_model=RetentionResponse)
async def get_retention(
    request: Request,
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """Monthly signup cohorts × retention (did cohort upload a deal in month N?).

    Short-circuits to empty cohorts if total_users < 5 (insufficient data).
    """
    _require_admin(request)
    _set_read_only(db)

    total_users = db.query(func.count(User.id)).scalar() or 0
    if total_users < 5:
        return RetentionResponse(months=months, cohorts=[])

    now = _utcnow()
    # Build cohort month keys (YYYY-MM) for the last N months
    cohort_starts: List[datetime] = []
    for i in range(months, 0, -1):
        d = (now.replace(day=1) - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        cohort_starts.append(d)

    # For each cohort, fetch its users then count how many were active in month N
    cohorts: List[RetentionCohort] = []
    for cohort_start in cohort_starts:
        # Approximate end: one month later
        next_month = (cohort_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        cohort_key = cohort_start.strftime("%Y-%m")

        cohort_users = [
            u.email for u in db.query(User).filter(
                User.created_at >= cohort_start,
                User.created_at < next_month,
            ).all()
        ]
        if not cohort_users:
            cohorts.append(RetentionCohort(
                cohort=cohort_key, signups=0, active_months={},
            ))
            continue

        active_months: Dict[str, int] = {}
        # Track activity in each month from cohort_start to now
        cursor = cohort_start
        while cursor <= now:
            cursor_end = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            month_key = cursor.strftime("%Y-%m")
            active_count = db.query(
                func.count(func.distinct(Deal.fund_id))
            ).filter(
                Deal.fund_id.in_(cohort_users),
                Deal.created_at >= cursor,
                Deal.created_at < cursor_end,
            ).scalar() or 0
            active_months[month_key] = int(active_count)
            cursor = cursor_end

        cohorts.append(RetentionCohort(
            cohort=cohort_key,
            signups=len(cohort_users),
            active_months=active_months,
        ))

    return RetentionResponse(months=months, cohorts=cohorts)
