"""Central configuration. All secrets come from the environment (.env, gitignored)."""
from __future__ import annotations
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env BEFORE reading any vars below (Config attributes are evaluated at
# import time, so env must be populated first).
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool = False) -> bool:
    v = _env(name)
    if not v:
        return default
    return v.lower() in ("1", "true", "yes", "on")


class Config:
    # Flask
    SECRET_KEY = _env("SECRET_KEY_FLASK", "change-me-in-production")
    SESSION_LIFETIME_MINUTES = int(_env("SESSION_LIFETIME_MINUTES", "30"))
    DEBUG = _bool("DEBUG", False)
    APP_NAME = _env("APP_NAME", "AegisPass")
    COMPANY = _env("COMPANY", "AegisPass")

    # Active Directory (writable, encrypted management channel)
    AD_HOST = _env("AD_HOST", "ad-example.example.com")
    AD_LDAPS_PORT = int(_env("AD_LDAPS_PORT", "636"))
    AD_DOMAIN = _env("AD_DOMAIN", "example.com")          # DNS domain for UPN/kerberos realm
    AD_BASE_DN = _env("AD_BASE_DN", "DC=example,DC=com")
    AD_BIND_USER = _env("AD_BIND_USER", "")
    AD_BIND_PASSWORD = _env("AD_BIND_PASSWORD", "")
    AD_DC_HOST = _env("AD_DC_HOST", AD_HOST)
    # SHA-256 fingerprint (colon-separated) of the DC cert we pin.
    AD_CERT_FINGERPRINT = _env("AD_CERT_FINGERPRINT", "").upper().replace(" ", "")

    # Global Catalog (read-only, cross-domain)
    AD_GC_HOST = _env("AD_GC_HOST", "ad-example.example.com")
    AD_GC_PORT = int(_env("AD_GC_PORT", "3268"))

    # Pinned DC certificate (public leaf cert, tracked in git)
    AD_CA_DIR = BASE_DIR / "app" / "ad" / "ca"
    AD_DC_CERT = AD_CA_DIR / "ad-example.example.com.pem"

    # SSO (Kerberos / Negotiate). When enabled, domain-joined browsers are
    # logged in automatically; the password form is the fallback.
    SSO_ENABLED = _bool("SSO_ENABLED", True)
    SSO_SERVICE_NAME = _env("SSO_SERVICE_NAME", "HTTP")  # HTTP/<hostname> principal
    SSO_KEYTAB = _env("SSO_KEYTAB", str(BASE_DIR / "app" / "ad" / "ca" / "http.keytab"))

    # Admin-only "Administration" tab (user creation workflow, etc.)
    # Set ADMIN_TAB_ENABLED=false to hide it for everyone.
    ADMIN_TAB_ENABLED = _bool("ADMIN_TAB_ENABLED", True)
    # DN of the group that may see/use the admin tab. Defaults to Domain Admins.
    DOMAIN_ADMINS_GROUP = _env(
        "DOMAIN_ADMINS_GROUP",
        "CN=Domain Admins,CN=Users," + AD_BASE_DN)

    # Optional integrations
    SLACK_BOT_TOKEN = _env("SLACK_BOT_TOKEN")
    SLACK_ACTIVATION = _bool("SLACK_ACTIVATION", False)
    RECAPTCHA_PUBLIC_KEY = _env("RECAPTCHA_PUBLIC_KEY")
    RECAPTCHA_PRIVATE_KEY = _env("RECAPTCHA_PRIVATE_KEY")
    RECAPTCHA_ENABLED = _bool("RECAPTCHA_ENABLED", False)

    # Email (internal district SMTP relay, no auth)
    SMTP_ENABLED = _bool("SMTP_ENABLED", False)
    ENROLL_KEY = _env("ENROLL_KEY")  # optional; falls back to SECRET_KEY
    SMTP_HOST = _env("SMTP_HOST", "smtp.example.com")
    SMTP_PORT = int(_env("SMTP_PORT", "25"))
    SMTP_SENDER = _env("SMTP_SENDER", "donoreply@example.com")
    SMTP_SENDER_NAME = _env("SMTP_SENDER_NAME", "AEGISPASS PASSWORD RESET")
    SMTP_USE_TLS = _bool("SMTP_USE_TLS", False)
    SMTP_SENDER_NAME = _env("SMTP_SENDER_NAME", "AEGISPASS PASSWORD RESET")
    SMTP_USE_TLS = _bool("SMTP_USE_TLS", False)
    ADMIN_ALERT_EMAIL = _env("ADMIN_ALERT_EMAIL", "Jhonattan.jimenez@example.com")
    EXPIRY_REMINDER_DAYS = [
        int(x) for x in _env("EXPIRY_REMINDER_DAYS", "7,3").split(",") if x.strip()
    ]

    # SMS gateway (self-hosted Gammu REST by default; "none" disables)
    SMS_PROVIDER = _env("SMS_PROVIDER", "none")
    SMS_GATEWAY_URL = _env("SMS_GATEWAY_URL", "")
    SMS_API_TOKEN = _env("SMS_API_TOKEN", "")
    TWILIO_ACCOUNT_SID = _env("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = _env("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM = _env("TWILIO_FROM", "")

    @classmethod
    def require_ad(cls) -> None:
        missing = [n for n in ("AD_BIND_USER", "AD_BIND_PASSWORD", "AD_CERT_FINGERPRINT")
                   if not getattr(cls, n)]
        if missing:
            raise RuntimeError(f"Missing required AD config: {', '.join(missing)}")


def load_dotenv_if_present() -> None:
    """Load .env from the project root if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except Exception:
        pass
