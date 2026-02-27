import os
import hmac
import hashlib
import json
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, SessionLocal
from app.models.user import User
from app.routes import deals_router, chat_router, admin_router, export_router
from app.routes.admin import hash_password, verify_password

# Path to frontend — check Docker path first, then relative (local dev)
_docker_frontend = Path("/frontend")
_local_frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
FRONTEND_DIR = _docker_frontend if _docker_frontend.exists() else _local_frontend

# Cookie config
COOKIE_NAME = "crelytic_session"
COOKIE_MAX_AGE = 86400 * 7  # 7 days


# ═══════════════════════════════════════════════════════════════
# SIGNED COOKIE HELPERS (no external deps)
# ═══════════════════════════════════════════════════════════════

def _sign(value: str) -> str:
    """Create HMAC signature for a value."""
    sig = hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{value}.{sig}"


def _verify(signed: str):
    """Verify a signed cookie value. Returns the payload if valid, None otherwise."""
    if not signed or "." not in signed:
        return None
    value, sig = signed.rsplit(".", 1)
    expected = hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()[:16]
    if hmac.compare_digest(sig, expected):
        return value
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

    PUBLIC_PATHS = {"/health", "/engine/login", "/", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in self.PUBLIC_PATHS or not path.startswith("/engine"):
            return await call_next(request)

        # Check session cookie
        session = request.cookies.get(COOKIE_NAME, "")
        user_data = _get_user_from_cookie(session)

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


# ═══════════════════════════════════════════════════════════════
# LOGIN PAGE HTML
# ═══════════════════════════════════════════════════════════════

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRE Lytic — Engine Access</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0a1628 0%, #1a2744 50%, #0d1f3c 100%);
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
            color: #e2e8f0;
        }
        .card {
            background: rgba(255,255,255,0.05); backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;
            padding: 3rem; width: 100%; max-width: 420px; text-align: center;
        }
        .logo { margin-bottom: 2rem; }
        .logo span:first-child { font-size: 2rem; font-weight: 800; color: white; }
        .logo span:last-child { font-size: 2rem; font-weight: 800; color: #00BFA5; }
        .subtitle { font-size: 0.85rem; color: #94a3b8; margin-bottom: 2rem; letter-spacing: 2px; text-transform: uppercase; }
        input {
            width: 100%; padding: 0.9rem 1.2rem; border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; background: rgba(255,255,255,0.05); color: white;
            font-size: 1rem; outline: none; transition: border 0.2s;
            margin-bottom: 0.75rem;
        }
        input:focus { border-color: #00BFA5; }
        input::placeholder { color: #64748b; }
        button {
            width: 100%; padding: 0.9rem; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #00BFA5, #00897B); color: white;
            font-size: 1rem; font-weight: 700; cursor: pointer; transition: opacity 0.2s;
            margin-top: 0.25rem;
        }
        button:hover { opacity: 0.9; }
        .error { color: #ef4444; font-size: 0.85rem; margin-bottom: 1rem; display: none; }
        .error.show { display: block; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo"><span>CRE</span><span>lytic</span></div>
        <div class="subtitle">Underwriting Engine</div>
        <form method="POST" action="/engine/login">
            <div class="error {error_class}" id="err">{error_msg}</div>
            <input type="email" name="email" placeholder="Email address" required />
            <input type="password" name="password" placeholder="Password" required />
            <button type="submit">Sign In</button>
        </form>
    </div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# SEED ADMIN USER
# ═══════════════════════════════════════════════════════════════

def seed_admin_user():
    """Create or update the admin user from env vars."""
    db = SessionLocal()
    try:
        admin_email = settings.admin_email.lower().strip()
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            # Always sync password from env var so changes take effect on redeploy
            existing.hashed_password = hash_password(settings.admin_password)
            existing.role = "admin"
            existing.is_active = True
            db.commit()
            print(f"Updated admin user: {admin_email}")
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
            print(f"Created admin user: {admin_email}")
    except Exception as e:
        print(f"Error seeding admin user: {e}")
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
    print(f"Application started. Upload directory: {settings.upload_dir}")
    print(f"Engine at: http://localhost:8000/engine")
    print(f"Login at:  http://localhost:8000/engine/login")
    yield
    print("Application shutting down")


app = FastAPI(
    title="CRE Deal Underwriting Tool",
    description="Backend API for commercial real estate deal analysis",
    version="2.0.0",
    lifespan=lifespan,
)

# Auth middleware (must be added BEFORE CORS)
app.add_middleware(AuthMiddleware)

# CORS middleware
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers under /engine prefix
app.include_router(deals_router, prefix="/engine")
app.include_router(chat_router, prefix="/engine")
app.include_router(admin_router, prefix="/engine")
app.include_router(export_router, prefix="/engine")


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
async def login_page():
    """Serve the email/password login form."""
    html = LOGIN_HTML.replace("{error_class}", "").replace("{error_msg}", "")
    return HTMLResponse(content=html)


@app.post("/engine/login")
async def login_submit(request: Request):
    """Validate email+password and set session cookie."""
    form = await request.form()
    email = (form.get("email", "") or "").lower().strip()
    password = form.get("password", "")

    # Look up user in database
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email, User.is_active == True).first()
        if user and verify_password(password, user.hashed_password):
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
    """Return current user info (for frontend header)."""
    return {
        "email": getattr(request.state, "user_email", "unknown"),
        "name": getattr(request.state, "user_name", ""),
        "role": getattr(request.state, "user_role", "analyst"),
    }


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
