"""JSON API for AD management.

All routes require an authenticated session. Responses use a consistent
envelope:  {"ok": bool, "data": ..., "error": str|None, "code": str|None}.
Mutating routes are audited via app.api.audit_action.
"""
from __future__ import annotations

import functools
from flask import Blueprint, request, session, jsonify

from app.api import ok, fail, audit_action
from app.ad import operations as op
from app.ad.operations import is_domain_admin
from app import audit

bp = Blueprint("api", __name__)


def login_required(f):
    @functools.wraps(f)
    def wrapper(*a, **k):
        if not session.get("user"):
            return fail("authentication required", code="auth", status=401)
        return f(*a, **k)
    return wrapper


def _user():
    return session.get("user", {})


# ───────────────────────────── USERS ─────────────────────────────
@bp.route("/user-stats", methods=["GET"])
@login_required
def user_stats():
    """Aggregate counts for the dashboard."""
    try:
        total = op.count_users()
        groups = op.count_groups()
        all_users = op.list_users(search="", size_limit=500)
        enabled = disabled = locked = 0
        for u in all_users:
            uac = u.get("userAccountControl", 0)
            if uac & 2: disabled += 1
            else: enabled += 1
            if u.get("locked"): locked += 1
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    return ok({"total": total, "enabled": enabled, "disabled": disabled, "locked": locked, "groups": groups})


@bp.route("/device-stats", methods=["GET"])
@login_required
def device_stats():
    """Non-sensitive aggregate device/computer status."""
    try:
        data = op.device_status()
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    return ok(data)


@bp.route("/users", methods=["GET"])
@login_required
def list_users():
    search = request.args.get("q", "")
    scope = request.args.get("scope", "subtree")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(500, max(1, int(request.args.get("per_page", 100))))
    try:
        all_users = op.list_users(search=search, scope=scope)
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    total = len(all_users)
    start = (page - 1) * per_page
    return ok(all_users[start:start + per_page],
              meta={"total": total, "page": page, "per_page": per_page})


@bp.route("/users/<path:dn>", methods=["GET"])
@login_required
def get_user(dn):
    try:
        u = op.get_user(dn)
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    if not u:
        return fail("not found", code="not_found", status=404)
    return ok(u)


@bp.route("/users", methods=["POST"])
@login_required
@audit_action("user.create", target_getter=lambda resp, *a, **k: (request.get_json(force=True, silent=True) or {}).get("dn") or "")
def create_user():
    data = request.get_json(force=True) if request.is_json else request.form
    dn = data.get("dn")
    if not dn:
        return fail("dn required", code="validation")
    pw = data.get("password", "")
    if not pw:
        from app.password_generator import generate_password
        # derive a school code from attrs if present (e.g. department/ou hint)
        hint = (data.get("attrs", {}) or {}).get("department", "")
        pw = generate_password(hint)
        auto = True
    else:
        auto = False
    u = op.create_user(dn, data.get("attrs", {}), pw,
                       force_change=bool(data.get("force_change", True)))
    # Workflow: email new account credentials (fail-safe, opt-in)
    try:
        from app import workflows as wf
        from app.email import send_welcome
        if wf.is_enabled("email_account_created") and pw:
            wf.run("email_account_created", lambda: send_welcome(u, pw))
    except Exception:
        pass
    return ok({"user": u, "generated_password": pw if auto else None}), 201


@bp.route("/users/<path:dn>", methods=["PATCH"])
@login_required
@audit_action("user.update", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def update_user(dn):
    data = request.get_json(force=True)
    u = op.update_user(dn, data.get("changes", {}))
    return ok(u)


@bp.route("/users/<path:dn>/enable", methods=["POST"])
@login_required
@audit_action("user.set_enabled", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def enable_user(dn):
    enabled = bool((request.get_json(force=True, silent=True) or {}).get("enabled", True))
    u = op.set_user_enabled(dn, enabled)
    return ok(u)


@bp.route("/users/<path:dn>/unlock", methods=["POST"])
@login_required
@audit_action("user.unlock", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def unlock_user(dn):
    u = op.unlock_user(dn)
    return ok(u)


@bp.route("/users/<path:dn>", methods=["DELETE"])
@login_required
@audit_action("user.delete", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def delete_user(dn):
    op.delete_user(dn)
    return ok({"deleted": dn})


# ─────────────────────────── PASSWORDS ───────────────────────────
@bp.route("/users/<path:dn>/password", methods=["POST"])
@login_required
@audit_action("user.password_reset", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def reset_password(dn):
    data = request.get_json(force=True)
    new_pw = data.get("new_password")
    auto = False
    if not new_pw:
        from app.password_generator import generate_password
        new_pw = generate_password()
        auto = True
    op.reset_password(dn, new_pw, force_change=bool(data.get("force_change", True)))
    # Workflow: email reset notice (fail-safe, opt-in)
    try:
        from app import workflows as wf
        from app.email import send_password_reset_notice
        if wf.is_enabled("email_password_reset") and auto:
            u = op.get_user(dn)
            wf.run("email_password_reset", lambda: send_password_reset_notice(u, new_pw))
    except Exception:
        pass
    return ok({"reset": dn, "generated_password": new_pw if auto else None})


@bp.route("/self/password", methods=["POST"])
@login_required
@audit_action("self.password_change")
def self_change():
    data = request.get_json(force=True)
    sam = _user().get("sAMAccountName", "")
    dn = _user().get("dn")
    if not dn:
        users = op.list_users(search=sam, size_limit=2)
        for u in users:
            if u.get("sAMAccountName", "").lower() == sam.lower():
                dn = u.get("dn"); break
    if not dn:
        return fail("user not resolved", code="not_found", status=404)
    try:
        op.change_password(dn, data.get("old_password", ""), data.get("new_password", ""))
    except PermissionError as e:
        return fail(str(e), code="denied", status=403)
    except Exception as e:
        msg = str(e)
        if "52e" in msg or "invalid credentials" in msg.lower():
            return fail("Current password is incorrect.", code="bad_old_pw", status=400)
        return fail(msg, code="ldap", status=500)
    return ok({"changed": dn})


# Self-service password reset REQUEST: user types username, gets email code.
@bp.route("/self/reset-request", methods=["POST"])
def reset_request():
    data = request.get_json(force=True) or {}
    identifier = (data.get("username") or "").strip()
    if not identifier:
        return fail("username required", code="validation")
    users = op.list_users(search=identifier, size_limit=10)
    target = None
    for u in users:
        if (u.get("sAMAccountName", "").lower() == identifier.lower()
                or u.get("userPrincipalName", "").lower() == identifier.lower()
                or u.get("mail", "").lower() == identifier.lower()):
            target = u
            break
    if not target:
        # Don't reveal existence; return generic success.
        return ok({"queued": True})
    # Generate a short-lived code and email it (workflow-gated).
    import secrets
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    # Store code briefly in session keyed by username (simple, no extra store).
    session.setdefault("reset_codes", {})[target.get("sAMAccountName", "")] = code
    session.modified = True
    try:
        from app import workflows as wf
        from app.email import send_password_reset
        wf.run("email_password_reset", lambda: send_password_reset(target, code))
    except Exception:
        pass
    return ok({"queued": True})


# Verify code + set new password (self-service, no old password needed).
@bp.route("/self/reset-confirm", methods=["POST"])
def reset_confirm():
    data = request.get_json(force=True) or {}
    identifier = (data.get("username") or "").strip()
    code = (data.get("code") or "").strip()
    new_pw = data.get("new_password") or ""
    if not (identifier and code and new_pw):
        return fail("username, code and new_password required", code="validation")
    codes = session.get("reset_codes", {})
    if codes.get(identifier.lower()) != code:
        return fail("Invalid or expired code.", code="bad_code", status=400)
    users = op.list_users(search=identifier, size_limit=10)
    target = None
    for u in users:
        if (u.get("sAMAccountName", "").lower() == identifier.lower()
                or u.get("userPrincipalName", "").lower() == identifier.lower()):
            target = u
            break
    if not target:
        return fail("user not resolved", code="not_found", status=404)
    try:
        op.reset_password(target.get("dn"), new_pw, force_change=True)
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    # Consume code
    codes.pop(identifier.lower(), None)
    session["reset_codes"] = codes
    session.modified = True
    audit.log("self.password_reset", identifier, target=target.get("dn", ""), outcome="success")
    return ok({"reset": True})


# ───────────────────────────── GROUPS ─────────────────────────────
@bp.route("/groups", methods=["GET"])
@login_required
def list_groups():
    search = request.args.get("q", "")
    try:
        out = op.list_groups(search=search)
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    return ok(out, meta={"total": len(out)})


@bp.route("/groups/<path:dn>", methods=["GET"])
@login_required
def get_group(dn):
    try:
        g = op.get_group(dn)
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    if not g:
        return fail("not found", code="not_found", status=404)
    return ok(g)


@bp.route("/groups", methods=["POST"])
@login_required
@audit_action("group.create", target_getter=lambda resp, *a, **k: (request.get_json(force=True,silent=True) or {}).get("dn") or "")
def create_group():
    data = request.get_json(force=True) if request.is_json else request.form
    dn = data.get("dn"); sam = data.get("sam")
    if not dn or not sam:
        return fail("dn and sam required", code="validation")
    g = op.create_group(dn, sam, desc=data.get("desc", ""),
                        scope=data.get("scope", "global"))
    return ok(g), 201


@bp.route("/groups/<path:dn>/members", methods=["POST"])
@login_required
@audit_action("group.add_member", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def add_member(dn):
    data = request.get_json(force=True)
    member = data.get("member_dn")
    if not member:
        return fail("member_dn required", code="validation")
    op.add_member(dn, member)
    return ok({"added": member})


@bp.route("/groups/<path:dn>/members", methods=["DELETE"])
@login_required
@audit_action("group.remove_member", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def remove_member(dn):
    data = request.get_json(force=True)
    member = data.get("member_dn")
    if not member:
        return fail("member_dn required", code="validation")
    op.remove_member(dn, member)
    return ok({"removed": member})


@bp.route("/groups/copy", methods=["POST"])
@login_required
@audit_action("group.copy_members", target_getter=lambda resp, *a, **k: (request.get_json(force=True,silent=True) or {}).get("source_dn") or "")
def copy_group():
    data = request.get_json(force=True)
    src = data.get("source_dn"); tgt = data.get("target_dn")
    if not src or not tgt:
        return fail("source_dn and target_dn required", code="validation")
    g = op.copy_group_members(src, tgt)
    return ok(g)


@bp.route("/groups/<path:dn>", methods=["DELETE"])
@login_required
@audit_action("group.delete", target_getter=lambda resp, *a, **k: k.get("dn") or "")
def delete_group(dn):
    op.delete_group(dn)
    return ok({"deleted": dn})


# ───────────────────────────── OUs ────────────────────────────────
@bp.route("/ous", methods=["GET"])
@login_required
def list_ous():
    parent = request.args.get("parent", "")
    try:
        out = op.list_ous(parent_dn=parent)
    except Exception as e:
        return fail(str(e), code="ldap", status=500)
    return ok(out, meta={"total": len(out)})


# ─────────────────────────── AUDIT (admin) ────────────────────────
@bp.route("/audit", methods=["GET"])
@login_required
def audit_feed():
    if not is_domain_admin(_user().get("sAMAccountName", "")):
        return fail("admin only", code="denied", status=403)
    limit = min(500, max(1, int(request.args.get("limit", 100))))
    actor = request.args.get("actor", "")
    return ok(audit.recent(limit=limit, actor=actor))
