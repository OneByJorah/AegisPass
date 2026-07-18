"""Auth blueprint: login (form + SSO Negotiate), logout, current user."""
from __future__ import annotations

import base64
from flask import Blueprint, request, redirect, url_for, session, jsonify, current_app

from app.auth import sso
from app.config import Config

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _resolve_user(identifier: str) -> dict:
    """Look up the AD user (by sAMAccountName OR dn) for the session."""
    from app.ad import operations
    try:
        if identifier.upper().startswith("CN="):
            u = operations.get_user(identifier)
            if u:
                return u
        users = operations.list_users(search=identifier, size_limit=10)
        for u in users:
            if u.get("sAMAccountName", "").lower() == identifier.lower():
                return u
    except Exception:
        pass
    return {"sAMAccountName": identifier, "displayName": identifier}


@bp.route("/login", methods=["GET", "POST"])
def login():
    # --- SSO path: REMOTE_USER set by front proxy (preferred) ---
    if sso.remote_user_trusted() and request.environ.get("REMOTE_USER"):
        sam = sso.map_remote_user_to_sam(request.environ["REMOTE_USER"])
        session["user"] = _resolve_user(sam)
        session["auth_method"] = "sso"
        return redirect(url_for("ui.dashboard"))

    # --- SSO path: Negotiate token presented by the browser ---
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Negotiate ") and sso.sso_enabled():
        token = auth.split(" ", 1)[1].strip()
        principal, out_token = sso.negotiate_response(token)
        if principal:
            sam = sso.map_remote_user_to_sam(principal)
            session["user"] = _resolve_user(sam)
            session["auth_method"] = "sso"
            resp = redirect(url_for("ui.dashboard"))
            if out_token:
                resp.headers["WWW-Authenticate"] = "Negotiate " + out_token
            return resp
        # negotiation incomplete — reply with a challenge
        if out_token:
            return jsonify({"auth": "negotiate", "token": out_token}), 401, \
                {"WWW-Authenticate": "Negotiate " + out_token}

    # --- Form path (fallback / manual) ---
    if request.method == "POST":
        ident = (request.form.get("username") or "").strip()
        pw = request.form.get("password") or ""
        if not ident or not pw:
            return jsonify({"result": 0, "error": "Enter your username and password."})
        ok, info, dn = _verify_credentials(ident, pw)
        if ok:
            session["user"] = _resolve_user(dn or ident)
            session["auth_method"] = "form"
            return jsonify({"result": 1, "info": "Login successful."})
        return jsonify({"result": 0, "error": info})
    return jsonify({"result": 0, "error": "Use POST to log in."})


def _verify_credentials(ident: str, pw: str):
    """Verify a user's credentials by binding to LDAPS as them.

    Accepts sAMAccountName, UPN (name@example.com) or firstname.lastname.
    Returns (ok, message, dn).
    """
    import ldap3
    user_dn = _dn_for_login(ident)
    if not user_dn:
        return False, "Username not found or password incorrect.", None
    try:
        tls = ldap3.Tls(validate=False)
        srv = ldap3.Server(Config.AD_HOST, port=Config.AD_LDAPS_PORT, use_ssl=True, tls=tls)
        auth = ldap3.NTLM if "\\" in user_dn else ldap3.SIMPLE
        c = ldap3.Connection(srv, user=user_dn, password=pw,
                             authentication=auth, auto_bind=True)
        c.unbind()
        return True, "ok", user_dn
    except ldap3.LDAPBindError:
        return False, "Username not found or password incorrect.", None
    except Exception:
        return False, "Authentication service unavailable.", None


def _dn_for_login(identifier: str):
    """Resolve a login identifier to a user DN.

    Accepts several formats:
      • sAMAccountName        e.g. 'jdoe'
      • UPN / email           e.g. 'jdoe@example.com' or 'jane.doe@example.com'
      • firstname.lastname    e.g. 'jane.doe' (matched against sAMAccountName,
                               mail, or userPrincipalName local-part)
    Returns the DN or None.
    """
    from app.ad import operations
    ident = identifier.strip()
    if not ident:
        return None
    if "@" in ident:
        # UPN or email — exact match against userPrincipalName / mail
        try:
            users = operations.list_users(search=ident.split("@")[0], size_limit=20)
            for u in users:
                upn = (u.get("userPrincipalName") or "").lower()
                mail = (u.get("mail") or "").lower()
                if upn == ident.lower() or mail == ident.lower():
                    return u.get("dn")
            # Convenience: 'name@example.com' is the canonical UPN suffix
            if ident.lower().endswith("@example.com"):
                alt = ident.rsplit("@", 1)[0] + "@example.com"
                for u in users:
                    if (u.get("userPrincipalName") or "").lower() == alt:
                        return u.get("dn")
        except Exception:
            pass
        return None
    # bare name (sAMAccountName or firstname.lastname)
    try:
        users = operations.list_users(search=ident, size_limit=20)
        for u in users:
            sam = (u.get("sAMAccountName") or "").lower()
            if sam == ident.lower():
                return u.get("dn")
            # firstname.lastname -> match local-part of UPN/mail or sam
            if "." in ident:
                local = ident.lower().split("@")[0]
                upn_local = (u.get("userPrincipalName") or "").lower().split("@")[0]
                mail_local = (u.get("mail") or "").lower().split("@")[0]
                if local and (upn_local == local or mail_local == local or sam == local):
                    return u.get("dn")
    except Exception:
        pass
    return None


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("ui.login_page"))
