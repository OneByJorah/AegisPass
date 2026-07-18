"""Enrollment storage for AegisPass Self-Service.

Enrollment data (recovery email/phone, security question, and the encrypted
TOTP secret) is persisted in the user's ``extensionAttribute1`` as an
encrypted JSON blob. We encrypt so no plaintext recovery secrets or TOTP
seeds are ever stored in the directory. Data is reversible only with the
server-side ENROLL_KEY (falls back to SECRET_KEY).

The encrypted blob is prefixed with ``aegis1:`` so we can tell a fresh/
unenrolled account apart from a real blob.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Optional

from cryptography.fernet import Fernet

from app.config import Config

_PREFIX = "aegis1:"
_TOTP_PREFIX = "totp1:"


def _key() -> bytes:
    raw = getattr(Config, "ENROLL_KEY", None) or Config.SECRET_KEY or os.urandom(32)
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    # Derive a 32-byte url-safe key for Fernet.
    import hashlib
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())


def _fernet() -> Fernet:
    return Fernet(_key())


def _encrypt(obj: dict) -> str:
    blob = _fernet().encrypt(json.dumps(obj).encode("utf-8"))
    return _PREFIX + blob.decode("utf-8")


def _decrypt(blob: str) -> Optional[dict]:
    if not blob or not blob.startswith(_PREFIX):
        return None
    try:
        raw = blob[len(_PREFIX):].encode("utf-8")
        return json.loads(_fernet().decrypt(raw).decode("utf-8"))
    except Exception:
        return None


def load_profile(conn, dn: str) -> dict:
    """Return the stored enrollment profile (may be empty)."""
    import ldap3
    from app.ad import client
    conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE,
                attributes=["extensionAttribute1"])
    if not conn.entries:
        return {}
    val = conn.entries[0].extensionAttribute1.value if conn.entries[0].extensionAttribute1 else None
    if not val:
        return {}
    data = _decrypt(val)
    return data or {}


def save_profile(conn, dn: str, profile: dict) -> None:
    """Persist the enrollment profile blob to extensionAttribute1."""
    import ldap3
    blob = _encrypt(profile)
    # Replace whole attribute.
    conn.modify(dn, {
        "extensionAttribute1": [(ldap3.MODIFY_REPLACE, blob)]
    })


def is_enrolled(conn, dn: str) -> bool:
    """True if the account has any enrollment data stored."""
    import ldap3
    from app.ad import client
    conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE,
                attributes=["extensionAttribute1"])
    if not conn.entries:
        return False
    val = conn.entries[0].extensionAttribute1.value if conn.entries[0].extensionAttribute1 else None
    return bool(val) and val.startswith(_PREFIX)


def write_totp_secret(conn, dn: str, secret: str) -> None:
    """Store only the encrypted TOTP secret in extensionAttribute2."""
    import ldap3
    blob = _TOTP_PREFIX + _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")
    conn.modify(dn, {
        "extensionAttribute2": [(ldap3.MODIFY_REPLACE, blob)]
    })


def read_totp_secret(conn, dn: str) -> Optional[str]:
    import ldap3
    from app.ad import client
    conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE,
                attributes=["extensionAttribute2"])
    if not conn.entries:
        return None
    val = conn.entries[0].extensionAttribute2.value if conn.entries[0].extensionAttribute2 else None
    if not val or not val.startswith(_TOTP_PREFIX):
        return None
    try:
        return _fernet().decrypt(val[len(_TOTP_PREFIX):].encode("utf-8")).decode("utf-8")
    except Exception:
        return None
