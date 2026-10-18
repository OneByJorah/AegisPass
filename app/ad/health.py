"""Infrastructure health / status — powers the login-page status panel.

IMPORTANT: this intentionally exposes ONLY non-sensitive signals so users can
see the directory is reachable and trusted, WITHOUT leaking internal hostnames,
IPs, DNs, or credentials. e.g. 'Directory: Online', 'Secure channel: Verified',
not '<DC-IP>:636 CN=kervado-DC...'.
"""
from __future__ import annotations

import socket
import time
from typing import Dict


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def status() -> Dict:
    """Return a non-sensitive health snapshot for the UI."""
    from app.config import Config
    if Config.DEMO_MODE:
        from app.ad.demo import count_users, count_groups
        sso_state = "available" if Config.SSO_ENABLED else "disabled"
        return {
            "directory": "online",
            "secure_channel": "verified",
            "sso": sso_state,
            "latency_ms": 12,
            "user_count": count_users(),
            "group_count": count_groups(),
            "message": "Demo mode — synthetic directory data.",
        }
    out = {
        "directory": "unknown",
        "secure_channel": "unknown",
        "sso": "unknown",
        "latency_ms": None,
        "user_count": None,
        "group_count": None,
        "message": "",
    }
    # 1) TCP reachability
    t0 = time.time()
    reachable = _tcp_open(Config.AD_HOST, Config.AD_LDAPS_PORT)
    if reachable:
        out["latency_ms"] = round((time.time() - t0) * 1000)
    out["directory"] = "online" if reachable else "offline"

    # 2) TLS pin verification + aggregate counts (via service account)
    if reachable:
        try:
            from app.ad import client
            from app.ad import operations as op
            conn = client.get_connection()
            out["secure_channel"] = "verified"
            out["message"] = "Secure channel to directory verified."
            try:
                out["user_count"] = op.count_users(conn=conn)
                out["group_count"] = op.count_groups(conn=conn)
            except Exception:
                pass
            conn.unbind()
        except Exception:
            out["secure_channel"] = "unverified"
            out["message"] = "Directory secure channel could not be verified."
    else:
        out["message"] = "Directory services are unreachable."

    # 3) SSO availability
    try:
        from app.auth import sso
        out["sso"] = "available" if sso.sso_enabled() else "disabled"
    except Exception:
        out["sso"] = "disabled"

    return out


def ldap_ping() -> bool:
    """Quick bind test used by /health/ldap endpoint."""
    from app.config import Config
    if Config.DEMO_MODE:
        return True
    try:
        from app.ad import client
        conn = client.get_connection()
        ok = conn.bound
        conn.unbind()
        return ok
    except Exception:
        return False
