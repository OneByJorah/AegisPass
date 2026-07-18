"""Workflow engine for aegispass.

A *workflow* is a named, toggleable automation that fires on an event
(password reset requested, account created, privileged action, password
expiring, account locked, etc.).

Security model:
- ALL workflows are DISABLED by default. An admin must explicitly activate
  each one from the admin-only "Workflows" view.
- Only Domain Admins (is_admin) can read/modify workflow state.
- Workflow state persists to a JSON file so it survives restarts.
- Each workflow's `enabled` flag gates execution; the global engine can also
  be hard-disabled via SMTP_ENABLED (no mail server -> no emails anyway).

This module is dependency-free and fail-safe: a broken workflow never
interrupts the user-facing operation that triggered it.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "config" / "workflows.json"

_LOCK = threading.Lock()

# Registry of available workflows. `enabled` is the *default*; the persisted
# state in STATE_FILE overrides it at load time.
_REGISTRY = [
    {
        "id": "email_password_reset",
        "name": "Email password reset code",
        "description": "Email the self-service password reset verification code to the user's address on file (AD mail attribute).",
        "category": "Self-service",
        "enabled": False,
    },
    {
        "id": "email_account_created",
        "name": "Email new account credentials",
        "description": "Email newly created users their username and temporary password.",
        "category": "Provisioning",
        "enabled": False,
    },
    {
        "id": "audit_alert_privileged",
        "name": "Email admin on privileged actions",
        "description": "Email Jhonattan.jimenez@example.com whenever a privileged action (create/reset/delete/unlock) is performed.",
        "category": "Security",
        "enabled": False,
    },
    {
        "id": "email_expiry_reminder",
        "name": "Password expiry reminders",
        "description": "Email users when their password is about to expire (default 7 and 3 days before).",
        "category": "Lifecycle",
        "enabled": False,
    },
    {
        "id": "email_account_locked",
        "name": "Email account locked notice",
        "description": "Email a user when their account becomes locked out.",
        "category": "Lifecycle",
        "enabled": False,
    },
    {
        "id": "email_welcome_firstlogin",
        "name": "Welcome email on first sign-in",
        "description": "Email a welcome message the first time a user signs in.",
        "category": "Lifecycle",
        "enabled": False,
    },
    {
        "id": "email_inactive_90d",
        "name": "Inactive account report (90 days)",
        "description": "Email admins a weekly list of accounts inactive for 90+ days for review.",
        "category": "Hygiene",
        "enabled": False,
    },
    {
        "id": "email_breach_notify",
        "name": "Breached/disabled-account notice",
        "description": "Email admins when an account is disabled or flagged, for incident awareness.",
        "category": "Security",
        "enabled": False,
    },
]


def _load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def list_workflows() -> list:
    """Return workflows with their current enabled state merged in."""
    state = _load_state()
    out = []
    for w in _REGISTRY:
        w = dict(w)
        w["enabled"] = bool(state.get(w["id"], w["enabled"]))
        out.append(w)
    return out


def is_enabled(wid: str) -> bool:
    state = _load_state()
    for w in _REGISTRY:
        if w["id"] == wid:
            return bool(state.get(wid, w["enabled"]))
    return False


def set_enabled(wid: str, enabled: bool) -> bool:
    state = _load_state()
    if not any(w["id"] == wid for w in _REGISTRY):
        return False
    state[wid] = bool(enabled)
    _save_state(state)
    return True


def run(wid: str, fn: Callable[[], None]) -> None:
    """Run a workflow's email action if it is enabled. Fail-safe wrapper."""
    try:
        if not is_enabled(wid):
            return
        fn()
    except Exception:
        # Never let a workflow break the triggering operation.
        pass
