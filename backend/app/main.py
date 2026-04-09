import os
import hmac
import hashlib
import json
import time
import base64
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)
from app.database import init_db, SessionLocal
from app.models.user import User
from app.routes import deals_router, chat_router, admin_router, export_router, billing_router
from app.routes.admin import hash_password, verify_password

# Path to frontend — check Docker path first, then relative (local dev)
_docker_frontend = Path("/frontend")
_local_frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
FRONTEND_DIR = _docker_frontend if _docker_frontend.exists() else _local_frontend

# Cookie config
COOKIE_NAME = "crelytic_session"
COOKIE_MAX_AGE = 86400  # 24 hours (was 7 days)

# Rate limiting for login — track failed attempts per IP
_login_attempts = {}  # ip -> [timestamp, timestamp, ...]
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes
LOCKOUT_SECONDS = 900  # 15 minute lockout after max attempts


# ═══════════════════════════════════════════════════════════════
# SIGNED COOKIE HELPERS (no external deps)
# ═══════════════════════════════════════════════════════════════

def _sign(value: str) -> str:
    """Create HMAC signature for a base64-encoded value."""
    b64 = base64.urlsafe_b64encode(value.encode()).decode()
    sig = hmac.new(settings.secret_key.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def _verify(signed: str):
    """Verify a signed cookie value. Returns the decoded payload if valid, None otherwise."""
    if not signed or "." not in signed:
        return None
    b64, sig = signed.rsplit(".", 1)
    expected = hmac.new(settings.secret_key.encode(), b64.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected):
        try:
            return base64.urlsafe_b64decode(b64.encode()).decode()
        except Exception:
            return None
    return None


def _get_user_from_cookie(cookie_value: str):
    """Extract user info from verified cookie payload."""
    payload = _verify(cookie_value)
    if not payload:
        return None
    try:
        data = json.loads(payload)
        return data
    except (json.JSONDecodeError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════
# AUTH MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

class AuthMiddleware(BaseHTTPMiddleware):
    """User authentication for /engine/* routes. Admin check for /engine/api/v1/admin/*."""

    _BASE_PUBLIC = {"/health", "/engine/login", "/engine/signup", "/engine/api/v1/billing/webhook", "/"}
    _DEV_PATHS = {"/docs", "/openapi.json", "/redoc"}
    PUBLIC_PATHS = _BASE_PUBLIC | _DEV_PATHS if settings.env != "production" else _BASE_PUBLIC

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in self.PUBLIC_PATHS or not path.startswith("/engine"):
            return await call_next(request)

        # Check session cookie
        try:
            session = request.cookies.get(COOKIE_NAME, "")
            user_data = _get_user_from_cookie(session)
        except Exception:
            user_data = None

        if not user_data:
            if "/api/" in path:
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            return RedirectResponse(url="/engine/login", status_code=302)

        # Inject user info into request state
        request.state.fund_id = user_data.get("email", "unknown")
        request.state.user_email = user_data.get("email", "unknown")
        request.state.user_role = user_data.get("role", "analyst")
        request.state.user_name = user_data.get("name", "")

        # Admin-only routes
        if "/api/v1/admin" in path and user_data.get("role") != "admin":
            return JSONResponse({"detail": "Admin access required"}, status_code=403)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ═══════════════════════════════════════════════════════════════
# LOGIN PAGE HTML
# ═══════════════════════════════════════════════════════════════

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRELYTIC Engine</title>
    <link rel="icon" type="image/png" sizes="32x32" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAABiUlEQVRYhe2WPy9DURiHn/e0FIn/qUi0FQwkTZlIfAJDTWInfAI7A7Gz2YTdavEhEFeCgXBaQRfSgV6peyxC5V6izW1ruL/tvHnP+zz33HuSK3wklpzsEopLgpkFBoAI/sYGrgyyJ6qwoS3rEUAABpITY2+87YP0+Qz9KVlHnHT29PBEEqlUJ06jVUP4pwTKHg11RBPLIOkawwHajGl4DRuYqcb09YUUw7FWV/1c51nZOQVAMDMKGKyGgBccYCTRVrocUvj/tZeTJlVHOACBQCBQd4FwJZumFueJxmOuek5nONjeLWtWRSfgBQfoScTLnlX3VxAIBAKua9gb6yfS1OxqtF+eub/Vvgu4TsALDhBpbvEd7ilQ6wQC/0LAriO/oICr0or98uzdWVLP6YxnT+7m65qe67xnz9n3+qXEk+Nrgln5m7DPEVaVqMIG4P1I1U1GhYubSlvWoyPONJCtJdxRJn19fPwUAsjn7h7ae7t3MCEbiIK0UuHf0i8pABcIW6qhOKdPjjTAO0ACbHMMH2tvAAAAAElFTkSuQmCC">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0a1628 0%, #1a2744 50%, #0d1f3c 100%);
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
            color: #e2e8f0; padding: 1rem;
        }
        .container {
            display: flex; gap: 2rem; max-width: 880px; width: 100%; align-items: stretch;
        }
        .panel {
            background: rgba(255,255,255,0.05); backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;
            padding: 2.5rem; flex: 1;
        }
        .panel-login { text-align: center; }
        .panel-cta {
            background: linear-gradient(135deg, rgba(0,191,165,0.08), rgba(59,130,246,0.08));
            border-color: rgba(0,191,165,0.25);
        }
        .logo { margin-bottom: 1.5rem; }
        .logo img { height: 48px; opacity: 0.95; }
        .brand-title { font-size: 1.5rem; font-weight: 800; letter-spacing: 3px; margin-bottom: 0.25rem; }
        .subtitle { font-size: 0.85rem; color: #94a3b8; margin-bottom: 2rem; letter-spacing: 2px; text-transform: uppercase; }
        input {
            width: 100%; padding: 0.9rem 1.2rem; border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; background: rgba(255,255,255,0.05); color: white;
            font-size: 1rem; outline: none; transition: border 0.2s;
            margin-bottom: 0.75rem;
        }
        input:focus { border-color: #00BFA5; }
        input::placeholder { color: #64748b; }
        .btn-primary {
            width: 100%; padding: 0.9rem; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #00BFA5, #00897B); color: white;
            font-size: 1rem; font-weight: 700; cursor: pointer; transition: opacity 0.2s;
            margin-top: 0.25rem; display: inline-block; text-align: center; text-decoration: none;
        }
        .btn-primary:hover { opacity: 0.9; }
        .btn-secondary {
            display: inline-block; margin-top: 1rem; padding: 0.65rem 1.5rem;
            border: 1px solid rgba(96,165,250,0.4); border-radius: 10px;
            color: #60a5fa; font-size: 0.9rem; font-weight: 600; text-decoration: none;
            transition: all 0.2s;
        }
        .btn-secondary:hover { background: rgba(96,165,250,0.1); border-color: #60a5fa; }
        .error { color: #ef4444; font-size: 0.85rem; margin-bottom: 1rem; display: none; }
        .error.show { display: block; }
        .cta-headline { font-size: 1.4rem; font-weight: 800; letter-spacing: 2px; margin-bottom: 0.35rem; }
        .cta-sub { font-size: 0.95rem; color: #94a3b8; margin-bottom: 1.5rem; line-height: 1.5; }
        .features { list-style: none; margin-bottom: 1.5rem; text-align: left; }
        .features li { padding: 0.4rem 0; font-size: 0.92rem; color: #cbd5e1; }
        .features li::before { content: "\\2713\\0020"; color: #00BFA5; font-weight: 700; margin-right: 0.5rem; }
        .pricing-note { font-size: 0.85rem; color: #94a3b8; margin-bottom: 1.25rem; }
        .pricing-note strong { color: #e2e8f0; font-size: 1.05rem; }
        @media (max-width: 768px) {
            .container { flex-direction: column; }
            .panel { padding: 2rem 1.5rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="panel panel-login">
            <div class="logo"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAYAAAA9zQYyAAAABmJLR0QA/wD/AP+gvaeTAAAK4klEQVR4nO3dbWxT1x3H8d85dmwnJDEQQkggCVDUAE5pgQQ2dQ+00rp23ZM0hY5uL6ZqarVu07SpqtQXmybtsZU6VVPVaVRTtUlVEbzqNnWimtp1q1rSkLQNMZC2WyAQhzzHIYljxz5nLxpQQp1g+97rezl8PhIiJL7Hf+CbmxvH11fAYZs3HwilK2b2C6X3CIEmaNwKoAFAOYBVC7+TOaYXfs0A6IdGLwR6tRJdwfmJ9o8++ijp5J0LJxatb9pdJ33ykBbyS4D+NIBSJ+6HbjgJAG9p6Fekwkvnz3QO2n0HdgYtG5v3fQ1aPayBLwDw2bg2mSejgVeh9OELZzr/CkDZsaj1oNvafA1nzh2CVk8AYqcNM9HNJyq0+M35yOYjOHYsY2UhS0E33LZnL5T8A4BWK+sQLXhPSPno+VPvvF3oAgUFXR2JlJei9GkA3wUgC71zoiwUNA4n/anHhrq7Z/LdOO+gG5v37NCQR6HRnO+2RHnoVUIdvNjT1Z3PRnntXesjLYe0lp2MmYqgSWr5dn1z6wP5bJTzIxGNkZYfAHgeQCDfyYgKVCKAb6yurp2OjwzmdFydU9ANzS0/B/AkHHrcmmgFAkLcE66uQ3wk9sb1bnzdoOsjrY8K4Cl7ZiMqkMCB8Pq6eHwkdmKlm60YdGNk74P4+DCDe2bygnvC1RvPxkdi0eVusGyo9TtamoVEO4AyR0YjKsycD/JTfdF33s/2wayPctTs2rVKSBwFYybvCSmoo01Nd1Zk+2DWoIOZwO8A7HB0LKICaeDWOX/qyWwf+8QhR32ktVVAnwB/AkjepqRSd54707Xkm8Sl0ba1+QT04U+8n8h7pJK+Z9HWtuSBjSV/aJBl3wbwvaKORVS4usqRyTNTI7GeK+9YvCcWAB4v/kxEhRPQP8Wijq++0di87+t8jgbdeMTO+p0tX7nyp6tBa60fcWcgImuExMNX3wY+PgdQ+H394GlTdGNKS4j6c9GOS34AkD55SDPmm87GdaWINIZRFir+f318Zh6n+uIYjdtyErhfQX8TwDN+AFg4O9uOhekGUFlWgke+vBX7tle5OofSwGtdQ3jheB9SaavnyIp7ATwjtm3bFkwFV0+ALzVwUygL+vCrh3ZhU7V3/rt7+uL45YunkVGWdqqzgeTkWpkOrebrZtxEHry70VMxA0DzljDu21drdZmyZKByn8xo7LZjKPK+Er/E52+vdnuMrL7YusHyGkKK3VIINNkwD90ANq0rRSjgze/9N6wJoSxobTah0SS1ZtA3i9Kg3+0RVrSq1Np8GqJJCuiNNs1D5CoB1EtAVLo9CJEdNFAhwZezJXNUSPA0KzLHKgme0U3mEDwzhYzCoMkoDJqMwqDJKAyajMKgySgMmozCoMkoDJqMwqDJKAyajMKgySgMmozCoMkoDJqMwqDJKAyajMKgySgMmozCoMkoDJqMwqDJKAyajMKgySgMmozCoMkoDJqMwqDJKAyajMKgySgMmozCoMkoDJqMwqDJKAyajMKgySgMmozCoMko3r6aucdIKbHl9l1o3LkD5WvCkL7i/vOlkymMxgbw4ckujMUGi3rfNwoGnaPS" alt="CRELYTIC" /></div>
            <div class="brand-title">CRELYTIC</div>
            <div class="subtitle">AI-Powered Deal Underwriting</div>
            <form method="POST" action="/engine/login">
                <div class="error {error_class}" id="err">{error_msg}</div>
                <input type="email" name="email" placeholder="Email address" required />
                <input type="password" name="password" placeholder="Password" required />
                <button type="submit" class="btn-primary">Sign In</button>
            </form>
            <a href="/engine/signup" class="btn-secondary">Don't have an account? Sign up</a>
        </div>
        <div class="panel panel-cta">
            <div class="cta-headline">CRELYTIC Engine</div>
            <div class="cta-sub">Upload an OM. Get a full DCF, waterfall, and investment memo &mdash; in minutes.</div>
            <ul class="features">
                <li>Instant OM parsing with AI</li>
                <li>Full DCF &amp; sensitivity analysis</li>
                <li>LP/GP waterfall distributions</li>
                <li>Institutional-quality memos</li>
                <li>Excel, Word &amp; PDF exports</li>
            </ul>
            <div class="pricing-note">Plans from <strong>$6.99/mo</strong></div>
            <a href="/engine/signup" class="btn-primary" style="margin-top:0;">Get Started &rarr;</a>
        </div>
    </div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# SEED ADMIN USER
# ═══════════════════════════════════════════════════════════════

def seed_admin_user():
    """Create or update the admin user from env vars. Requires ADMIN_EMAIL and ADMIN_PASSWORD."""
    if not settings.admin_email or not settings.admin_password:
        print("[Security] ADMIN_EMAIL and ADMIN_PASSWORD not set — skipping admin seed")
        return
    db = SessionLocal()
    try:
        admin_email = settings.admin_email.lower().strip()
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            existing.hashed_password = hash_password(settings.admin_password)
            existing.role = "admin"
            existing.is_active = True
            db.commit()
            print(f"[Startup] Admin user synced")
        else:
            admin = User(
                email=admin_email,
                hashed_password=hash_password(settings.admin_password),
                name="Admin",
                role="admin",
                fund_id=admin_email,
            )
            db.add(admin)
            db.commit()
            print(f"[Startup] Admin user created")
    except Exception as e:
        print(f"[Startup] Admin seed error: {e}")
        db.rollback()
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize app on startup, cleanup on shutdown."""
    init_db()
    seed_admin_user()
    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info(f"Application started. ENV={settings.env}")
    logger.info(f"Anthropic API key: {'SET' if settings.anthropic_api_key else 'NOT SET'}")
    logger.info(f"Engine at: http://localhost:8000/engine")
    yield
    print("Application shutting down")


app = FastAPI(
    title="CRE Deal Underwriting Tool",
    description="Backend API for commercial real estate deal analysis",
    version="2.0.0",
    lifespan=lifespan,
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Auth middleware (must be added BEFORE CORS)
app.add_middleware(AuthMiddleware)

# CORS middleware
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# Register API routers under /engine prefix
app.include_router(deals_router, prefix="/engine")
app.include_router(chat_router, prefix="/engine")
app.include_router(admin_router, prefix="/engine")
app.include_router(export_router, prefix="/engine")
app.include_router(billing_router)


# ═══════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy", "service": "CRE Lytic Engine", "version": "2.0.0"}


@app.get("/")
async def root():
    """Root endpoint — redirect to engine or show info."""
    return RedirectResponse(url="/engine")


@app.get("/engine/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the email/password login form."""
    html = LOGIN_HTML.replace("{error_class}", "").replace("{error_msg}", "")
    # Show success message after signup
    if request.query_params.get("signup") == "success":
        html = html.replace(
            '<div class="error " id="err"></div>',
            '<div style="background:#22c55e33;border:1px solid #22c55e;color:#86efac;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;">Account created! Please sign in with your email and password.</div>'
        )
    return HTMLResponse(content=html)


@app.post("/engine/login")
async def login_submit(request: Request):
    """Validate email+password and set session cookie."""
    # Rate limiting by IP
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = _login_attempts.get(client_ip, [])
    # Clean old attempts outside window
    attempts = [t for t in attempts if now - t < LOGIN_WINDOW_SECONDS]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        oldest = min(attempts) if attempts else now
        wait = int(LOCKOUT_SECONDS - (now - oldest))
        html = LOGIN_HTML.replace("{error_class}", "show").replace("{error_msg}", f"Too many attempts. Try again in {max(1, wait // 60)} minutes.")
        return HTMLResponse(content=html, status_code=429)

    form = await request.form()
    email = (form.get("email", "") or "").lower().strip()
    password = form.get("password", "")

    # Look up user in database
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email, User.is_active == True).first()
        if user and verify_password(password, user.hashed_password):
            # Clear failed attempts on successful login
            _login_attempts.pop(client_ip, None)
            # Create signed session cookie with user data
            payload = json.dumps({
                "user_id": user.id,
                "email": user.email,
                "name": user.name or "",
                "role": user.role,
                "ts": int(time.time()),
            })
            token = _sign(payload)
            response = RedirectResponse(url="/engine", status_code=302)
            response.set_cookie(
                key=COOKIE_NAME,
                value=token,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=settings.env == "production",
            )
            return response
    finally:
        db.close()

    # Track failed attempt
    attempts.append(now)
    _login_attempts[client_ip] = attempts
    remaining = LOGIN_MAX_ATTEMPTS - len(attempts)

    # Wrong credentials — re-render login with error
    html = LOGIN_HTML.replace("{error_class}", "show").replace("{error_msg}", "Invalid email or password.")
    return HTMLResponse(content=html, status_code=401)


@app.get("/engine/logout")
async def logout():
    """Clear session cookie."""
    response = RedirectResponse(url="/engine/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/engine/me")
async def get_current_user(request: Request):
    """Return current user info (for frontend header) including investment preferences."""
    email = getattr(request.state, "user_email", "unknown")
    result = {
        "email": email,
        "name": getattr(request.state, "user_name", ""),
        "role": getattr(request.state, "user_role", "analyst"),
        "subscription_tier": None,
        "subscription_status": None,
        "has_stripe": False,
        "preferences": {},
    }
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            result["subscription_tier"] = user.subscription_tier
            result["subscription_status"] = user.subscription_status
            result["has_stripe"] = bool(user.stripe_customer_id)
            result["preferences"] = user.user_preferences or {}
    finally:
        db.close()
    return result


@app.get("/engine/me/preferences")
async def get_preferences(request: Request):
    """Return user's investment preferences."""
    email = getattr(request.state, "user_email", "unknown")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        return user.user_preferences or {} if user else {}
    finally:
        db.close()


ALLOWED_PREF_KEYS = {
    "hurdleIRR", "hurdleEM", "hurdleCoC", "hurdleDSCR", "hurdleMaxCap",
    "marketRenewalProb", "marketVacantMonths", "marketFreeRentMonths",
    "marketTINewPSF", "marketTIRenewalPSF", "marketLCNewPct", "marketLCRenewalPct",
}


@app.put("/engine/me/preferences")
async def update_preferences(request: Request):
    """Update user's investment preferences (merge with existing)."""
    email = getattr(request.state, "user_email", "unknown")
    body = await request.json()

    # Whitelist only allowed preference keys
    filtered = {k: v for k, v in body.items() if k in ALLOWED_PREF_KEYS and isinstance(v, (int, float))}

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return JSONResponse({"detail": "User not found"}, status_code=404)
        current = user.user_preferences or {}
        current.update(filtered)
        user.user_preferences = current
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user, "user_preferences")
        db.commit()
        return current
    finally:
        db.close()


@app.get("/engine", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend dashboard (authenticated)."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(), status_code=200)
    return HTMLResponse(
        content="<h1>Frontend not found</h1><p>Place index.html in the frontend/ directory.</p>",
        status_code=404,
    )


# Keep /app as an alias for backward compatibility
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend_legacy():
    """Legacy route — redirects to /engine."""
    return RedirectResponse(url="/engine", status_code=301)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
