# AegisPass

![license](https://img.shields.io/badge/license-MIT-amber)
![status](https://img.shields.io/badge/status-OPERATIONAL-amber)
![stack](https://img.shields.io/badge/stack-Flask%20%7C%20LDAPS-amber)

A secure, self-service Active Directory password reset and identity management portal. AegisPass lets end users reset/expire their own passwords, enroll MFA and recovery factors, and gives Domain Admins a read-only-to-privileged directory console — all over pinned LDAPS.

> Branded in the **Dark Amber Cyberpunk** style (accent `#FFB300`, JetBrains Mono).

## 🚀 Features

- **AegisPass branded login** with large animated seal and live **Services status** panel.
- **Multi-format login** — `firstname.lastname`, `name@example.com`, or `@example.com` alias.
- **Self-service password change** for regular users.
- **Modern admin dashboard** with real-time KPIs, directory health, activity feed, services status, and device fleet status.
- **User, Group, and OU management** (Domain Admins only for writes).
- **Audit logging** of privileged actions.
- **Pinned TLS** to the domain controller — no blind trust of system CAs.
- **Safety denylist** protects Tier-0 accounts and built-in containers.

## 📸 Screenshots (sanitized)

Screenshots show aggregate counts and service health only. No individual staff data is exposed.

- `screenshots/login.png` — Branded login page with live services status.
- `screenshots/dashboard.png` — Hero greeting, KPI cards, quick actions, directory health, services status, device fleet status.

## 🔒 Security

- Credentials live in `.env` (chmod 600, gitignored).
- The pinned DC certificate is tracked in `app/ad/ca/` (public cert, not secret).
- All privileged actions are written to `logs/audit.log`.
- Writable operations are scoped to configured OUs; Tier-0 objects are protected.
- Session cookies are signed and configurable as Secure / HttpOnly / SameSite.

## 🛠️ Deployment

### Requirements

- Python 3.11+
- Linux server with network access to the domain controller.
- AD service account with appropriate permissions.

### Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with real values, then chmod 600 .env

SESSION_COOKIE_SECURE=False python -c "from app import app; app.run(host='0.0.0.0', port=8000)"
```

> For production, use a WSGI server such as Gunicorn behind a reverse proxy with HTTPS.

### Environment variables

```bash
AD_HOST=ad-example.example.com
AD_PORT=636
AD_BIND_USER=CN=AegisPass Service Account,OU=Service Accounts,DC=example,DC=com
AD_BIND_PASSWORD=...
AD_BASE_DN=DC=example,DC=com
DOMAIN_ADMINS_GROUP=CN=Domain Admins,CN=Users,DC=example,DC=com
ADMIN_TAB_ENABLED=True
```

## 🧪 Live sample data shown in screenshots

Aggregate status only:

- **Users:** 8,445 total · 277 active · 0 locked
- **Groups:** 763
- **Devices:** 1,840 total · 1,464 active · 376 disabled · 86 servers · 1,631 workstations
- **Services:** Directory services, Secure channel, Single sign-on, API services — all operational
- **Latency:** ~2 ms

> These are real production totals from the author's environment and are safe to share because they contain no hostnames, IPs, individual names, or credentials.

## 📦 Files

- `app/` — Flask application
  - `ad/` — LDAP client, operations, health, safety
  - `auth/` — login/logout, SSO negotiation
  - `routes/` — UI and API blueprints
  - `templates/` — Jinja2 templates
  - `static/` — CSS, JS, AegisPass assets
- `scripts/` — utility scripts
- `logs/` — audit log (created at runtime, gitignored)
- `.env.example` — template for credentials
- `requirements.txt`

## 📝 License

Internal-use project for AegisPass. Contact the IT team before redistribution.
