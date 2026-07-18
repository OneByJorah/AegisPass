"""Audit logging for aegispass.

Every privileged action (user/group/OU create, modify, reset, delete, unlock,
enable/disable) is recorded with: timestamp, actor (sAMAccountName), action,
target DN, source IP, and outcome. Logs are appended to a rotating file and
also kept in a bounded in-memory ring for the live /api/audit feed.

Design: intentionally dependency-free and fail-safe — if logging breaks, the
action still proceeds (we never let the audit sink take down the operation).
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIT_DIR = BASE_DIR / "logs"
AUDIT_DIR.mkdir(exist_ok=True)
AUDIT_FILE = AUDIT_DIR / "audit.log"

# Bounded in-memory ring for the live feed (newest last).
_RING: deque = deque(maxlen=500)
_LOCK = threading.Lock()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(action: str, actor: str, target: str = "", outcome: str = "success",
        detail: str = "", ip: str = "") -> None:
    """Record an auditable event. Fail-safe: never raises."""
    rec = {
        "ts": _now_iso(),
        "action": action,
        "actor": actor or "anonymous",
        "target": target,
        "outcome": outcome,
        "detail": detail,
        "ip": ip,
    }
    line = json.dumps(rec, ensure_ascii=False)
    try:
        with _LOCK:
            _RING.append(rec)
            with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        # Logging must never break the operation.
        pass

    # Fire the "email admin on privileged actions" workflow (fail-safe).
    try:
        from app import workflows as wf
        from app.config import Config
        _PRIV = ("user.create", "user.delete", "user.reset_password",
                 "user.unlock", "user.enable", "user.disable", "group.create",
                 "group.delete", "group.member_add", "group.member_remove",
                 "ou.create", "ou.delete")
        if rec.get("action") in _PRIV and wf.is_enabled("audit_alert_privileged"):
            from app.email import send_audit_alert
            send_audit_alert(rec.get("action", ""), rec.get("actor", ""),
                             rec.get("target", ""), rec.get("outcome", ""),
                             rec.get("detail", ""))
    except Exception:
        pass


def recent(limit: int = 100, actor: str = "") -> list:
    with _LOCK:
        items = list(_RING)
    if actor:
        items = [r for r in items if r.get("actor", "").lower() == actor.lower()]
    return items[-limit:]


def tail_file(lines: int = 200) -> list:
    """Read the last N raw lines from the audit file (for export/debug)."""
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            all_lines = f.read().splitlines()
        return all_lines[-lines:]
    except Exception:
        return []
