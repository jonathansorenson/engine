"""Billing routes — signup, Stripe Checkout, webhook, portal."""

import uuid
import time
import threading
from typing import Optional

import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.routes.admin import hash_password

router = APIRouter(tags=["billing"])

# ═══════════════════════════════════════════════════════════════
# PENDING SIGNUP STORE (in-memory, 1-hour TTL)
# ═══════════════════════════════════════════════════════════════

_pending_signups: dict = {}
_SIGNUP_TTL = 3600  # 1 hour


def _cleanup_expired():
    """Remove expired pending signups."""
    now = time.time()
    expired = [k for k, v in _pending_signups.items() if now - v["created_at"] > _SIGNUP_TTL]
    for k in expired:
        del _pending_signups[k]


# ═══════════════════════════════════════════════════════════════
# TIER CONFIG
# ═══════════════════════════════════════════════════════════════

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from app.models.deal import Deal

# Monthly upload limits (how many new deals per billing month)
MONTHLY_LIMITS = {
    "starter": 5,
    "pro": 25,
    "unlimited": 999,
    "free": 25,
    "enterprise": 999,
    "admin": 999,
}

# Total deal storage caps (max deals a user can keep at once)
TOTAL_LIMITS = {
    "starter": 50,
    "pro": 200,
    "unlimited": 9999,
    "free": 200,
    "enterprise": 9999,
    "admin": 9999,
}


def _get_billing_cycle_start(user: User) -> datetime:
    """Get the start of the user's current billing month.
    Uses the user's created_at day-of-month as the anchor.
    Returns naive UTC datetime to match Deal.created_at format."""
    now = datetime.utcnow()  # naive UTC — must match Deal.created_at which uses datetime.utcnow
    anchor_day = min(user.created_at.day, 28)  # Cap at 28 to avoid month-length issues

    # Start of current billing cycle
    cycle_start = now.replace(day=anchor_day, hour=0, minute=0, second=0, microsecond=0)
    if cycle_start > now:
        cycle_start = cycle_start - relativedelta(months=1)
    return cycle_start


def _get_billing_cycle_reset(user: User) -> datetime:
    """Get the reset date (start of next billing month)."""
    cycle_start = _get_billing_cycle_start(user)
    return cycle_start + relativedelta(months=1)


def get_monthly_limit(user: User) -> int:
    """Return monthly upload limit for a user."""
    if not user:
        return 0
    tier = user.subscription_tier or "admin"
    # Admin-created users without stripe = unlimited
    if not user.stripe_customer_id and tier in ("admin",):
        return 999
    if user.stripe_customer_id and user.subscription_status not in ("active", "trialing"):
        return 0  # Expired subscription
    return MONTHLY_LIMITS.get(tier, 0)


def get_total_limit(user: User) -> int:
    """Return total deal storage cap for a user."""
    if not user:
        return 0
    tier = user.subscription_tier or "admin"
    if not user.stripe_customer_id and tier in ("admin",):
        return 9999
    if user.stripe_customer_id and user.subscription_status not in ("active", "trialing"):
        return 0
    return TOTAL_LIMITS.get(tier, 0)


def get_monthly_used(db, user: User) -> int:
    """Count deals created by this user in the current billing month."""
    if not user:
        return 0
    cycle_start = _get_billing_cycle_start(user)
    return db.query(func.count(Deal.id)).filter(
        Deal.fund_id == user.email,
        Deal.created_at >= cycle_start,
    ).scalar() or 0


# Legacy compatibility wrapper
def get_deal_limit_for_user(user: User) -> int:
    """Return the monthly upload limit (legacy compat)."""
    return get_monthly_limit(user)


# ═══════════════════════════════════════════════════════════════
# SIGNUP PAGE HTML
# ═══════════════════════════════════════════════════════════════

SIGNUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Create your CRELYTIC Engine account. AI-powered CRE deal underwriting starting at $6.99/month. Full DCF, waterfall, and investment memos in minutes.">
    <meta name="robots" content="noindex, nofollow">
    <link rel="canonical" href="https://engine.crelytic.ai/engine/signup">
    <meta property="og:title" content="Sign Up | CRELYTIC Engine">
    <meta property="og:description" content="AI-powered CRE deal underwriting starting at $6.99/month. Full DCF, waterfall, and investment memos in minutes.">
    <meta property="og:url" content="https://engine.crelytic.ai/engine/signup">
    <meta property="og:image" content="https://engine.crelytic.ai/og-image.png">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="CRELYTIC">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Sign Up | CRELYTIC Engine">
    <meta name="twitter:description" content="AI-powered CRE deal underwriting starting at $6.99/month.">
    <meta name="twitter:image" content="https://engine.crelytic.ai/og-image.png">
    <title>Sign Up | CRELYTIC Engine — CRE Deal Underwriting</title>
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
            background: rgba(255,255,255,0.06); backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;
            padding: 40px; width: 480px; max-width: 95vw;
        }
        .logo { text-align: center; margin-bottom: 8px; }
        .logo img { height: 32px; }
        h1 { text-align: center; font-size: 22px; font-weight: 600; margin-bottom: 4px; }
        .subtitle { text-align: center; color: #94a3b8; font-size: 14px; margin-bottom: 24px; }
        .error { display: none; background: #ef444433; border: 1px solid #ef4444; color: #fca5a5;
                 padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 16px; }
        .error.show { display: block; }
        .success { display: none; background: #22c55e33; border: 1px solid #22c55e; color: #86efac;
                   padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 16px; }
        .success.show { display: block; }
        label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 6px; margin-top: 14px; }
        input[type="text"], input[type="email"], input[type="password"] {
            width: 100%; padding: 10px 14px; border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.15); background: rgba(255,255,255,0.05);
            color: #e2e8f0; font-size: 14px; outline: none; transition: border 0.2s;
        }
        input:focus { border-color: #60a5fa; }
        .tiers { display: flex; gap: 10px; margin-top: 8px; }
        .tier-card {
            flex: 1; padding: 14px; border-radius: 10px; cursor: pointer;
            border: 2px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.03);
            text-align: center; transition: all 0.2s;
        }
        .tier-card:hover { border-color: rgba(96,165,250,0.4); }
        .tier-card.selected { border-color: #60a5fa; background: rgba(96,165,250,0.1); }
        .tier-card input[type="radio"] { display: none; }
        .tier-name { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
        .tier-price { color: #94a3b8; font-size: 13px; }
        .tier-deals { color: #60a5fa; font-size: 12px; margin-top: 4px; }
        .tier-card.enterprise .tier-price { color: #a78bfa; }
        button[type="submit"] {
            width: 100%; padding: 12px; border-radius: 8px; border: none;
            background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff;
            font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 20px;
            transition: opacity 0.2s;
        }
        button[type="submit"]:hover { opacity: 0.9; }
        button[type="submit"]:disabled { opacity: 0.5; cursor: not-allowed; }
        .login-link { text-align: center; margin-top: 16px; font-size: 13px; color: #94a3b8; }
        .login-link a { color: #60a5fa; text-decoration: none; }
        .contact-note { display: none; text-align: center; color: #a78bfa; font-size: 13px;
                        margin-top: 16px; padding: 12px; border-radius: 8px;
                        background: rgba(167,139,250,0.1); border: 1px solid rgba(167,139,250,0.2); }
        .contact-note.show { display: block; }
        .contact-note a { color: #c4b5fd; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">
            <svg width="32" height="32" viewBox="0 0 32 32"><circle cx="16" cy="16" r="15" fill="none" stroke="#60a5fa" stroke-width="1.5"/><text x="16" y="21" text-anchor="middle" fill="#60a5fa" font-size="14" font-weight="700" font-family="sans-serif">C</text></svg>
        </div>
        <h1>Create Your Account</h1>
        <p class="subtitle">Start analyzing CRE deals in minutes</p>
        <div class="error {error_class}" id="err">{error_msg}</div>
        <div class="success {success_class}" id="suc">{success_msg}</div>
        <form method="POST" action="/engine/signup" id="signupForm">
            <label>Full Name</label>
            <input type="text" name="name" placeholder="Jane Smith" required value="{name_val}" />
            <label>Company</label>
            <input type="text" name="company" placeholder="Acme Capital" required value="{company_val}" />
            <label>Email</label>
            <input type="email" name="email" placeholder="jane@acme.com" required value="{email_val}" />
            <label>Password</label>
            <input type="password" name="password" placeholder="Min 8 characters" required minlength="8" />
            <label>Confirm Password</label>
            <input type="password" name="password_confirm" placeholder="Confirm password" required minlength="8" />
            <label>Select Plan</label>
            <div class="tiers">
                <label class="tier-card {starter_sel}" onclick="selectTier(this,'starter')">
                    <input type="radio" name="tier" value="starter" {starter_chk} />
                    <div class="tier-name">Starter</div>
                    <div class="tier-price">$6.99/mo</div>
                    <div class="tier-deals">5 deals</div>
                </label>
                <label class="tier-card {pro_sel}" onclick="selectTier(this,'pro')">
                    <input type="radio" name="tier" value="pro" {pro_chk} />
                    <div class="tier-name">Pro</div>
                    <div class="tier-price">$11.99/mo</div>
                    <div class="tier-deals">25 deals</div>
                </label>
                <label class="tier-card {unlimited_sel}" onclick="selectTier(this,'unlimited')" style="border-color: rgba(244,114,182,0.3); position: relative;">
                    <input type="radio" name="tier" value="unlimited" {unlimited_chk} />
                    <div class="tier-name" style="color: #f472b6;">Unlimited</div>
                    <div class="tier-price">$20/mo</div>
                    <div class="tier-deals" style="color: #f472b6;">Unlimited deals</div>
                    <div style="position: absolute; top: -8px; right: -8px; background: linear-gradient(135deg, #ec4899, #8b5cf6); color: #fff; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Popular</div>
                </label>
                <label class="tier-card enterprise {ent_sel}" onclick="selectTier(this,'enterprise')">
                    <input type="radio" name="tier" value="enterprise" {ent_chk} />
                    <div class="tier-name">Enterprise</div>
                    <div class="tier-price">Custom</div>
                    <div class="tier-deals">Unlimited</div>
                </label>
            </div>
            <div class="contact-note" id="contactNote">
                Enterprise plans are custom-priced. <a href="mailto:jonathan_sorenson@losttree.com">Contact us</a> to get started.
            </div>
            <button type="submit" id="submitBtn">Continue to Payment</button>
        </form>
        <div class="login-link">Already have an account? <a href="/engine/login">Sign in</a></div>
    </div>
    <script>
        function selectTier(el, tier) {
            document.querySelectorAll('.tier-card').forEach(c => c.classList.remove('selected'));
            el.classList.add('selected');
            el.querySelector('input[type=radio]').checked = true;
            const btn = document.getElementById('submitBtn');
            const note = document.getElementById('contactNote');
            if (tier === 'enterprise') {
                btn.disabled = true;
                btn.textContent = 'Contact Us for Enterprise';
                note.classList.add('show');
            } else {
                btn.disabled = false;
                btn.textContent = 'Continue to Payment';
                note.classList.remove('show');
            }
        }
        // Validate passwords match on submit
        document.getElementById('signupForm').addEventListener('submit', function(e) {
            const pw = this.querySelector('input[name=password]').value;
            const pw2 = this.querySelector('input[name=password_confirm]').value;
            if (pw !== pw2) {
                e.preventDefault();
                document.getElementById('err').textContent = 'Passwords do not match.';
                document.getElementById('err').classList.add('show');
            }
        });
    </script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════

def _render_signup(error: str = "", success: str = "", name: str = "",
                   company: str = "", email: str = "", tier: str = "starter") -> str:
    """Render the signup page HTML with optional error/success messages."""
    html = SIGNUP_HTML
    html = html.replace("{error_class}", "show" if error else "")
    html = html.replace("{error_msg}", error)
    html = html.replace("{success_class}", "show" if success else "")
    html = html.replace("{success_msg}", success)
    html = html.replace("{name_val}", name)
    html = html.replace("{company_val}", company)
    html = html.replace("{email_val}", email)
    html = html.replace("{starter_sel}", "selected" if tier == "starter" else "")
    html = html.replace("{pro_sel}", "selected" if tier == "pro" else "")
    html = html.replace("{unlimited_sel}", "selected" if tier == "unlimited" else "")
    html = html.replace("{ent_sel}", "selected" if tier == "enterprise" else "")
    html = html.replace("{starter_chk}", "checked" if tier == "starter" else "")
    html = html.replace("{pro_chk}", "checked" if tier == "pro" else "")
    html = html.replace("{unlimited_chk}", "checked" if tier == "unlimited" else "")
    html = html.replace("{ent_chk}", "checked" if tier == "enterprise" else "")
    return html


@router.get("/engine/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Serve the signup form."""
    canceled = request.query_params.get("canceled")
    error = "Payment was canceled. Please try again." if canceled else ""
    return HTMLResponse(content=_render_signup(error=error))


@router.post("/engine/signup")
async def signup_submit(request: Request):
    """Validate signup form, create Stripe Checkout session, redirect to Stripe."""
    form = await request.form()
    name = (form.get("name", "") or "").strip()
    company = (form.get("company", "") or "").strip()
    email = (form.get("email", "") or "").lower().strip()
    password = form.get("password", "") or ""
    password_confirm = form.get("password_confirm", "") or ""
    tier = form.get("tier", "starter") or "starter"

    # Validate
    if not all([name, company, email, password]):
        return HTMLResponse(content=_render_signup(
            error="All fields are required.", name=name, company=company, email=email, tier=tier
        ), status_code=400)

    if password != password_confirm:
        return HTMLResponse(content=_render_signup(
            error="Passwords do not match.", name=name, company=company, email=email, tier=tier
        ), status_code=400)

    if len(password) < 10:
        return HTMLResponse(content=_render_signup(
            error="Password must be at least 10 characters.", name=name, company=company, email=email, tier=tier
        ), status_code=400)
    if not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        return HTMLResponse(content=_render_signup(
            error="Password must contain at least one uppercase letter and one number.", name=name, company=company, email=email, tier=tier
        ), status_code=400)

    if tier not in ("starter", "pro", "unlimited"):
        return HTMLResponse(content=_render_signup(
            error="Please select a plan.", name=name, company=company, email=email, tier=tier
        ), status_code=400)

    # Check email not taken
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return HTMLResponse(content=_render_signup(
                error="An account with this email already exists.",
                name=name, company=company, email=email, tier=tier
            ), status_code=400)
    finally:
        db.close()

    # Check Stripe config
    if not settings.stripe_secret_key:
        return HTMLResponse(content=_render_signup(
            error="Payment system is not configured. Please contact support.",
            name=name, company=company, email=email, tier=tier
        ), status_code=500)

    # Store pending signup
    _cleanup_expired()
    token = str(uuid.uuid4())
    _pending_signups[token] = {
        "name": name,
        "company": company,
        "email": email,
        "hashed_password": hash_password(password),
        "tier": tier,
        "created_at": time.time(),
    }

    # Create Stripe Checkout Session
    stripe.api_key = settings.stripe_secret_key
    _price_ids = {
        "starter": settings.stripe_starter_price_id,
        "pro": settings.stripe_pro_price_id,
        "unlimited": settings.stripe_unlimited_price_id,
    }
    price_id = _price_ids.get(tier, settings.stripe_pro_price_id)

    try:
        base_url = str(request.base_url).rstrip("/")
        # Use X-Forwarded headers if behind proxy
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        forwarded_host = request.headers.get("x-forwarded-host", "")
        if forwarded_host:
            base_url = f"{forwarded_proto or 'https'}://{forwarded_host}"

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=email,
            metadata={"signup_token": token},
            success_url=f"{base_url}/engine/login?signup=success",
            cancel_url=f"{base_url}/engine/signup?canceled=true",
        )
        return RedirectResponse(url=checkout_session.url, status_code=303)
    except stripe.error.StripeError as e:
        return HTMLResponse(content=_render_signup(
            error=f"Payment error: {str(e)}", name=name, company=company, email=email, tier=tier
        ), status_code=500)


# ═══════════════════════════════════════════════════════════════
# STRIPE WEBHOOK
# ═══════════════════════════════════════════════════════════════

@router.post("/engine/api/v1/billing/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        return JSONResponse({"error": "Webhook not configured"}, status_code=500)

    stripe.api_key = settings.stripe_secret_key
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data)

    return JSONResponse({"status": "ok"})


def _handle_checkout_completed(session: dict):
    """Create user account or upgrade existing user after successful checkout."""
    metadata = session.get("metadata", {})
    customer_id = session.get("customer", "")
    subscription_id = session.get("subscription", "")

    # Case 1: Existing user upgrading from free/admin tier
    upgrade_email = metadata.get("upgrade_user_email")
    if upgrade_email:
        tier = metadata.get("tier", "pro")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == upgrade_email).first()
            if user:
                user.stripe_customer_id = customer_id
                user.stripe_subscription_id = subscription_id
                user.subscription_tier = tier
                user.subscription_status = "active"
                db.commit()
                print(f"Webhook: Upgraded {upgrade_email} to {tier}")
            else:
                print(f"Webhook: Upgrade user {upgrade_email} not found")
        except Exception as e:
            print(f"Webhook: Error upgrading user: {e}")
            db.rollback()
        finally:
            db.close()
        return

    # Case 2: New user signup
    token = metadata.get("signup_token")
    if not token or token not in _pending_signups:
        print(f"Webhook: No pending signup for token {token}")
        return

    signup = _pending_signups.pop(token)

    db = SessionLocal()
    try:
        # Double-check email not taken (race condition guard)
        existing = db.query(User).filter(User.email == signup["email"]).first()
        if existing:
            print(f"Webhook: User {signup['email']} already exists, skipping")
            return

        user = User(
            email=signup["email"],
            hashed_password=signup["hashed_password"],
            name=signup["name"],
            company_name=signup["company"],
            role="analyst",
            fund_id=signup["email"],
            subscription_tier=signup["tier"],
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            subscription_status="active",
        )
        db.add(user)
        db.commit()
        print(f"Webhook: Created user {signup['email']} (tier={signup['tier']})")
    except Exception as e:
        print(f"Webhook: Error creating user: {e}")
        db.rollback()
    finally:
        db.close()


def _handle_subscription_updated(subscription: dict):
    """Update subscription status and tier when Stripe notifies us."""
    customer_id = subscription.get("customer", "")
    status = subscription.get("status", "")

    # Extract the new tier from the subscription's current price
    items = subscription.get("items", {}).get("data", [])
    new_price_id = items[0]["price"]["id"] if items else None
    _price_to_tier = {
        settings.stripe_starter_price_id: "starter",
        settings.stripe_pro_price_id: "pro",
        settings.stripe_unlimited_price_id: "unlimited",
    }
    new_tier = _price_to_tier.get(new_price_id) if new_price_id else None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.subscription_status = status
            if new_tier:
                user.subscription_tier = new_tier
                print(f"Webhook: Updated {user.email} subscription_tier={new_tier} subscription_status={status}")
            else:
                print(f"Webhook: Updated {user.email} subscription_status={status}")
            db.commit()
    except Exception as e:
        print(f"Webhook: Error updating subscription: {e}")
        db.rollback()
    finally:
        db.close()


def _handle_subscription_deleted(subscription: dict):
    """Mark subscription as canceled."""
    customer_id = subscription.get("customer", "")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.subscription_status = "canceled"
            db.commit()
            print(f"Webhook: Canceled subscription for {user.email}")
    except Exception as e:
        print(f"Webhook: Error canceling subscription: {e}")
        db.rollback()
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# BILLING PORTAL
# ═══════════════════════════════════════════════════════════════

@router.post("/engine/api/v1/billing/portal")
async def billing_portal(request: Request):
    """Create a Stripe Customer Portal session for subscription management."""
    email = getattr(request.state, "user_email", None)
    if not email:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not user.stripe_customer_id:
            return JSONResponse({"detail": "No subscription found"}, status_code=404)

        stripe.api_key = settings.stripe_secret_key
        base_url = str(request.base_url).rstrip("/")
        forwarded_host = request.headers.get("x-forwarded-host", "")
        if forwarded_host:
            proto = request.headers.get("x-forwarded-proto", "https")
            base_url = f"{proto}://{forwarded_host}"

        portal = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{base_url}/engine",
        )
        return JSONResponse({"url": portal.url})
    finally:
        db.close()


@router.post("/engine/api/v1/billing/upgrade")
async def upgrade_plan(request: Request):
    """Smart upgrade: Stripe users → portal, free/admin users → new checkout session."""
    email = getattr(request.state, "user_email", None)
    if not email:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    target_tier = body.get("tier", "pro")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return JSONResponse({"detail": "User not found"}, status_code=404)

        stripe.api_key = settings.stripe_secret_key
        base_url = str(request.base_url).rstrip("/")
        forwarded_host = request.headers.get("x-forwarded-host", "")
        if forwarded_host:
            proto = request.headers.get("x-forwarded-proto", "https")
            base_url = f"{proto}://{forwarded_host}"

        _price_ids = {
            "starter": settings.stripe_starter_price_id,
            "pro": settings.stripe_pro_price_id,
            "unlimited": settings.stripe_unlimited_price_id,
        }

        # If user already has Stripe → targeted plan-switch via portal
        if user.stripe_customer_id:
            target_price_id = _price_ids.get(target_tier, settings.stripe_pro_price_id)
            if user.stripe_subscription_id:
                try:
                    sub = stripe.Subscription.retrieve(user.stripe_subscription_id)
                    item_id = sub["items"]["data"][0]["id"]
                    portal = stripe.billing_portal.Session.create(
                        customer=user.stripe_customer_id,
                        return_url=f"{base_url}/engine?upgraded=true",
                        flow_data={
                            "type": "subscription_update_confirm",
                            "subscription_update_confirm": {
                                "subscription": user.stripe_subscription_id,
                                "items": [{"id": item_id, "price": target_price_id}],
                            },
                        },
                    )
                    return JSONResponse({"url": portal.url, "method": "portal"})
                except stripe.error.StripeError:
                    # Fallback to generic portal if flow_data fails
                    portal = stripe.billing_portal.Session.create(
                        customer=user.stripe_customer_id,
                        return_url=f"{base_url}/engine",
                    )
                    return JSONResponse({"url": portal.url, "method": "portal"})
            else:
                portal = stripe.billing_portal.Session.create(
                    customer=user.stripe_customer_id,
                    return_url=f"{base_url}/engine",
                )
                return JSONResponse({"url": portal.url, "method": "portal"})

        # Free/admin user without Stripe → create checkout session
        price_id = _price_ids.get(target_tier, settings.stripe_pro_price_id)

        # Create a Stripe customer first
        customer = stripe.Customer.create(email=user.email, name=user.name or "")

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer=customer.id,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"upgrade_user_email": user.email, "tier": target_tier},
            success_url=f"{base_url}/engine?upgraded=true",
            cancel_url=f"{base_url}/engine?upgrade_canceled=true",
        )
        return JSONResponse({"url": checkout_session.url, "method": "checkout"})
    except stripe.error.StripeError as e:
        return JSONResponse({"detail": f"Stripe error: {str(e)}"}, status_code=500)
    finally:
        db.close()
