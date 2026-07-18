"""Email delivery for aegispass.

Uses the internal district SMTP relay (no authentication required).
All outbound mail is sent from a single configured sender address.
Fail-safe: email failures are logged but never break the triggering action.
"""
from __future__ import annotations

import os
import smtplib
import ssl
import threading
from email.message import EmailMessage
from typing import Optional

from app.config import Config

_LOCK = threading.Lock()


def _enabled() -> bool:
    return bool(getattr(Config, "SMTP_ENABLED", False))


def send(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
    """Send a plaintext (and optional HTML) email. Returns True on success."""
    if not _enabled():
        return False
    if not to:
        return False
    sender = Config.SMTP_SENDER
    msg = EmailMessage()
    from email.utils import formataddr
    sender_name = getattr(Config, "SMTP_SENDER_NAME", "AEGISPASS PASSWORD RESET")
    msg["From"] = formataddr((sender_name, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        with _LOCK:
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15) as s:
                s.send_message(msg)
        return True
    except Exception as e:
        try:
            from app.audit import log
            log("email.send", "system", target=to, outcome="error", detail=str(e)[:200])
        except Exception:
            pass
        return False


# ── Templated helpers ────────────────────────────────────────────────
def send_password_reset(user: dict, code: str, expires_min: int = 30) -> bool:
    to = user.get("mail") or user.get("email")
    name = user.get("displayName") or user.get("givenName") or user.get("sAMAccountName") or "user"
    subject = "AegisPass Password Reset Request"
    body = (
        f"Hello {name},\n\n"
        f"We received a request to reset your AegisPass password.\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in {expires_min} minutes. If you did not request this, "
        f"you can ignore this email — your password will not change.\n\n"
        f"– AegisPass IT Department"
    )
    html = (
        f"<p>Hello {name},</p>"
        f"<p>We received a request to reset your AegisPass password.</p>"
        f"<p>Your verification code is: <b>{code}</b></p>"
        f"<p>This code expires in {expires_min} minutes. If you did not request this, "
        f"you can ignore this email.</p>"
        f"<p>– AegisPass IT Department</p>"
    )
    return send(to, subject, body, html)


def send_welcome(user: dict, temp_password: str) -> bool:
    to = user.get("mail") or user.get("email")
    name = user.get("displayName") or user.get("givenName") or user.get("sAMAccountName") or "user"
    uname = user.get("sAMAccountName") or user.get("userPrincipalName") or ""
    subject = "Welcome to AegisPass — Your Account is Ready"
    body = (
        f"Hello {name},\n\n"
        f"Your AegisPass account has been created.\n\n"
        f"Username: {uname}\n"
        f"Temporary password: {temp_password}\n\n"
        f"Please sign in and change your password at your first opportunity.\n\n"
        f"– AegisPass IT Department"
    )
    html = (
        f"<p>Hello {name},</p>"
        f"<p>Your AegisPass account has been created.</p>"
        f"<p>Username: <b>{uname}</b><br>Temporary password: <b>{temp_password}</b></p>"
        f"<p>Please sign in and change your password at your first opportunity.</p>"
        f"<p>– AegisPass IT Department</p>"
    )
    return send(to, subject, body, html)


def send_password_reset_notice(user: dict, new_password: str) -> bool:
    """Notify a user that an admin reset their password, with the new temp password."""
    to = user.get("mail") or user.get("email")
    if not to:
        return False
    name = user.get("displayName") or user.get("givenName") or user.get("sAMAccountName") or "user"
    uname = user.get("sAMAccountName") or user.get("userPrincipalName") or ""
    subject = "AegisPass — Your Password Was Reset"
    body = (
        f"Hello {name},\n\n"
        f"Your AegisPass account password was reset by an administrator.\n\n"
        f"Username: {uname}\n"
        f"New temporary password: {new_password}\n\n"
        f"Please sign in and change your password at your first opportunity.\n\n"
        f"– AegisPass IT Department"
    )
    html = (
        f"<p>Hello {name},</p>"
        f"<p>Your AegisPass account password was reset by an administrator.</p>"
        f"<p>Username: <b>{uname}</b><br>New temporary password: <b>{new_password}</b></p>"
        f"<p>Please sign in and change your password at your first opportunity.</p>"
        f"<p>– AegisPass IT Department</p>"
    )
    return send(to, subject, body, html)
    to = getattr(Config, "ADMIN_ALERT_EMAIL", "")
    if not to:
        return False
    subject = f"[AegisPass AD] Privileged action: {action}"
    body = (
        f"A privileged action was performed in AegisPass.\n\n"
        f"Action : {action}\n"
        f"Actor  : {actor}\n"
        f"Target : {target}\n"
        f"Outcome: {outcome}\n"
        f"Detail : {detail}\n"
    )
    return send(to, subject, body)


def send_expiry_reminder(user: dict, days_left: int) -> bool:
    to = user.get("mail") or user.get("email")
    name = user.get("displayName") or user.get("givenName") or user.get("sAMAccountName") or "user"
    subject = f"AegisPass Password Expiry Reminder — {days_left} day(s) left"
    body = (
        f"Hello {name},\n\n"
        f"Your AegisPass password will expire in {days_left} day(s).\n\n"
        f"Please change it before it expires to avoid being locked out. "
        f"You can do this from the AegisPass Self Service portal.\n\n"
        f"– AegisPass IT Department"
    )
    html = (
        f"<p>Hello {name},</p>"
        f"<p>Your AegisPass password will expire in <b>{days_left} day(s)</b>.</p>"
        f"<p>Please change it before it expires to avoid being locked out.</p>"
        f"<p>– AegisPass IT Department</p>"
    )
    return send(to, subject, body, html)


def send_locked_notice(user: dict) -> bool:
    to = user.get("mail") or user.get("email")
    name = user.get("displayName") or user.get("givenName") or user.get("sAMAccountName") or "user"
    subject = "AegisPass Account Locked"
    body = (
        f"Hello {name},\n\n"
        f"Your AegisPass account has been locked, likely due to too many failed sign-in attempts.\n\n"
        f"It will unlock automatically or contact the IT Help Desk for assistance.\n\n"
        f"– AegisPass IT Department"
    )
    return send(to, subject, body)
