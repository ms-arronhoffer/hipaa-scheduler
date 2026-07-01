"""SendGrid email adapter.

`send(...)` is a thin wrapper — the caller is responsible for rendering
subject/body via `template_renderer.render()` first. In non-production or when
`SENDGRID_API_KEY` is unset, this logs and records the message but does not
call SendGrid, so tests and dev never spam real inboxes.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings


log = logging.getLogger(__name__)

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


class EmailSendError(RuntimeError):
    pass


async def send(*, to: str, subject: str, html_body: str, text_body: str | None = None) -> str | None:
    """Send an email. Returns provider message id on success, None in dev/no-key mode."""
    key = settings.sendgrid_api_key
    if key is None or settings.app_env != "production":
        log.info("email_send_stub", extra={"to": to, "subject": subject})
        return None

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.email_from, "name": settings.email_from_name},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text_body or ""},
            {"type": "text/html", "value": html_body},
        ],
    }
    headers = {
        "Authorization": f"Bearer {key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(SENDGRID_URL, json=payload, headers=headers)
    if resp.status_code >= 300:
        raise EmailSendError(f"sendgrid {resp.status_code}: {resp.text[:200]}")
    return resp.headers.get("X-Message-Id")
