"""
Smoke-test the first-deal feedback email end-to-end against Resend.

Reproduces what app.services.email.send_first_deal_feedback_email does, but
imports only the minimal pieces (template + http POST) to avoid pulling in the
full backend dependency tree. The template path and HTTP payload MUST stay in
sync with app/services/email.py.

Usage:
    RESEND_API_KEY=re_xxx python scripts/test_feedback_email.py <recipient_email>
"""

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = HERE.parent / "app" / "templates"

RESEND_API_URL = "https://api.resend.com/emails"

EMAIL_FROM = os.environ.get("EMAIL_FROM", "intelligence@crelytic.ai")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO", "jonathan@crelytic.ai")
FEEDBACK_BASE_URL = os.environ.get("FEEDBACK_BASE_URL", "https://engine.crelytic.ai")


def build_feedback_url(deal_id: str) -> str:
    base = FEEDBACK_BASE_URL.rstrip("/")
    path = f"/engine/feedback?deal={quote(deal_id)}"
    return f"{base}/engine/login?next={quote(path, safe='')}"


def render(first_name: str, deal_name: str, feedback_url: str) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env.get_template("first_deal_feedback.html").render(
        first_name=first_name,
        deal_name=deal_name,
        feedback_url=feedback_url,
    )


def send(to: str, subject: str, html: str, api_key: str) -> tuple[bool, str]:
    payload = {
        "from": EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
        "reply_to": EMAIL_REPLY_TO,
    }
    req = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "crelytic-engine/1.0 (+https://engine.crelytic.ai)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
            return True, data.get("id", "")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    if len(sys.argv) < 2:
        print("Usage: test_feedback_email.py <recipient_email>")
        sys.exit(2)

    recipient = sys.argv[1].strip()
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        print("ERROR: RESEND_API_KEY not set in env")
        sys.exit(2)

    print(f"[test] to:         {recipient}")
    print(f"[test] from:       {EMAIL_FROM}")
    print(f"[test] reply-to:   {EMAIL_REPLY_TO}")
    print(f"[test] key prefix: {api_key[:6]}...")

    feedback_url = build_feedback_url("deal-smoke-test-0001")
    html = render(
        first_name="Jonathan",
        deal_name="Westlake Commerce Center",
        feedback_url=feedback_url,
    )
    print(f"[test] template rendered: {len(html)} chars")
    print(f"[test] feedback URL:      {feedback_url}")

    ok, info = send(
        to=recipient,
        subject="How was your first CRELYTIC deal?",
        html=html,
        api_key=api_key,
    )
    if ok:
        print(f"[test] SENT ok  resend_id={info}")
        sys.exit(0)
    else:
        print(f"[test] FAILED: {info}")
        sys.exit(1)


if __name__ == "__main__":
    main()
