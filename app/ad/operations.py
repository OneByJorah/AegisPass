"""AD management operations: users, groups, passwords, OUs.

All write operations go through app.ad.safety guards.
Password operations use the unicodePwd attribute (UTF-16LE quoted), which is
the correct AD mechanism and works over LDAPS (636).
"""
from __future__ import annotations

import ldap3
import ssl
from datetime import datetime, timedelta
from typing import Optional

from app.ad import client
from app.ad.safety import assert_writable, assert_safe_to_delete, is_protected
from app.config import Config

UF_NORMAL_ACCOUNT = 0x0200
UF_ACCOUNTDISABLE = 0x0002
UF_DONT_EXPIRE_PASSWD = 0x10000
UF_PASSWD_NOTREQD = 0x0020


def _set_unicode_pwd(conn, dn: str, password: str) -> None:
    """Set unicodePwd directly (the canonical AD mechanism, works over LDAPS)."""
    enc = ('"' + password + '"').encode("utf-16-le")
    conn.modify(dn, {"unicodePwd": [(ldap3.MODIFY_REPLACE, enc)]})


def _sam(dn: str) -> str:
    for part in dn.split(","):
        if part.strip().lower().startswith("cn="):
            return part.strip()[3:]
    return ""


def is_domain_admin(sam: str) -> bool:
    """True if the sAMAccountName belongs to the admin group (Config.DOMAIN_ADMINS_GROUP).

    Checks both direct/ nested memberOf AND the primary group (Domain Admins'
    primaryGroupID is 512). Returns False on any error rather than raising.
    """
    if not sam:
        return False
    try:
        group_dn = Config.DOMAIN_ADMINS_GROUP
        conn = client.get_connection()
        # Resolve the user DN
        flt = f"(sAMAccountName={ldap3.utils.conv.escape_filter_chars(sam)})"
        conn.search(Config.AD_BASE_DN, flt, search_scope=ldap3.SUBTREE,
                    attributes=["distinguishedName", "memberOf", "primaryGroupID"])
        if not conn.entries:
            conn.unbind()
            return False
        e = conn.entries[0]
        member_of = [str(x) for x in (e.memberOf.values if e.memberOf else [])]
        # nested membership: walk up one level for direct members' groups
        primary = int(e.primaryGroupID.value) if e.primaryGroupID else None
        conn.unbind()
        # direct or nested membership of the admin group
        if group_dn in member_of:
            return True
        # primary group check (RID 512 = Domain Admins)
        if primary == 512:
            return True
        # one-level nested: check groups the user is in for membership in admin group
        for g in member_of:
            try:
                c2 = client.get_connection()
                c2.search(g, "(objectClass=group)", search_scope=ldap3.BASE,
                          attributes=["memberOf"])
                if c2.entries and group_dn in [str(x) for x in c2.entries[0].memberOf.values]:
                    c2.unbind()
                    return True
                c2.unbind()
            except Exception:
                pass
        return False
    except Exception:
        return False


def count_users(conn=None) -> int:
    """Approximate number of user objects. Reuses `conn` if provided."""
    own = False
    try:
        if conn is None:
            conn = client.get_connection(); own = True
        conn.search(Config.AD_BASE_DN, "(objectClass=user)", search_scope=ldap3.SUBTREE,
                    attributes=["cn"], size_limit=0)
        return len(conn.entries)
    except Exception:
        return 0
    finally:
        if own and conn:
            try: conn.unbind()
            except Exception: pass


def count_groups(conn=None) -> int:
    """Approximate number of group objects. Reuses `conn` if provided."""
    own = False
    try:
        if conn is None:
            conn = client.get_connection(); own = True
        conn.search(Config.AD_BASE_DN, "(objectClass=group)", search_scope=ldap3.SUBTREE,
                    attributes=["cn"], size_limit=0)
        return len(conn.entries)
    except Exception:
        return 0
    finally:
        if own and conn:
            try: conn.unbind()
            except Exception: pass


def device_status() -> dict:
    """Non-sensitive aggregate device/computer status from AD.

    Returns counts only — no hostnames, IPs, or user-specific last-logon data.
    """
    out = {"total": 0, "active": 0, "disabled": 0, "workstations": 0,
           "servers": 0, "domain_controllers": 0, "stale": 0, "sites": {}, "os": {}}
    conn = None
    own = False
    try:
        conn = client.get_connection(); own = True
        now = datetime.utcnow()
        # All enabled & disabled computer accounts
        conn.search(Config.AD_BASE_DN, "(objectClass=computer)", search_scope=ldap3.SUBTREE,
                    attributes=["userAccountControl", "lastLogonTimestamp",
                                "operatingSystem", "distinguishedName"], size_limit=0)
        entries = list(conn.entries)
        out["total"] = len(entries)
        for e in entries:
            uac = int(e.userAccountControl.value) if e.userAccountControl else 0
            disabled = bool(uac & 2)
            if disabled:
                out["disabled"] += 1
            else:
                out["active"] += 1
            dn = str(e.entry_dn) if hasattr(e, "entry_dn") else ""
            # Classify by OU / location (take first RDN component as site bucket)
            ou_part = None
            for part in dn.split(","):
                if part.strip().upper().startswith("OU="):
                    ou_part = part.strip()[3:]
                    break
            site = ou_part or "Other"
            out["sites"][site] = out["sites"].get(site, 0) + 1
            # Stale: lastLogonTimestamp older than 60 days (or absent for new)
            ts = e.lastLogonTimestamp.value if e.lastLogonTimestamp else None
            try:
                if ts:
                    ad_dt = ldap3_time_to_datetime(ts)
                    if (now - ad_dt).days > 60:
                        out["stale"] += 1
            except Exception:
                pass
            # OS family aggregation (sanitized, no specific hostnames)
            os_name = ""
            try:
                os_name = str(e.operatingSystem.value) if e.operatingSystem else ""
            except Exception:
                pass
            family = "Windows"
            if "Server" in os_name:
                out["servers"] += 1
                family = "Windows Server"
                if "Domain Controller" in os_name or "_DC" in dn:
                    out["domain_controllers"] += 1
            elif os_name:
                out["workstations"] += 1
            if os_name:
                out["os"][family] = out["os"].get(family, 0) + 1
        # Fallback classification if operatingSystem attribute missing
        if not out["workstations"] and not out["servers"]:
            for e in entries:
                dn = str(e.entry_dn) if hasattr(e, "entry_dn") else ""
                if "CN=Domain Controllers" in dn:
                    out["domain_controllers"] += 1
                    out["servers"] += 1
                elif "CN=Computers" in dn or any(x in dn for x in ["OU=STTJ", "OU=STX", "OU=Workstations"]):
                    out["workstations"] += 1
                else:
                    out["servers"] += 1
    except Exception as e:
        out["error"] = str(e)
    finally:
        if own and conn:
            try: conn.unbind()
            except Exception: pass
    return out


def ldap3_time_to_datetime(val) -> datetime:
    """Convert AD large integer / datetime to Python datetime."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, int):
        # AD time in 100-ns intervals since 1601-01-01
        return datetime(1601, 1, 1) + timedelta(microseconds=val // 10)
    if isinstance(val, str):
        # try common formats
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y%m%d%H%M%S.%fZ", "%Y%m%d%H%M%SZ"):
            try: return datetime.strptime(val, fmt)
            except Exception: pass
    return datetime.utcnow()


# ───────────────────────────── USERS ─────────────────────────────
def _enrich_user(u: dict) -> dict:
    """Add computed fields (passwordExpires) to a user dict."""
    try:
        pls = u.get("pwdLastSet")
        if isinstance(pls, str):
            pls = int(pls)
        if isinstance(pls, datetime):
            set_dt = pls
        else:
            set_dt = datetime(1601, 1, 1) + timedelta(microseconds=(pls or 0) // 10)
        max_age = _domain_max_pwd_age()
        if max_age is not None:
            exp = set_dt + max_age
            u["passwordLastSet"] = set_dt
            u["passwordExpires"] = exp
    except Exception:
        pass
    return u


_DOMAIN_MAX_PWD_AGE = None  # cached


def _domain_max_pwd_age():
    """Return the domain password policy max age as a timedelta, or None."""
    global _DOMAIN_MAX_PWD_AGE
    if _DOMAIN_MAX_PWD_AGE is not None:
        return _DOMAIN_MAX_PWD_AGE
    try:
        from datetime import timedelta
        # search against the domain naming context root
        domain_dn = Config.AD_BASE_DN
        conn = client.get_connection()
        conn.search(domain_dn, "(objectClass=domainDNS)",
                    search_scope=ldap3.BASE, attributes=["maxPwdAge"])
        if conn.entries:
            raw = conn.entries[0]["maxPwdAge"].value
            if isinstance(raw, timedelta):
                _DOMAIN_MAX_PWD_AGE = raw
            elif raw:
                # maxPwdAge may be negative (I8) in 100-ns ticks
                secs = abs(int(raw)) // 10_000_000
                _DOMAIN_MAX_PWD_AGE = timedelta(seconds=secs)
        conn.unbind()
    except Exception:
        pass
    return _DOMAIN_MAX_PWD_AGE


def list_users(search: str = "", scope: str = "subtree", size_limit: int = 200) -> list[dict]:
    conn = client.get_connection()
    flt = "(objectClass=user)"
    if search:
        safe = ldap3.utils.conv.escape_filter_chars(search)
        flt = f"(|(sAMAccountName=*{safe}*)(cn=*{safe}*)(mail=*{safe}*)(displayName=*{safe}*))"
    sc = ldap3.SUBTREE if scope == "subtree" else ldap3.LEVEL
    conn.search(Config.AD_BASE_DN, flt, search_scope=sc,
                attributes=client.USER_ATTRS, size_limit=size_limit)
    out = [_enrich_user(client.entry_to_dict(e)) for e in conn.entries]
    conn.unbind()
    return out


def get_user(dn: str) -> Optional[dict]:
    conn = client.get_connection()
    conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE,
                attributes=client.USER_ATTRS)
    out = client.entry_to_dict(conn.entries[0]) if conn.entries else None
    conn.unbind()
    if out:
        out = _enrich_user(out)
    return out


def create_user(dn: str, attrs: dict, password: str,
                force_change: bool = True) -> dict:
    """Create a user and set its password. attrs: givenName, sn, sAMAccountName,
    userPrincipalName, displayName, mail, etc. (without CN — derived from dn)."""
    assert_writable(dn, attrs.get("sAMAccountName", ""))
    conn = client.get_connection()
    conn.add(dn, object_class=["top", "person", "organizationalPerson", "user"],
             attributes={k: v for k, v in attrs.items() if v is not None})
    # set password (must happen over LDAPS; account disabled until then)
    _set_unicode_pwd(conn, dn, password)
    # enable account + optional "must change at next logon"
    uac = UF_NORMAL_ACCOUNT
    conn.modify(dn, {"userAccountControl": [(ldap3.MODIFY_REPLACE, uac)]})
    if force_change:
        conn.modify(dn, {"pwdLastSet": [(ldap3.MODIFY_REPLACE, 0)]})
    conn.unbind()
    return get_user(dn)


def update_user(dn: str, changes: dict) -> dict:
    assert_writable(dn, _sam(dn))
    conn = client.get_connection()
    mods = {}
    for k, v in changes.items():
        mods[k] = [(ldap3.MODIFY_REPLACE, v if isinstance(v, list) else v)]
    conn.modify(dn, mods)
    conn.unbind()
    return get_user(dn)


def set_user_enabled(dn: str, enabled: bool) -> dict:
    assert_writable(dn, _sam(dn))
    conn = client.get_connection()
    conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE,
                attributes=["userAccountControl"])
    uac = int(conn.entries[0]["userAccountControl"].value)
    if enabled:
        uac &= ~UF_ACCOUNTDISABLE
    else:
        uac |= UF_ACCOUNTDISABLE
    conn.modify(dn, {"userAccountControl": [(ldap3.MODIFY_REPLACE, uac)]})
    conn.unbind()
    return get_user(dn)


def unlock_user(dn: str) -> dict:
    """Clear lockoutTime (0 = not locked). Does not reset password."""
    assert_writable(dn, _sam(dn))
    conn = client.get_connection()
    conn.modify(dn, {"lockoutTime": [(ldap3.MODIFY_REPLACE, 0)]})
    conn.unbind()
    return get_user(dn)


def delete_user(dn: str) -> None:
    assert_safe_to_delete(dn, _sam(dn))
    conn = client.get_connection()
    conn.delete(dn)
    conn.unbind()


# ─────────────────────────── PASSWORDS ───────────────────────────
def reset_password(dn: str, new_password: str, force_change: bool = True,
                   sam: str = "") -> None:
    """Admin reset (no knowledge of old password). Over LDAPS."""
    assert_writable(dn, sam or _sam(dn))
    conn = client.get_connection()
    _set_unicode_pwd(conn, dn, new_password)
    if force_change:
        conn.modify(dn, {"pwdLastSet": [(ldap3.MODIFY_REPLACE, 0)]})
    conn.unbind()


def change_password(dn: str, old: str, new: str, sam: str = "") -> None:
    """Self-service change (requires old password). Verifies old first.

    AD only allows a user to change their own password when they supply the
    correct current password. We bind as the user with `old`, then set
    unicodePwd to `new` over that authenticated (user-owned) connection.
    """
    assert_writable(dn, sam or _sam(dn))
    import ldap3
    from app.config import Config
    # Bind as the user with their CURRENT password (proves identity).
    tls = ldap3.Tls(validate=False)
    srv = ldap3.Server(Config.AD_HOST, port=Config.AD_LDAPS_PORT, use_ssl=True, tls=tls)
    auth = ldap3.NTLM if "\\" in dn else ldap3.SIMPLE
    uconn = ldap3.Connection(srv, user=dn, password=old,
                             authentication=auth, auto_bind=True)
    try:
        # Set the new password on the user's own authenticated connection.
        enc = ('"' + new + '"').encode("utf-16-le")
        uconn.modify(dn, {"unicodePwd": [(ldap3.MODIFY_REPLACE, enc)]})
    finally:
        uconn.unbind()


def set_must_change(dn: str, force: bool = True, sam: str = "") -> None:
    assert_writable(dn, sam or _sam(dn))
    conn = client.get_connection()
    conn.modify(dn, {"pwdLastSet": [(ldap3.MODIFY_REPLACE, 0 if force else -1)]})
    conn.unbind()


# ───────────────────────────── GROUPS ─────────────────────────────
def list_groups(search: str = "", size_limit: int = 200) -> list[dict]:
    conn = client.get_connection()
    flt = "(objectClass=group)"
    if search:
        safe = ldap3.utils.conv.escape_filter_chars(search)
        flt = f"(|(cn=*{safe}*)(sAMAccountName=*{safe}*)(displayName=*{safe}*))"
    conn.search(Config.AD_BASE_DN, flt, search_scope=ldap3.SUBTREE,
                attributes=["cn", "sAMAccountName", "distinguishedName",
                            "description", "member", "groupType"],
                size_limit=size_limit)
    out = [client.entry_to_dict(e) for e in conn.entries]
    conn.unbind()
    return out


def get_group(dn: str) -> Optional[dict]:
    conn = client.get_connection()
    conn.search(dn, "(objectClass=group)", search_scope=ldap3.BASE,
                attributes=["cn", "sAMAccountName", "distinguishedName",
                            "description", "member", "groupType"])
    out = client.entry_to_dict(conn.entries[0]) if conn.entries else None
    conn.unbind()
    return out


def create_group(dn: str, sam: str, desc: str = "", scope: str = "global") -> dict:
    assert_writable(dn)
    # groupType = scope flag OR'd with SECURITY flag (0x80000000).
    # GLOBAL=2, DOMAIN_LOCAL=4, UNIVERSAL=8; SECURITY = -2147483648 (0x80000000).
    scope_flag = {"global": 2, "domain": 4, "universal": 8}.get(scope, 2)
    gt = -2147483648 | scope_flag  # signed 32-bit security-enabled group
    conn = client.get_connection()
    attrs = {"sAMAccountName": sam, "groupType": gt}
    if desc:
        attrs["description"] = desc
    conn.add(dn, object_class=["top", "group"], attributes=attrs)
    conn.unbind()
    return get_group(dn)


def add_member(dn: str, member_dn: str) -> None:
    assert_writable(dn)
    conn = client.get_connection()
    conn.modify(dn, {"member": [(ldap3.MODIFY_ADD, member_dn)]})
    conn.unbind()


def remove_member(dn: str, member_dn: str) -> None:
    assert_writable(dn)
    conn = client.get_connection()
    conn.modify(dn, {"member": [(ldap3.MODIFY_DELETE, member_dn)]})
    conn.unbind()


def set_members(dn: str, member_dns: list[str]) -> None:
    """Replace the entire member set (used by 'copy group')."""
    assert_writable(dn)
    conn = client.get_connection()
    conn.modify(dn, {"member": [(ldap3.MODIFY_REPLACE, member_dns)]})
    conn.unbind()


def copy_group_members(source_dn: str, target_dn: str) -> dict:
    """Copy all members from source group into target group (additive)."""
    src = get_group(source_dn)
    if not src:
        raise ValueError("Source group not found")
    members = src.get("member", [])
    members = members if isinstance(members, list) else [members]
    if members:
        add_member(target_dn, members[0])
        conn = client.get_connection()
        conn.modify(target_dn, {"member": [(ldap3.MODIFY_ADD, m) for m in members[1:]]})
        conn.unbind()
    return get_group(target_dn)


def delete_group(dn: str) -> None:
    assert_safe_to_delete(dn)
    conn = client.get_connection()
    conn.delete(dn)
    conn.unbind()


# ───────────────────────────── OUs ────────────────────────────────
def list_ous(parent_dn: str = "") -> list[dict]:
    base = parent_dn or Config.AD_BASE_DN
    conn = client.get_connection()
    conn.search(base, "(objectClass=organizationalUnit)", search_scope=ldap3.LEVEL,
                attributes=["ou", "distinguishedName", "description"])
    out = [client.entry_to_dict(e) for e in conn.entries]
    conn.unbind()
    return out
