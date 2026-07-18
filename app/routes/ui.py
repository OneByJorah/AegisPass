"""UI blueprint: renders the SPA shell. All views are client-side; the
server only provides this single page + JSON APIs.

Legacy /<page> routes are kept as thin redirects to the SPA hash routes so old
bookmarks still work.
"""
from __future__ import annotations

from flask import Blueprint, render_template, session, redirect, url_for, request

from app.config import Config

bp = Blueprint("ui", __name__)


def _current_user():
    return session.get("user")


def _is_admin() -> bool:
    from app.ad import operations
    sam = (_current_user() or {}).get("sAMAccountName", "")
    return bool(Config.ADMIN_TAB_ENABLED and sam and operations.is_domain_admin(sam))


@bp.route("/")
def root():
    if not _current_user():
        return redirect(url_for("ui.login_page"))
    return redirect(url_for("ui.shell") + "#dashboard")


@bp.route("/login")
def login_page():
    from app.ad.health import status
    st = status()
    return render_template("auth/login.html",
                           status=st,
                           company=Config.COMPANY,
                           app_name=Config.APP_NAME,
                           sso_available=st.get("sso") == "available",
                           recaptcha=Config.RECAPTCHA_ENABLED)


@bp.route("/app")
def shell():
    if not _current_user():
        return redirect(url_for("ui.login_page"))
    from app.ad.health import status
    st = status()
    return render_template("base.html",
                           user=_current_user(),
                           company=Config.COMPANY,
                           app_name=Config.APP_NAME,
                           is_admin=_is_admin(),
                           sso_available=st.get("sso") == "available")


# Thin compatibility redirects to SPA hash routes
@bp.route("/dashboard")
@bp.route("/users")
@bp.route("/groups")
@bp.route("/ous")
@bp.route("/audit")
@bp.route("/self")
@bp.route("/admin")
def compat_redirects():
    if not _current_user():
        return redirect(url_for("ui.login_page"))
    view = request.path.strip("/") or "dashboard"
    return redirect(url_for("ui.shell") + "#" + view)
