"""Safety guards for AD write operations.

This module exists to make accidental destruction of Tier-0 / protected
objects impossible from the UI or API. Every write path must call
`assert_writable(dn)` before touching an object, and `assert_safe_to_delete(dn)`
before deleting.

Configuration (env):
  AD_WRITE_SCOPE_OU  -> comma-separated DNs; if set, writes are ONLY allowed
                        under these OUs (recommended for production).
  AD_PROTECT_DENYLIST -> comma-separated DNs/names always forbidden even if
                        inside the write scope. Default covers Tier-0.
"""
from __future__ import annotations

import os
from app.config import Config

# Tier-0 /永远-protected well-known objects (by sAMAccountName or CN fragment)
DEFAULT_PROTECTED_SAM = {
    "administrator", "krbtgt", "guest", "domain admins", "enterprise admins",
    "schema admins", "administrators", "cert publishers", "domain controllers",
    "read-only domain controllers", "group policy creator owners",
    "ras and ias servers", "enterprise read-only domain controllers",
    "denied rodc password replication group", "protected users",
}

DEFAULT_PROTECTED_OU = {
    "ou=domain controllers",
    "ou=users,cn=builtin",
    "cn=users",
    "cn=builtin",
    "ou=service accounts",  # protect the service account OU by default
}


def _normalize_dn(dn: str) -> str:
    return dn.strip().lower().replace("\\", "")


def protected_dns() -> set[str]:
    extra = os.environ.get("AD_PROTECT_DENYLIST", "").strip()
    out = {_normalize_dn(x) for x in DEFAULT_PROTECTED_OU}
    for d in extra.split(","):
        d = d.strip()
        if d:
            out.add(_normalize_dn(d))
    return out


def write_scope_ous() -> list[str]:
    scope = os.environ.get("AD_WRITE_SCOPE_OU", "").strip()
    if not scope:
        return []
    return [_normalize_dn(x) for x in scope.split(",") if x.strip()]


def _sam_from_dn(dn: str) -> str:
    # best-effort: take CN value
    for part in dn.split(","):
        if part.strip().lower().startswith("cn="):
            return part.strip()[3:].lower()
    return ""


def is_protected(dn: str, sam: str = "") -> bool:
    dn_n = _normalize_dn(dn)
    if dn_n in protected_dns():
        return True
    sam = (sam or _sam_from_dn(dn)).strip().lower()
    if sam in DEFAULT_PROTECTED_SAM:
        return True
    # protect any DN containing a protected OU fragment
    for p in protected_dns():
        if p.startswith("ou=") or p.startswith("cn="):
            if dn_n.endswith(p) or ("," + p) in dn_n:
                return True
    return False


def assert_writable(dn: str, sam: str = "") -> None:
    """Raise PermissionError if writing to dn is not allowed."""
    dn_n = _normalize_dn(dn)
    if is_protected(dn_n, sam):
        raise PermissionError(
            "Refusing to modify a protected object. This operation is blocked "
            "by the safety denylist (Tier-0 / built-in accounts)."
        )
    scope = write_scope_ous()
    if scope:
        allowed = any(dn_n.endswith(o) or ("," + o) in dn_n for o in scope)
        if not allowed:
            raise PermissionError(
                "Target is outside the configured write scope "
                f"({os.environ.get('AD_WRITE_SCOPE_OU')}). Set AD_WRITE_SCOPE_OU "
                "or choose a target within the allowed OUs."
            )


def assert_safe_to_delete(dn: str, sam: str = "") -> None:
    dn_n = _normalize_dn(dn)
    if is_protected(dn_n, sam):
        raise PermissionError(
            "Refusing to delete a protected object (safety denylist)."
        )
    scope = write_scope_ous()
    if scope:
        allowed = any(dn_n.endswith(o) or ("," + o) in dn_n for o in scope)
        if not allowed:
            raise PermissionError(
                "Delete target is outside the configured write scope."
            )
