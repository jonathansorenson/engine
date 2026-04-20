"""Tests for /engine/api/v1/admin/analytics/* — the admin analytics dashboard.

Every endpoint is tested for:
  - auth (401 unauth, 403 non-admin)
  - happy path with correct aggregates
  - empty-state handling
  - input clamping / validation
  - PII non-leakage in response bodies
  - read-only guarantee (data unchanged after request)
"""

import hashlib
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func

from app.models.deal import Deal
from app.models.user import User


BASE = "/engine/api/v1/admin/analytics"

ENDPOINTS = [
    "/overview",
    "/timeseries",
    "/by-tier",
    "/top-users",
    "/status-breakdown",
    "/retention",
]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _snapshot(db):
    """Hash every deal and user row so we can assert nothing changed."""
    deals = db.query(Deal).order_by(Deal.id).all()
    users = db.query(User).order_by(User.id).all()
    h = hashlib.sha256()
    for d in deals:
        h.update(f"{d.id}|{d.fund_id}|{d.status}|{d.version}|{d.updated_at}".encode())
    for u in users:
        h.update(f"{u.id}|{u.email}|{u.role}|{u.subscription_tier}|{u.subscription_status}|{u.updated_at}".encode())
    return h.hexdigest(), len(deals), len(users)


def _assert_no_pii(text: str):
    """Response body must never contain sensitive fields."""
    forbidden = [
        "hashed_password",
        "stripe_customer_id",
        "stripe_subscription_id",
        "parsed_data",
        "v2_state",
        "assumptions",
        "parsing_report",
    ]
    for f in forbidden:
        assert f not in text, f"Response leaks sensitive field: {f}"


# ═══════════════════════════════════════════════════════════════════════════
# Auth gating
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("path", ENDPOINTS)
def test_anon_gets_401(anon_client, path):
    r = anon_client.get(BASE + path)
    assert r.status_code == 401


@pytest.mark.parametrize("path", ENDPOINTS)
def test_analyst_gets_403(analyst_client, path):
    r = analyst_client.get(BASE + path)
    assert r.status_code == 403


@pytest.mark.parametrize("path", ENDPOINTS)
def test_viewer_gets_403(viewer_client, path):
    r = viewer_client.get(BASE + path)
    assert r.status_code == 403


@pytest.mark.parametrize("path", ENDPOINTS)
def test_admin_gets_200(admin_client, seeded_deals, path):
    r = admin_client.get(BASE + path)
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# /overview
# ═══════════════════════════════════════════════════════════════════════════

def test_overview_aggregates(admin_client, seeded_deals, test_db):
    r = admin_client.get(BASE + "/overview")
    assert r.status_code == 200
    data = r.json()

    # 16 seeded deals, 3 users (admin+analyst+viewer)
    assert data["total_deals"] == 16
    assert data["total_users"] == 3

    # Active users in last 30d: 4 distinct fund_ids (analyst, viewer, admin, orphan)
    assert data["active_users_30d"] == 4

    # Deals last 30d: all 16 are within 30d
    assert data["deals_last_30d"] == 16

    # Deals last 7d: viewer's 3 (days 1,2,3) + analyst's parsed (days 0,3,6) +
    # analyst's error (day 2) + analyst's parsing (day 1) + admin's (day 0) = 9
    assert data["deals_last_7d"] >= 7  # tolerant to day-boundary timing

    # 14 parsed / 16 total = 0.875
    assert data["parse_error_count"] == 1
    assert data["parse_success_rate"] == pytest.approx(0.875, abs=0.01)

    _assert_no_pii(r.text)


def test_overview_empty_db(admin_client, test_db):
    r = admin_client.get(BASE + "/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["total_deals"] == 0
    assert data["total_users"] == 1  # admin_user fixture is seeded
    assert data["active_users_30d"] == 0
    assert data["deals_last_30d"] == 0
    assert data["parse_success_rate"] == 0.0


def test_overview_read_only(admin_client, seeded_deals, test_db):
    before = _snapshot(test_db)
    r = admin_client.get(BASE + "/overview")
    assert r.status_code == 200
    after = _snapshot(test_db)
    assert before == after, "Overview endpoint mutated the database"


# ═══════════════════════════════════════════════════════════════════════════
# /timeseries
# ═══════════════════════════════════════════════════════════════════════════

def test_timeseries_default(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/timeseries")
    assert r.status_code == 200
    data = r.json()
    assert data["bucket"] == "day"
    assert data["days"] == 30
    assert len(data["points"]) >= 1
    # Sum across points equals total deals (all within 30d for our seed)
    total = sum(p["count"] for p in data["points"])
    assert total == 16


def test_timeseries_week_bucket(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/timeseries?bucket=week&days=90")
    assert r.status_code == 200
    assert r.json()["bucket"] == "week"


def test_timeseries_month_bucket(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/timeseries?bucket=month&days=365")
    assert r.status_code == 200
    assert r.json()["bucket"] == "month"


def test_timeseries_invalid_bucket_400(admin_client):
    r = admin_client.get(BASE + "/timeseries?bucket=bogus")
    assert r.status_code == 422  # Pydantic pattern validation


def test_timeseries_clamps_days(admin_client):
    # Above max → 422 (we use Query(ge/le)); below 1 → 422
    r = admin_client.get(BASE + "/timeseries?days=99999")
    assert r.status_code == 422
    r = admin_client.get(BASE + "/timeseries?days=0")
    assert r.status_code == 422


def test_timeseries_no_pii(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/timeseries")
    _assert_no_pii(r.text)


def test_timeseries_read_only(admin_client, seeded_deals, test_db):
    before = _snapshot(test_db)
    admin_client.get(BASE + "/timeseries")
    admin_client.get(BASE + "/timeseries?bucket=week&days=60")
    admin_client.get(BASE + "/timeseries?bucket=month&days=180")
    assert _snapshot(test_db) == before


# ═══════════════════════════════════════════════════════════════════════════
# /by-tier
# ═══════════════════════════════════════════════════════════════════════════

def test_by_tier_aggregates(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/by-tier")
    assert r.status_code == 200
    data = r.json()
    tiers = {t["tier"]: t for t in data["tiers"]}

    # pro tier has 1 active user with stripe → MRR = 1 * 1199 = 1199
    assert tiers["pro"]["user_count"] == 1
    assert tiers["pro"]["mrr_cents"] == 1199
    assert tiers["pro"]["deal_count"] == 10

    # starter tier has 1 user (viewer) → but viewer has no stripe_customer_id,
    # but subscription_status = "active". MRR is counted only when active/trialing.
    # The viewer fixture has status='active' → MRR counted.
    assert tiers["starter"]["user_count"] == 1
    assert tiers["starter"]["mrr_cents"] == 699
    assert tiers["starter"]["deal_count"] == 3

    # admin tier has 1 user → price 0
    assert tiers["admin"]["user_count"] == 1
    assert tiers["admin"]["mrr_cents"] == 0
    assert tiers["admin"]["deal_count"] == 2

    # Total MRR
    assert data["total_mrr_cents"] == 1199 + 699


def test_by_tier_empty_db(admin_client, test_db):
    # Only admin_user exists (from fixture)
    r = admin_client.get(BASE + "/by-tier")
    assert r.status_code == 200
    data = r.json()
    # Admin tier has 1 user, no deals
    tiers = {t["tier"]: t for t in data["tiers"]}
    assert tiers["admin"]["user_count"] == 1
    assert data["total_mrr_cents"] == 0


def test_by_tier_no_pii(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/by-tier")
    _assert_no_pii(r.text)


def test_by_tier_read_only(admin_client, seeded_deals, test_db):
    before = _snapshot(test_db)
    admin_client.get(BASE + "/by-tier")
    assert _snapshot(test_db) == before


# ═══════════════════════════════════════════════════════════════════════════
# /top-users
# ═══════════════════════════════════════════════════════════════════════════

def test_top_users_ordering(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/top-users")
    assert r.status_code == 200
    users = r.json()["users"]
    counts = [u["total_deals"] for u in users]
    assert counts == sorted(counts, reverse=True), "Leaderboard not sorted desc"

    # Analyst has the most deals (10)
    assert users[0]["email"] == "analyst@test.local"
    assert users[0]["total_deals"] == 10
    assert users[0]["subscription_tier"] == "pro"


def test_top_users_includes_orphan(admin_client, seeded_deals):
    """Deals from users without a matching User row still appear (null tier)."""
    r = admin_client.get(BASE + "/top-users")
    emails = [u["email"] for u in r.json()["users"]]
    assert "orphan@nouser.local" in emails
    orphan = next(u for u in r.json()["users"] if u["email"] == "orphan@nouser.local")
    assert orphan["subscription_tier"] is None
    assert orphan["monthly_limit"] == 0


def test_top_users_limit(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/top-users?limit=2")
    assert r.status_code == 200
    assert len(r.json()["users"]) == 2


def test_top_users_limit_validation(admin_client):
    r = admin_client.get(BASE + "/top-users?limit=99999")
    assert r.status_code == 422
    r = admin_client.get(BASE + "/top-users?limit=0")
    assert r.status_code == 422


def test_top_users_no_pii(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/top-users")
    _assert_no_pii(r.text)
    # Extra: stripe customer id NEVER appears
    assert "cus_test_analyst" not in r.text


def test_top_users_monthly_used_matches_billing(admin_client, seeded_deals, test_db):
    from app.routes.billing import get_monthly_used
    analyst = test_db.query(User).filter(User.email == "analyst@test.local").first()
    expected = get_monthly_used(test_db, analyst)

    r = admin_client.get(BASE + "/top-users")
    analyst_row = next(u for u in r.json()["users"] if u["email"] == "analyst@test.local")
    assert analyst_row["monthly_used"] == expected


def test_top_users_read_only(admin_client, seeded_deals, test_db):
    before = _snapshot(test_db)
    admin_client.get(BASE + "/top-users")
    assert _snapshot(test_db) == before


def test_top_users_empty(admin_client, test_db):
    r = admin_client.get(BASE + "/top-users")
    assert r.status_code == 200
    assert r.json()["users"] == []


# ═══════════════════════════════════════════════════════════════════════════
# /status-breakdown
# ═══════════════════════════════════════════════════════════════════════════

def test_status_breakdown(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/status-breakdown")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 16
    # 14 parsed (8 analyst + 3 viewer + 2 admin + 1 orphan), 1 error, 1 parsing
    assert data["by_status"]["parsed"] == 14
    assert data["by_status"]["error"] == 1
    assert data["by_status"]["parsing"] == 1
    # All seeded deals use version="2"
    assert data["by_version"]["2"] == 16
    # 1 error, created 2 days ago → within 7d
    assert data["errors_last_7d"] == 1


def test_status_breakdown_empty(admin_client, test_db):
    r = admin_client.get(BASE + "/status-breakdown")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["by_status"] == {}
    assert data["by_version"] == {}
    assert data["errors_last_7d"] == 0


def test_status_breakdown_no_pii(admin_client, seeded_deals):
    r = admin_client.get(BASE + "/status-breakdown")
    _assert_no_pii(r.text)


def test_status_breakdown_read_only(admin_client, seeded_deals, test_db):
    before = _snapshot(test_db)
    admin_client.get(BASE + "/status-breakdown")
    assert _snapshot(test_db) == before


# ═══════════════════════════════════════════════════════════════════════════
# /retention
# ═══════════════════════════════════════════════════════════════════════════

def test_retention_short_circuits_with_few_users(admin_client, seeded_deals):
    # Only 3 users → short-circuits to empty cohorts
    r = admin_client.get(BASE + "/retention")
    assert r.status_code == 200
    data = r.json()
    assert data["cohorts"] == []


def test_retention_with_enough_users(admin_client, test_db):
    # Seed 6 users to pass the threshold
    import uuid
    for i in range(6):
        u = User(
            id=str(uuid.uuid4()),
            email=f"user{i}@test.local",
            fund_id=f"user{i}@test.local",
            hashed_password="x",
            name=f"User {i}",
            role="analyst",
            is_active=True,
            subscription_tier="starter",
            subscription_status="active",
            created_at=datetime.utcnow() - timedelta(days=30 * (i + 1)),
            updated_at=datetime.utcnow(),
        )
        test_db.add(u)
    test_db.commit()

    r = admin_client.get(BASE + "/retention?months=3")
    assert r.status_code == 200
    data = r.json()
    assert data["months"] == 3
    assert len(data["cohorts"]) == 3


def test_retention_validation(admin_client):
    r = admin_client.get(BASE + "/retention?months=999")
    assert r.status_code == 422
    r = admin_client.get(BASE + "/retention?months=0")
    assert r.status_code == 422


def test_retention_read_only(admin_client, seeded_deals, test_db):
    before = _snapshot(test_db)
    admin_client.get(BASE + "/retention")
    assert _snapshot(test_db) == before


# ═══════════════════════════════════════════════════════════════════════════
# Module-level contract: full read-only sweep across all endpoints
# ═══════════════════════════════════════════════════════════════════════════

def test_full_sweep_read_only(admin_client, seeded_deals, test_db):
    """Hit every endpoint and assert zero mutations."""
    before = _snapshot(test_db)
    for path in ENDPOINTS:
        r = admin_client.get(BASE + path)
        assert r.status_code == 200, f"{path} failed: {r.text}"
    assert _snapshot(test_db) == before


def test_full_sweep_no_pii(admin_client, seeded_deals):
    for path in ENDPOINTS:
        r = admin_client.get(BASE + path)
        _assert_no_pii(r.text)
