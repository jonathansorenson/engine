"""Public, unauthenticated metrics endpoint for marketing pages.

Returns aggregate counts and totals only — no PII, no per-user data, no
deal-level detail. Used by the marketing site (crelytic.ai) to display
live "deals analyzed" / "deal volume" tiles.

Hard constraint: this module MUST NOT contain db.add, db.delete, db.commit,
db.merge, db.flush, INSERT, UPDATE, or DELETE. Read-only aggregations only.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBaseModel

from app.config import settings
from app.database import get_db
from app.models.deal import Deal


router = APIRouter(prefix="/api/v1/public", tags=["public"])


class PublicMetricsResponse(PydanticBaseModel):
    deals_analyzed: int
    deal_volume_usd: float
    generated_at: str


def _set_read_only(db: Session) -> None:
    if "postgresql" in settings.database_url:
        try:
            db.execute(text("SET TRANSACTION READ ONLY"))
        except Exception:
            pass


def _sum_asking_price(db: Session) -> float:
    """Sum the per-deal price across all parsed deals.

    Mirrors the V2-wins-over-V1 priority used in deals.py when surfacing
    asking_price on a deal list item:

      1. v2_state->'assumptions'->>'purchasePrice' (camelCase, V2 — set by
         Claude AI extraction or user-edited assumption; canonical for V2)
      2. parsed_data->'property'->>'asking_price' (snake_case, V1 — OM regex)
      3. parsed_data->'financials'->>'asking_price' (V1 fallback)

    Per-deal COALESCE picks the first non-null in priority order. Outer SUM
    aggregates across deals.
    """
    if "postgresql" in settings.database_url:
        sql = text(
            """
            SELECT COALESCE(SUM(
                COALESCE(
                    NULLIF(v2_state->'assumptions'->>'purchasePrice', '')::numeric,
                    NULLIF(parsed_data->'property'->>'asking_price', '')::numeric,
                    NULLIF(parsed_data->'financials'->>'asking_price', '')::numeric,
                    0
                )
            ), 0)::float
            FROM deals
            WHERE status = 'parsed'
            """
        )
        try:
            return float(db.execute(sql).scalar() or 0.0)
        except Exception:
            return 0.0

    # SQLite / dev fallback: iterate in Python with the same priority.
    total = 0.0
    rows = db.query(Deal.parsed_data, Deal.v2_state).filter(Deal.status == "parsed").all()
    for parsed, v2 in rows:
        v2_pp = (v2 or {}).get("assumptions", {}).get("purchasePrice") if isinstance(v2, dict) else None
        prop = (parsed or {}).get("property", {}).get("asking_price") if isinstance(parsed, dict) else None
        fin = (parsed or {}).get("financials", {}).get("asking_price") if isinstance(parsed, dict) else None
        try:
            total += float(v2_pp or prop or fin or 0)
        except (TypeError, ValueError):
            continue
    return total


@router.get("/metrics", response_model=PublicMetricsResponse)
async def get_public_metrics(request: Request, db: Session = Depends(get_db)):
    """Aggregate marketing metrics. No auth, no PII.

    Returns:
      - deals_analyzed: count of successfully parsed deals
      - deal_volume_usd: sum of asking_price across parsed deals
      - generated_at: ISO timestamp
    """
    _set_read_only(db)

    deals_analyzed = db.query(func.count(Deal.id)).filter(
        Deal.status == "parsed"
    ).scalar() or 0

    deal_volume_usd = _sum_asking_price(db)

    payload = PublicMetricsResponse(
        deals_analyzed=int(deals_analyzed),
        deal_volume_usd=round(float(deal_volume_usd), 2),
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    response = JSONResponse(content=payload.model_dump())
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
