"""Shared pytest fixtures for backend tests.

Provides:
  - test_db:         in-memory SQLite Session
  - admin_user /
    analyst_user /
    viewer_user:     pre-seeded User rows
  - seeded_deals:    a deterministic set of Deal rows for aggregation tests
  - admin_client /
    analyst_client /
    anon_client:     TestClient instances with a pre-signed session cookie

Tests that need auth should use *_client fixtures — the cookie is built via
`app.main._sign` using the same payload shape as the real login handler.
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Add backend/ to path so `app.*` imports work regardless of where pytest runs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Force a fresh in-memory SQLite before importing the app
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD", "testpass")

from app.main import app, _sign, COOKIE_NAME  # noqa: E402
from app.database import get_db  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.deal import Deal  # noqa: E402
from app.routes.admin import hash_password  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# DB fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def test_engine():
    """Fresh in-memory SQLite engine per test — full isolation."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(test_engine) -> Generator[Session, None, None]:
    """Session bound to the per-test engine. Also overrides get_db in FastAPI."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()

    def _override():
        try:
            yield session
        finally:
            pass  # Session closed in outer fixture cleanup

    app.dependency_overrides[get_db] = _override
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.pop(get_db, None)


# ═══════════════════════════════════════════════════════════════════════════
# User fixtures — persisted to test_db
# ═══════════════════════════════════════════════════════════════════════════

def _mk_user(
    db: Session,
    email: str,
    role: str = "analyst",
    tier: str = "admin",
    status: str = "active",
    stripe_customer_id: str = None,
    name: str = None,
    created_at: datetime = None,
) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=email,
        fund_id=email,
        hashed_password=hash_password("pw"),
        name=name or email.split("@")[0],
        role=role,
        is_active=True,
        subscription_tier=tier,
        subscription_status=status,
        stripe_customer_id=stripe_customer_id,
        created_at=created_at or datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def admin_user(test_db) -> User:
    return _mk_user(test_db, "admin@test.local", role="admin", tier="admin")


@pytest.fixture
def analyst_user(test_db) -> User:
    return _mk_user(
        test_db, "analyst@test.local", role="analyst", tier="pro",
        status="active", stripe_customer_id="cus_test_analyst",
    )


@pytest.fixture
def viewer_user(test_db) -> User:
    return _mk_user(test_db, "viewer@test.local", role="viewer", tier="starter")


# ═══════════════════════════════════════════════════════════════════════════
# Seeded deals — deterministic fixture for aggregation tests
# ═══════════════════════════════════════════════════════════════════════════

def _mk_deal(
    db: Session,
    fund_id: str,
    status: str = "parsed",
    created_at: datetime = None,
    version: str = "2",
    name: str = None,
) -> Deal:
    d = Deal(
        id=str(uuid.uuid4()),
        fund_id=fund_id,
        name=name or f"Deal {uuid.uuid4().hex[:6]}",
        status=status,
        version=version,
        created_at=created_at or datetime.utcnow(),
        updated_at=created_at or datetime.utcnow(),
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture
def seeded_deals(test_db, admin_user, analyst_user, viewer_user):
    """Seed a known dataset for analytics tests.

    Distribution:
      analyst@test.local (pro):      10 deals (8 parsed, 1 error, 1 parsing), mixed dates
      viewer@test.local (starter):    3 deals (all parsed), all in last 7 days
      admin@test.local (admin):       2 deals (both parsed), in last 30 days
      orphan@nouser.local:            1 deal (parsed), in last 30 days (no user row)
    Total: 16 deals, 4 distinct fund_ids
    """
    now = datetime.utcnow()
    deals: List[Deal] = []

    # Analyst: 10 deals
    for i in range(8):
        deals.append(_mk_deal(
            test_db, analyst_user.email, status="parsed",
            created_at=now - timedelta(days=i * 3),  # spread over last 24 days
        ))
    deals.append(_mk_deal(
        test_db, analyst_user.email, status="error",
        created_at=now - timedelta(days=2),
    ))
    deals.append(_mk_deal(
        test_db, analyst_user.email, status="parsing",
        created_at=now - timedelta(days=1),
    ))

    # Viewer: 3 deals, all in last 7 days
    for i in range(3):
        deals.append(_mk_deal(
            test_db, viewer_user.email, status="parsed",
            created_at=now - timedelta(days=i + 1),
        ))

    # Admin: 2 deals
    for i in range(2):
        deals.append(_mk_deal(
            test_db, admin_user.email, status="parsed",
            created_at=now - timedelta(days=i * 10),
        ))

    # Orphan deal (no matching user row)
    deals.append(_mk_deal(
        test_db, "orphan@nouser.local", status="parsed",
        created_at=now - timedelta(days=5),
    ))

    return deals


# ═══════════════════════════════════════════════════════════════════════════
# Auth clients — TestClient with pre-signed session cookie
# ═══════════════════════════════════════════════════════════════════════════

def _cookie_for(email: str, role: str, name: str = "") -> str:
    payload = json.dumps({
        "user_id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "role": role,
        "ts": int(time.time()),
    })
    return _sign(payload)


@pytest.fixture
def anon_client(test_db) -> TestClient:
    """Unauthenticated client."""
    return TestClient(app)


@pytest.fixture
def admin_client(test_db, admin_user) -> TestClient:
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, _cookie_for(admin_user.email, "admin", admin_user.name or ""))
    return client


@pytest.fixture
def analyst_client(test_db, analyst_user) -> TestClient:
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, _cookie_for(analyst_user.email, "analyst", analyst_user.name or ""))
    return client


@pytest.fixture
def viewer_client(test_db, viewer_user) -> TestClient:
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, _cookie_for(viewer_user.email, "viewer", viewer_user.name or ""))
    return client
