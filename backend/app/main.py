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
    <link rel="icon" type="image/png" sizes="32x32" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABmJLR0QA/wD/AP+gvaeTAAABiUlEQVRYhe2WPy9DURiHn/e0FIn/qUi0FQwkTZlIfAJDTWInfAI7A7Gz2YTdavEhEFeCgXBaQRfSgV6peyxC5V6izW1ruL/tvHnP+zz33HuSK3wklpzsEopLgpkFBoAI/sYGrgyyJ6qwoS3rEUAABpITY2+87YP0+Qz9KVlHnHT29PBEEqlUJ06jVUP4pwTKHg11RBPLIOkawwHajGl4DRuYqcb09YUUw7FWV/1c51nZOQVAMDMKGKyGgBccYCTRVrocUvj/tZeTJlVHOACBQCBQd4FwJZumFueJxmOuek5nONjeLWtWRSfgBQfoScTLnlX3VxAIBAKua9gb6yfS1OxqtF+eub/Vvgu4TsALDhBpbvEd7ilQ6wQC/0LAriO/oICr0or98uzdWVLP6YxnT+7m65qe67xnz9n3+qXEk+Nrgln5m7DPEVaVqMIG4P1I1U1GhYubSlvWoyPONJCtJdxRJn19fPwUAsjn7h7ae7t3MCEbiIK0UuHf0i8pABcIW6qhOKdPjjTAO0ACbHMMH2tvAAAAAElFTkSuQmCC">
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
        .logo img { height: 48px; opacity: 0.95; }
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
        <div class="logo"><img src="data:image/png;base64,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" alt="CRElytic" /></div>
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
