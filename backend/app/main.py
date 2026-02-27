import os
import hmac
import hashlib
import time
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db
from app.auth.middleware import add_fund_id_to_request
from app.routes import deals_router, chat_router

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


def _verify(signed: str) -> bool:
    """Verify a signed cookie value."""
    if not signed or "." not in signed:
        return False
    value, sig = signed.rsplit(".", 1)
    expected = hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()[:16]
    return hmac.compare_digest(sig, expected)


# ═══════════════════════════════════════════════════════════════
# PASSWORD GATE MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

class PasswordGateMiddleware(BaseHTTPMiddleware):
    """Require password authentication for /engine/* routes."""

    # Paths that don't require auth
    PUBLIC_PATHS = {"/health", "/engine/login", "/", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in self.PUBLIC_PATHS or not path.startswith("/engine"):
            return await call_next(request)

        # Check session cookie
        session = request.cookies.get(COOKIE_NAME, "")
        if _verify(session):
            return await call_next(request)

        # Not authenticated — redirect to login (for browser) or 401 (for API)
        if "api" in path:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return RedirectResponse(url="/engine/login", status_code=302)


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
        input[type=password] {
            width: 100%; padding: 0.9rem 1.2rem; border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; background: rgba(255,255,255,0.05); color: white;
            font-size: 1rem; outline: none; transition: border 0.2s;
            margin-bottom: 1rem;
        }
        input[type=password]:focus { border-color: #00BFA5; }
        input[type=password]::placeholder { color: #64748b; }
        button {
            width: 100%; padding: 0.9rem; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #00BFA5, #00897B); color: white;
            font-size: 1rem; font-weight: 700; cursor: pointer; transition: opacity 0.2s;
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
            <input type="password" name="password" placeholder="Enter access password" autofocus required />
            <button type="submit">Access Engine</button>
        </form>
    </div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize app on startup, cleanup on shutdown."""
    init_db()
    os.makedirs(settings.upload_dir, exist_ok=True)
    print(f"Application started. Upload directory: {settings.upload_dir}")
    print(f"Engine at: http://localhost:8000/engine")
    print(f"Login at:  http://localhost:8000/engine/login")
    yield
    print("Application shutting down")


app = FastAPI(
    title="CRE Deal Underwriting Tool",
    description="Backend API for commercial real estate deal analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# Password gate middleware (must be added BEFORE CORS)
app.add_middleware(PasswordGateMiddleware)

# CORS middleware
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (fund ID injection)
app.middleware("http")(add_fund_id_to_request)

# Register API routers under /engine prefix
app.include_router(deals_router, prefix="/engine")
app.include_router(chat_router, prefix="/engine")


# ═══════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy", "service": "CRE Lytic Engine", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint — redirect to engine or show info."""
    return RedirectResponse(url="/engine")


@app.get("/engine/login", response_class=HTMLResponse)
async def login_page():
    """Serve the password login form."""
    html = LOGIN_HTML.replace("{error_class}", "").replace("{error_msg}", "")
    return HTMLResponse(content=html)


@app.post("/engine/login")
async def login_submit(request: Request):
    """Validate password and set session cookie."""
    form = await request.form()
    password = form.get("password", "")

    if password == settings.engine_password:
        # Set signed session cookie
        token = _sign(f"authenticated:{int(time.time())}")
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

    # Wrong password — re-render login with error
    html = LOGIN_HTML.replace("{error_class}", "show").replace("{error_msg}", "Incorrect password. Please try again.")
    return HTMLResponse(content=html, status_code=401)


@app.get("/engine/logout")
async def logout():
    """Clear session cookie."""
    response = RedirectResponse(url="/engine/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/engine", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend dashboard (password-protected)."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(), status_code=200)
    return HTMLResponse(
        content="<h1>Frontend not found</h1><p>Place index.html in the frontend/ directory.</p>",
        status_code=404,
    )


# Keep /app as an alias for backward compatibility during local dev
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend_legacy():
    """Legacy route — redirects to /engine."""
    return RedirectResponse(url="/engine", status_code=301)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
