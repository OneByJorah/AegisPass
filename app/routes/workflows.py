"""Workflow management API.

Admin-only. Lists available workflows (all disabled by default), toggles them,
and runs on-demand checks (e.g. send pending password-expiry reminders now).
"""
from __future__ import annotations

import datetime

from flask import Blueprint, request, session

from app import workflows as wf
from app.config import Config
from app.ad import operations
from app.api import ok, fail

bp = Blueprint("workflows_api", __name__)


def _is_admin() -> bool:
    from app.routes.ui import _is_admin as ui_admin
    return ui_admin()


# ── list & toggle ───────────────────────────────────────────────────
@bp.route("/workflows", methods=["GET"])
def list_workflows():
    if not _is_admin():
        return fail("Admin only", code="denied", status=403)
    return ok(wf.list_workflows())


@bp.route("/workflows/<wid>", methods=["POST"])
def toggle_workflow(wid):
    if not _is_admin():
        return fail("Admin only", code="denied", status=403)
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", False))
    if not wf.set_enabled(wid, enabled):
        return fail("Unknown workflow", code="not_found", status=404)
    return ok({"id": wid, "enabled": enabled})


# ── manual run: password expiry reminders ───────────────────────────
@bp.route("/workflows/run-expiry", methods=["POST"])
def run_expiry():
    if not _is_admin():
        return fail("Admin only", code="denied", status=403)
    if not Config.SMTP_ENABLED:
        return fail("Email is not configured (SMTP_ENABLED=false)", code="smtp_off", status=400)
    from app.email import send_expiry_reminder
    days = Config.EXPIRY_REMINDER_DAYS or [7, 3]
    try:
        users = operations.list_users(search="", size_limit=500)
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    sent = 0
    for u in users:
        exp = u.get("passwordExpires")
        if not exp:
            continue
        try:
            delta = (exp - datetime.datetime.utcnow()).days
        except Exception:
            continue
        if delta in days and u.get("mail"):
            if send_expiry_reminder(u, delta):
                sent += 1
    return ok({"sent": sent})


# ── admin: test SMS gateway ───────────────────────────────────────
@bp.route("/sms/test", methods=["POST"])
def test_sms():
    if not _is_admin():
        return fail("Admin only", code="denied", status=403)
    data = request.get_json(silent=True) or {}
    to = (data.get("to") or "").strip()
    if not to:
        return fail("Provide 'to' (mobile number)", code="validation")
    from app.sms import send
    ok_ = send(to, data.get("body", "AegisPass Self-Service: SMS gateway test message."))
    return ok({"sent": ok_, "provider": (Config.SMS_PROVIDER or "none")})
