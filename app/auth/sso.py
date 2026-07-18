"""SSO via Kerberos / Negotiate (SPNEGO).

Domain-joined clients that have a Kerberos TGT auto-authenticate: the browser
sends an Authorization: Negotiate <token>; we verify it against the DC's
LDAP whoami (SASL GSSAPI) or, more simply, decode the AP-REQ and map the
client principal to an AD sAMAccountName.

This module supports two modes:
  1. gssapi available  -> full SPNEGO accept (preferred; needs python-gssapi +
     a keytab for HTTP/<host>).
  2. fallback          -> we attempt an LDAP SASL GSSAPI bind using the
     delegated credential is not possible from the web tier, so instead we
     show the SSO *banner* and rely on the password form. The Negotiate
     handshake is still attempted; if it fails we silently fall back.

For the common deployment (nginx + mod_auth_gssapi doing the real Kerberos
validation and setting REMOTE_USER), this module simply trusts REMOTE_USER
when SSO_REMOTE_USER_TRUST=True (set by the proxy). That is the most robust
and is what we document in SECURITY.md.
"""
from __future__ import annotations

import base64
import os
from typing import Optional, Tuple

from app.config import Config


def sso_enabled() -> bool:
    return Config.SSO_ENABLED


def remote_user_trusted() -> bool:
    """When the front proxy (nginx/mod_auth_gssapi) has authenticated the user,
    it sets REMOTE_USER. We trust it only if explicitly enabled."""
    return os.environ.get("SSO_REMOTE_USER_TRUST", "False").lower() in ("1", "true", "yes")


def map_remote_user_to_sam(remote_user: str) -> str:
    """Convert a Kerberos/UPN principal (user@REALM or DOMAIN\\user) to the
    sAMAccountName we use for the session."""
    ru = remote_user.strip()
    if "@" in ru:
        ru = ru.split("@")[0]
    if "\\" in ru:
        ru = ru.split("\\")[-1]
    return ru


def try_spnego(token_b64: str) -> Optional[str]:
    """Attempt to accept a SPNEGO Negotiate token.

    Returns the client principal (user@REALM) if gssapi is available and the
    token validates, else None. Never raises — any failure means 'no SSO'.
    """
    if not token_b64:
        return None
    try:
        import gssapi
    except Exception:
        return None
    try:
        server_name = gssapi.Name(Config.SSO_SERVICE_NAME + "/" + Config.AD_HOST,
                                   gssapi.NameType.hostbased_service)
        ctx = gssapi.SecurityContext(usage="accept", name=server_name)
        in_token = base64.b64decode(token_b64)
        out_token, source_name, _ = ctx.step(in_token)
        if ctx.complete and source_name:
            return str(source_name)
    except Exception:
        return None
    return None


def negotiate_response(token_b64: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (client_principal, out_token_b64)."""
    try:
        import gssapi
    except Exception:
        return None, None
    try:
        server_name = gssapi.Name(Config.SSO_SERVICE_NAME + "/" + Config.AD_HOST,
                                   gssapi.NameType.hostbased_service)
        ctx = gssapi.SecurityContext(usage="accept", name=server_name)
        in_token = base64.b64decode(token_b64) if token_b64 else b""
        out_token, source_name, _ = ctx.step(in_token)
        out_b64 = base64.b64encode(out_token).decode() if out_token else None
        return (str(source_name) if source_name else None, out_b64)
    except Exception:
        return None, None
