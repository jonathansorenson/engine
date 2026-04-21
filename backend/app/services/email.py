"""Email service — Resend via stdlib urllib (matches tenantiq-campaign pattern)."""

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

RESEND_API_URL = "https://api.resend.com/emails"


def _first_name(full_name: Optional[str], email: str) -> str:
    """Best-effort personalization token."""
    if full_name and full_name.strip():
        return full_name.strip().split()[0]
    return email.split("@")[0].capitalize()


def _render_template(name: str, **context) -> str:
    return _env.get_template(name).render(**context)


def _post_to_resend(payload: dict, api_key: str, timeout: int = 15) -> tuple[bool, str]:
    """POST to Resend's REST API. Returns (ok, message_id_or_error)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Cloudflare fronts api.resend.com and blocks the default Python urllib UA.
            "User-Agent": "crelytic-engine/1.0 (+https://engine.crelytic.ai)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
            return True, data.get("id", "")
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return False, f"HTTP {e.code}: {err_body}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _send_via_resend(to: str, subject: str, html: str, reply_to: Optional[str] = None) -> bool:
    """Send an email via Resend. Returns True on success, False otherwise."""
    if not settings.resend_api_key:
        logger.info("[email] RESEND_API_KEY not set — logging email instead of sending")
        logger.info("[email] To=%s Subject=%s\n%s", to, subject, html[:500])
        return False

    payload = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html,
        "reply_to": reply_to or settings.email_reply_to,
    }

    ok, info = _post_to_resend(payload, settings.resend_api_key)
    if ok:
        logger.info("[email] sent feedback email to %s (id=%s)", to, info)
        return True
    logger.error("[email] Resend send failed: %s", info)
    return False


def send_first_deal_feedback_email(user, deal) -> bool:
    """
    Send the first-deal feedback email to a user.
    `user` is a User SQLAlchemy instance; `deal` is a Deal instance (may be None for manual sends).
    """
    deal_id = getattr(deal, "id", None) if deal is not None else None
    deal_name = (getattr(deal, "name", None) if deal is not None else None) or "your deal"

    base = settings.feedback_base_url.rstrip("/")
    feedback_path = "/engine/feedback"
    if deal_id:
        feedback_path += f"?deal={quote(str(deal_id))}"
    # Wrap in a login ?next= so logged-out recipients land on the form after signing in.
    feedback_url = f"{base}/engine/login?next={quote(feedback_path, safe='')}"

    html = _render_template(
        "first_deal_feedback.html",
        first_name=_first_name(user.name, user.email),
        deal_name=deal_name,
        feedback_url=feedback_url,
    )

    return _send_via_resend(
        to=user.email,
        subject="How was your first CRELYTIC deal?",
        html=html,
    )
