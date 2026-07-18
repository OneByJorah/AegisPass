"""Self-service Enrollment API.

Three enrollment capabilities, all gated behind an authenticated session
(the user verifies their identity with their current password first, in the
front-end, before calling these):

  1. Recovery profile  — recovery email, mobile, security question/answer.
  2. MFA / TOTP        — register an authenticator app (encrypted secret in AD).
  3. Account/device    — mark this account as enrolled (enrolledAt timestamp).

All writes go through the encrypted enrollment blob in extensionAttribute1/2.
Nothing sensitive is stored in plaintext.
"""
from __future__ import annotations

import pyotp
import qrcode
import io
import base64
from flask import Blueprint, request, session, jsonify

from app.api import ok, fail
from app.ad import operations as op, client, enrollment as enr
from app import audit

bp = Blueprint("enrollment_api", __name__)


def _dn():
    return (session.get("user") or {}).get("dn") or ""


def _sam():
    return (session.get("user") or {}).get("sAMAccountName") or ""


def _actor():
    return _sam() or "anonymous"


# ── status ────────────────────────────────────────────────────────
@bp.route("/enrollment/status", methods=["GET"])
def status():
    dn = _dn()
    if not dn:
        return fail("authentication required", code="auth", status=401)
    conn = client.get_connection()
    try:
        prof = enr.load_profile(conn, dn)
        enrolled = enr.is_enrolled(conn, dn)
        secret = enr.read_totp_secret(conn, dn)
    finally:
        conn.unbind()
    return ok({
        "enrolled": enrolled,
        "has_recovery": bool(prof.get("recovery_email") or prof.get("security_question")),
        "mfa_enabled": bool(secret),
        "recovery_email_set": bool(prof.get("recovery_email")),
        "mobile_set": bool(prof.get("mobile")),
        "security_question": prof.get("security_question", ""),
        "enrolled_at": prof.get("enrolled_at"),
    })


# ── recovery profile ──────────────────────────────────────────────
@bp.route("/enrollment/recovery", methods=["POST"])
def set_recovery():
    dn = _dn()
    if not dn:
        return fail("authentication required", code="auth", status=401)
    data = request.get_json(force=True) or {}
    recovery_email = (data.get("recovery_email") or "").strip().lower()
    mobile = (data.get("mobile") or "").strip()
    question = (data.get("security_question") or "").strip()
    answer = (data.get("security_answer") or "").strip()
    if not recovery_email and not mobile and not question:
        return fail("Provide at least a recovery email, mobile, or security question.",
                    code="validation")
    conn = client.get_connection()
    try:
        prof = enr.load_profile(conn, dn)
        if recovery_email:
            prof["recovery_email"] = recovery_email
        if mobile:
            prof["mobile"] = mobile
        if question and answer:
            # store a simple hash of the answer (case/space-insensitive)
            import hashlib
            prof["security_question"] = question
            prof["security_answer_hash"] = hashlib.sha256(
                answer.strip().lower().encode("utf-8")).hexdigest()
        enr.save_profile(conn, dn, prof)
    finally:
        conn.unbind()
    audit.log("enrollment.recovery", _actor(), target=dn, outcome="success")
    return ok({"saved": True})


@bp.route("/enrollment/recovery/verify", methods=["POST"])
def verify_recovery():
    """Verify a security-question answer (used during password reset)."""
    dn = _dn()
    if not dn:
        return fail("authentication required", code="auth", status=401)
    data = request.get_json(force=True) or {}
    answer = (data.get("security_answer") or "").strip()
    if not answer:
        return fail("Answer required", code="validation")
    conn = client.get_connection()
    try:
        prof = enr.load_profile(conn, dn)
    finally:
        conn.unbind()
    import hashlib
    h = hashlib.sha256(answer.strip().lower().encode("utf-8")).hexdigest()
    ok_ = prof.get("security_answer_hash") == h
    return ok({"verified": ok_, "question": prof.get("security_question", "")})


# ── TOTP / MFA ────────────────────────────────────────────────────
@bp.route("/enrollment/totp/setup", methods=["POST"])
def totp_setup():
    dn = _dn()
    if not dn:
        return fail("authentication required", code="auth", status=401)
    data = request.get_json(force=True) or {}
    sam = _sam()
    label = data.get("label") or f"AegisPass:{sam}"
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name="AegisPass Self-Service")
    # Build a QR code as inline SVG (no PIL dependency).
    from qrcode.image.svg import SvgPathImage
    img = qrcode.make(uri, image_factory=SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    qr_svg = buf.getvalue().decode("utf-8")
    return ok({
        "secret": secret,
        "uri": uri,
        "qr_svg": qr_svg,
    })


@bp.route("/enrollment/totp/verify", methods=["POST"])
def totp_verify():
    dn = _dn()
    if not dn:
        return fail("authentication required", code="auth", status=401)
    data = request.get_json(force=True) or {}
    code = (data.get("code") or "").strip().replace(" ", "")
    secret = (data.get("secret") or "").strip()
    if not secret or not code:
        return fail("secret and code required", code="validation")
    ok_ = pyotp.TOTP(secret).verify(code, valid_window=1)
    if not ok_:
        return ok({"verified": False})
    # Commit the encrypted secret to AD.
    conn = client.get_connection()
    try:
        enr.write_totp_secret(conn, dn, secret)
        prof = enr.load_profile(conn, dn)
        prof["mfa_enabled"] = True
        enr.save_profile(conn, dn, prof)
    finally:
        conn.unbind()
    audit.log("enrollment.mfa", _actor(), target=dn, outcome="success")
    return ok({"verified": True})


# ── account / device enrollment ───────────────────────────────────
@bp.route("/enrollment/account", methods=["POST"])
def account_enroll():
    dn = _dn()
    if not dn:
        return fail("authentication required", code="auth", status=401)
    data = request.get_json(force=True) or {}
    device = (data.get("device") or "").strip()
    conn = client.get_connection()
    try:
        prof = enr.load_profile(conn, dn)
        from datetime import datetime
        prof["enrolled"] = True
        prof["enrolled_at"] = datetime.utcnow().isoformat() + "Z"
        if device:
            prof.setdefault("devices", []).append(device)
        enr.save_profile(conn, dn, prof)
    finally:
        conn.unbind()
    audit.log("enrollment.account", _actor(), target=dn, outcome="success",
              detail=device or "")
    return ok({"enrolled": True})
