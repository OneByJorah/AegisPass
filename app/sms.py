"""SMS delivery for aegispass.

Provider-agnostic SMS layer. The app talks to a gateway over the LAN; no
per-message fee when self-hosted.

Recommended self-hosted setup (free, your own number):
  • USB GSM/3G/4G modem (Huawei dongle, ~$15-30) + a SIM with SMS plan.
  • Gammu SMSD drives the modem via AT commands.
  • `sms-gammu-gateway` (Docker) exposes a tiny REST API:
        POST http://<gateway>:8080/messages
        { "text": "...", "recipients": ["+13405551234"] }
  See deploy/sms-gateway/README.md for the one-command bring-up.

Providers (set SMS_PROVIDER in .env):
  • "gammu"  — self-hosted Gammu REST gateway (default, no per-msg cost)
  • "twilio"  — Twilio API (needs TWILIO_* creds) if you prefer a SaaS number
  • "mock"    — logs to audit, returns True (dev/testing, no real SMS)
  • "none"    — disabled

All sends are fail-safe: errors are audited, never raise to the caller.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from app.config import Config

_LOCK = threading.Lock()


def _provider() -> str:
    return (getattr(Config, "SMS_PROVIDER", "none") or "none").lower()


def send(to: str, body: str) -> bool:
    """Send an SMS. Returns True if accepted by the provider."""
    prov = _provider()
    if prov in ("none", "", None):
        return False
    if not to or not body:
        return False
    try:
        if prov == "mock":
            return _send_mock(to, body)
        if prov == "gammu":
            return _send_gammu(to, body)
        if prov == "twilio":
            return _send_twilio(to, body)
        return False
    except Exception as e:
        try:
            from app.audit import log
            log("sms.send", "system", target=to, outcome="error", detail=str(e)[:200])
        except Exception:
            pass
        return False


def send_otp(to: str, code: str, purpose: str = "verification") -> bool:
    body = f"AegisPass Self-Service {purpose} code: {code}. Do not share this code."
    return send(to, body)


# ── providers ─────────────────────────────────────────────────────
def _send_mock(to: str, body: str) -> bool:
    from app.audit import log
    log("sms.send", "system", target=to, outcome="mock",
        detail=body[:160])
    return True


def _send_gammu(to: str, body: str) -> bool:
    import requests
    url = getattr(Config, "SMS_GATEWAY_URL", "")
    token = getattr(Config, "SMS_API_TOKEN", "")
    if not url:
        return False
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"text": body, "recipients": [to]}
    with _LOCK:
        r = requests.post(url.rstrip("/") + "/messages", json=payload,
                         headers=headers, timeout=15)
    return r.status_code in (200, 201, 202)


def _send_twilio(to: str, body: str) -> bool:
    from twilio.rest import Client
    sid = getattr(Config, "TWILIO_ACCOUNT_SID", "")
    tok = getattr(Config, "TWILIO_AUTH_TOKEN", "")
    frm = getattr(Config, "TWILIO_FROM", "")
    if not (sid and tok and frm):
        return False
    client = Client(sid, tok)
    client.messages.create(to=to, from_=frm, body=body)
    return True
