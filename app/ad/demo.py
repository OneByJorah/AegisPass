"""In-memory mock AD backend for DEMO_MODE.

Provides the same operations surface as app.ad.operations so the UI and API
render real screens without contacting a live directory. All data is synthetic:
fake names, example.com DNs, and no real hostnames or credentials.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.config import Config
from app.ad.safety import assert_writable, assert_safe_to_delete

_BASE_DN = Config.AD_BASE_DN or "DC=example,DC=com"
_USERS: list[dict] = [
    {
        "dn": f"CN=Demo User,OU=Users,{_BASE_DN}",
        "cn": "Demo User",
        "sAMAccountName": Config.DEMO_USERNAME or "demo.user",
        "displayName": "Demo User",
        "givenName": "Demo",
        "sn": "User",
        "userAccountControl": 512,
        "pwdLastSet": int((datetime.utcnow() - timedelta(days=10) - datetime(1601, 1, 1)).total_seconds() * 10_000_000),
        "memberOf": [f"CN=Domain Admins,CN=Users,{_BASE_DN}"],
        "description": "Demo administrator account",
        "locked": False,
    },
    {
        "dn": f"CN=Alice Admin,OU=Users,{_BASE_DN}",
        "cn": "Alice Admin",
        "sAMAccountName": "alice.admin",
        "displayName": "Alice Admin",
        "givenName": "Alice",
        "sn": "Admin",
        "userAccountControl": 512,
        "pwdLastSet": int((datetime.utcnow() - timedelta(days=5) - datetime(1601, 1, 1)).total_seconds() * 10_000_000),
        "memberOf": [f"CN=Domain Admins,CN=Users,{_BASE_DN}"],
        "description": "IT administrator",
        "locked": False,
    },
    {
        "dn": f"CN=Bob Example,OU=Users,{_BASE_DN}",
        "cn": "Bob Example",
        "sAMAccountName": "bob.example",
        "displayName": "Bob Example",
        "givenName": "Bob",
        "sn": "Example",
        "userAccountControl": 512,
        "pwdLastSet": int((datetime.utcnow() - timedelta(days=20) - datetime(1601, 1, 1)).total_seconds() * 10_000_000),
        "memberOf": [f"CN=IT Support,OU=Groups,{_BASE_DN}"],
        "description": "Standard user",
        "locked": False,
    },
    {
        "dn": f"CN=Carol Locked,OU=Users,{_BASE_DN}",
        "cn": "Carol Locked",
        "sAMAccountName": "carol.locked",
        "displayName": "Carol Locked",
        "givenName": "Carol",
        "sn": "Locked",
        "userAccountControl": 514,
        "pwdLastSet": int((datetime.utcnow() - timedelta(days=45) - datetime(1601, 1, 1)).total_seconds() * 10_000_000),
        "badPwdCount": 5,
        "lockoutTime": 1,
        "description": "Locked test account",
        "locked": True,
    },
]

_GROUPS: list[dict] = [
    {
        "dn": f"CN=Domain Admins,CN=Users,{_BASE_DN}",
        "cn": "Domain Admins",
        "sAMAccountName": "Domain Admins",
        "description": "Enterprise administrators",
        "member": [f"CN=Demo User,OU=Users,{_BASE_DN}", f"CN=Alice Admin,OU=Users,{_BASE_DN}"],
    },
    {
        "dn": f"CN=IT Support,OU=Groups,{_BASE_DN}",
        "cn": "IT Support",
        "sAMAccountName": "IT Support",
        "description": "Helpdesk team",
        "member": [f"CN=Bob Example,OU=Users,{_BASE_DN}"],
    },
]

_OUS: list[dict] = [
    {"dn": f"OU=Users,{_BASE_DN}", "ou": "Users", "description": "User accounts"},
    {"dn": f"OU=Groups,{_BASE_DN}", "ou": "Groups", "description": "Security groups"},
]


def _users():
    return _USERS


def _groups():
    return _GROUPS


def _user_by_dn(dn: str) -> Optional[dict]:
    for u in _users():
        if u["dn"].lower() == dn.lower():
            return u
    return None


def _group_by_dn(dn: str) -> Optional[dict]:
    for g in _groups():
        if g["dn"].lower() == dn.lower():
            return g
    return None


def _matches(search: str, obj: dict, keys: list[str]) -> bool:
    s = search.lower()
    return any(s in str(obj.get(k, "")).lower() for k in keys)


def is_domain_admin(sam: str) -> bool:
    if not sam:
        return False
    sam_l = sam.lower()
    admin_sams = {(Config.DEMO_USERNAME or "demo.user").lower(), "alice.admin"}
    if sam_l in admin_sams:
        return True
    for u in _users():
        if u.get("sAMAccountName", "").lower() == sam_l:
            for m in u.get("memberOf", []):
                if "domain admins" in m.lower():
                    return True
    return False


def count_users(conn=None) -> int:
    return len(_users())


def count_groups(conn=None) -> int:
    return len(_groups())


def device_status() -> dict:
    return {
        "total": 12,
        "active": 10,
        "disabled": 1,
        "workstations": 8,
        "servers": 3,
        "domain_controllers": 1,
        "stale": 1,
        "sites": {"Main Site": 8, "Branch": 4},
        "os": {"Windows": 8, "Windows Server": 4},
    }


def _enrich_user(u: dict) -> dict:
    out = dict(u)
    try:
        pls = out.get("pwdLastSet")
        if isinstance(pls, int) and pls:
            set_dt = datetime(1601, 1, 1) + timedelta(microseconds=pls // 10)
            out["passwordLastSet"] = set_dt
            out["passwordExpires"] = set_dt + timedelta(days=90)
    except Exception:
        pass
    return out


def list_users(search: str = "", scope: str = "subtree", size_limit: int = 200) -> list[dict]:
    out = [_enrich_user(dict(u)) for u in _users()]
    if search:
        out = [u for u in out if _matches(search, u, ["sAMAccountName", "cn", "displayName", "givenName", "sn"])]
    return out[:size_limit]


def get_user(dn: str) -> Optional[dict]:
    u = _user_by_dn(dn)
    return _enrich_user(dict(u)) if u else None


def create_user(dn: str, attrs: dict, password: str, force_change: bool = True) -> dict:
    assert_writable(dn, attrs.get("sAMAccountName", ""))
    name = dn.split(",")[0][3:] if dn.lower().startswith("cn=") else dn
    new = {
        "dn": dn,
        "cn": name,
        "sAMAccountName": attrs.get("sAMAccountName", name.lower().replace(" ", ".")),
        "displayName": attrs.get("displayName", name),
        "givenName": attrs.get("givenName", name.split()[0] if " " in name else name),
        "sn": attrs.get("sn", name.split()[-1] if " " in name else name),
        "userAccountControl": 512,
        "memberOf": [],
        "description": attrs.get("description", ""),
        "locked": False,
    }
    _users().append(new)
    return get_user(dn)


def update_user(dn: str, changes: dict) -> dict:
    assert_writable(dn, "")
    u = _user_by_dn(dn)
    if not u:
        raise ValueError("user not found")
    u.update(changes)
    return get_user(dn)


def set_user_enabled(dn: str, enabled: bool) -> dict:
    assert_writable(dn, "")
    u = _user_by_dn(dn)
    if not u:
        raise ValueError("user not found")
    uac = int(u.get("userAccountControl", 512))
    if enabled:
        uac &= ~2
    else:
        uac |= 2
    u["userAccountControl"] = uac
    return get_user(dn)


def unlock_user(dn: str) -> dict:
    assert_writable(dn, "")
    u = _user_by_dn(dn)
    if not u:
        raise ValueError("user not found")
    u["lockoutTime"] = 0
    u["badPwdCount"] = 0
    u["locked"] = False
    return get_user(dn)


def delete_user(dn: str) -> None:
    assert_safe_to_delete(dn, "")
    u = _user_by_dn(dn)
    if u and u in _USERS:
        _USERS.remove(u)


def reset_password(dn: str, new_password: str, force_change: bool = True, sam: str = "") -> None:
    assert_writable(dn, sam)
    u = _user_by_dn(dn)
    if not u:
        raise ValueError("user not found")
    u["pwdLastSet"] = int((datetime.utcnow() - datetime(1601, 1, 1)).total_seconds() * 10_000_000)
    if force_change:
        u["pwdLastSet"] = 0


def change_password(dn: str, old: str, new: str, sam: str = "") -> None:
    assert_writable(dn, sam or "")
    u = _user_by_dn(dn)
    if not u:
        raise ValueError("user not found")


def set_must_change(dn: str, force: bool = True, sam: str = "") -> None:
    assert_writable(dn, sam or "")
    u = _user_by_dn(dn)
    if u:
        u["pwdLastSet"] = 0 if force else int((datetime.utcnow() - datetime(1601, 1, 1)).total_seconds() * 10_000_000)


def list_groups(search: str = "", size_limit: int = 200) -> list[dict]:
    out = [dict(g) for g in _groups()]
    if search:
        out = [g for g in out if _matches(search, g, ["cn", "sAMAccountName", "description"])]
    return out[:size_limit]


def get_group(dn: str) -> Optional[dict]:
    g = _group_by_dn(dn)
    return dict(g) if g else None


def create_group(dn: str, sam: str, desc: str = "", scope: str = "global") -> dict:
    assert_writable(dn)
    name = dn.split(",")[0][3:] if dn.lower().startswith("cn=") else dn
    new = {"dn": dn, "cn": name, "sAMAccountName": sam, "description": desc, "member": []}
    _groups().append(new)
    return get_group(dn)


def add_member(dn: str, member_dn: str) -> None:
    assert_writable(dn)
    g = _group_by_dn(dn)
    if not g:
        raise ValueError("group not found")
    members = g.get("member", [])
    if isinstance(members, str):
        members = [members]
    if member_dn not in members:
        members.append(member_dn)
    g["member"] = members


def remove_member(dn: str, member_dn: str) -> None:
    assert_writable(dn)
    g = _group_by_dn(dn)
    if not g:
        raise ValueError("group not found")
    members = g.get("member", [])
    if isinstance(members, str):
        members = [members]
    g["member"] = [m for m in members if m.lower() != member_dn.lower()]


def set_members(dn: str, member_dns: list[str]) -> None:
    assert_writable(dn)
    g = _group_by_dn(dn)
    if g:
        g["member"] = list(member_dns)


def copy_group_members(source_dn: str, target_dn: str) -> dict:
    src = get_group(source_dn)
    if not src:
        raise ValueError("source group not found")
    members = src.get("member", [])
    if isinstance(members, str):
        members = [members]
    for m in members:
        add_member(target_dn, m)
    return get_group(target_dn)


def delete_group(dn: str) -> None:
    assert_safe_to_delete(dn)
    g = _group_by_dn(dn)
    if g and g in _GROUPS:
        _GROUPS.remove(g)


def list_ous(parent_dn: str = "") -> list[dict]:
    if parent_dn:
        return [dict(o) for o in _OUS if o["dn"].lower().endswith(parent_dn.lower()) or parent_dn.lower() in o["dn"].lower()]
    return [dict(o) for o in _OUS]
