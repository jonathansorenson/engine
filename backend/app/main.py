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
