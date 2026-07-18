"""Flask app factory + blueprint wiring."""
from __future__ import annotations

import os
from flask import Flask, jsonify

from app.config import Config
from app.auth import bp as auth_bp
from app.routes import api_bp
from app.routes import ui_bp
from app.routes import workflows_bp
from app.routes import enrollment_bp


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    # Trust nginx reverse proxy headers
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)

    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
        "SESSION_COOKIE_SECURE", "True").lower() in ("1", "true", "yes")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = Config.SESSION_LIFETIME_MINUTES * 60
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(ui_bp)
    app.register_blueprint(workflows_bp, url_prefix="/api")
    app.register_blueprint(enrollment_bp, url_prefix="/api")

    @app.route("/health")
    def health():
        from app.ad.health import ldap_ping
        ok = ldap_ping()
        return jsonify({"status": "ok" if ok else "degraded",
                        "directory": "online" if ok else "offline"}), 200 if ok else 503

    @app.route("/health/ldap")
    def health_ldap():
        from app.ad.health import ldap_ping
        return jsonify({"ldap": "up" if ldap_ping() else "down"})

    @app.route("/status.json")
    def status_json():
        from app.ad.health import status
        return jsonify(status())

    return app


app = create_app()
