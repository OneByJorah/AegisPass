# AegisPass

<div align="center">

![AegisPass Banner](docs/assets/banner.svg)

**Self-service Active Directory password management with real-time safety guards, workflow automation, and SSO/Kerberos support.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LDAP](https://img.shields.io/badge/LDAP-Active%20Directory-00599C?logo=microsoftactive-directory&logoColor=white)](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/get-started/virtual-dc/active-directory-domain-services-overview)

[Quick Start](#quick-start) · [Features](#features) · [Architecture](#architecture) · [Configuration](#configuration) · [Deployment](#deployment) · [Contributing](#contributing)

</div>

---

## Overview

AegisPass is a Flask-based web application that gives end users secure self-service access to common Active Directory operations — password resets, account unlocks, MFA enrollment — while enforcing safety guards on privileged Tier-0 objects and surfacing every action through audit logs.

| Capability | Detail |
|---|---|
| Self-service enrollment | Users register recovery profiles and set up TOTP-based MFA |
| Password management | Self-service reset with configurable expiry reminders via workflow engine |
| Tier-0 safety guards | Prevents accidental or malicious changes to Domain Admins, KRBTGT, and other critical AD objects |
| SSO / Kerberos | Optional GSSAPI-based single sign-on for domain-joined machines |
| Workflow engine | Password expiry notifications and approval chains |
| Audit logging | Every action logged with user, timestamp, and result |
| Global Catalog | Read-only lookups across the forest on port 3268 |
| PWA | Offline-capable progressive web app with service worker |

---

## Features

### Self-Service Enrollment
Users register a recovery profile (security questions, phone number, email) and enroll TOTP-based multi-factor authentication via any authenticator app.

### Password Management
End users reset expired or forgotten passwords through the web portal. Expiry reminders are delivered through the workflow engine at configurable intervals.

### Tier-0 AD Safety Guards
Changes to high-privilege accounts (Domain Admins, KRBTGT, Enterprise Admins, Schema Admins) are blocked or require elevated approval, preventing catastrophic misconfigurations.

### Workflow Engine
Automated notifications for password expiry, account lockout events, and approval chains for privileged operations. Configurable via environment variables.

### SSO / Kerberos
Domain-joined machines authenticate automatically using GSSAPI. Falls back to username/password when Kerberos is unavailable.

### Global Catalog
Read-only forest-wide lookups on port 3268 for user discovery and group membership queries without binding to individual domain controllers.

### Audit Trail
Every password reset, enrollment, and workflow action is logged with user identity, timestamp, source IP, and result for compliance reporting.

### PWA Support
Service worker enables offline access to static assets and cached pages. Installable on mobile and desktop for a native-like experience.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (PWA)                     │
│            Flask SPA + Service Worker               │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP :8000
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Gunicorn (2 workers)                │
│                  ┌──────────────┐                   │
│                  │  Flask App   │                   │
│                  └──────┬───────┘                   │
│         ┌───────────────┼───────────────┐           │
│         ▼               ▼               ▼           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │   Routes   │  │   Safety   │  │  Workflow  │    │
│  │ ui / api / │  │   Guards   │  │   Engine   │    │
│  │ enrollment │  │            │  │            │    │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │
│        │               │               │            │
│        └───────────────┼───────────────┘            │
│                        ▼                            │
│               ┌───────────────┐                     │
│               │  AD Connector │                     │
│               │  (ldap3)      │                     │
│               └───────┬───────┘                     │
└───────────────────────┼─────────────────────────────┘
                        │ LDAP/389  GC/3268
                        ▼
              ┌──────────────────┐
              │  Active Directory │
              │  Domain Forest    │
              └──────────────────┘
```

### Project Structure

```
AegisPass/
├── app/
│   ├── ad/                    # Active Directory connector (ldap3)
│   ├── auth/                  # Authentication (LDAP bind, Kerberos/GSSAPI)
│   ├── routes/
│   │   ├── ui.py              # Web UI routes (login, dashboard, enrollment)
│   │   ├── api.py             # REST API endpoints
│   │   ├── enrollment.py      # Self-service enrollment flow
│   │   ├── workflows.py       # Password expiry reminders, approval chains
│   │   └── __init__.py        # Blueprint registration
│   ├── static/                # CSS, JS, images, service worker
│   └── templates/             # Jinja2 HTML templates
├── docs/assets/               # Screenshots, banner SVG
├── Dockerfile                 # python:3.11-slim + gunicorn
├── docker-compose.yml         # Single-service deployment
├── requirements.txt           # Python dependencies
├── .env.example               # 47 configuration variables
├── LICENSE                    # MIT
└── README.md
```

---

## Configuration

AegisPass is configured entirely through environment variables. Copy `.env.example` to `.env` and set the required values.

### Flask / General

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | Flask secret key for sessions |
| `FLASK_ENV` | `production` | `production` or `development` |
| `PORT` | `8000` | Server listen port |
| `ALLOWED_HOSTS` | `*` | Comma-separated hostnames |

### Active Directory Management

| Variable | Default | Description |
|---|---|---|
| `AD_SERVER` | — | Domain controller hostname or IP |
| `AD_PORT` | `389` | LDAP port |
| `AD_USE_SSL` | `true` | Use LDAP over SSL (636) |
| `AD_BASE_DN` | — | Base DN for user searches (e.g. `DC=example,DC=com`) |
| `AD_BIND_DN` | — | Service account DN for write operations |
| `AD_BIND_PASSWORD` | — | Service account password |
| `AD_USER_SEARCH_BASE` | — | OU/container to search for users |
| `AD_GROUP_SEARCH_BASE` | — | OU/container to search for groups |

### Global Catalog (Read-Only)

| Variable | Default | Description |
|---|---|---|
| `GC_SERVER` | — | Global Catalog server hostname |
| `GC_PORT` | `3268` | Global Catalog LDAP port |

### Slack Integration

| Variable | Default | Description |
|---|---|---|
| `SLACK_WEBHOOK_URL` | — | Slack incoming webhook for notifications |
| `SLACK_CHANNEL` | — | Target channel |

### reCAPTCHA

| Variable | Default | Description |
|---|---|---|
| `RECAPTCHA_SITE_KEY` | — | Google reCAPTCHA v2 site key |
| `RECAPTCHA_SECRET_KEY` | — | Google reCAPTCHA v2 secret key |

### Email / SMTP

| Variable | Default | Description |
|---|---|---|
| `SMTP_SERVER` | — | SMTP relay hostname |
| `SMTP_PORT` | `587` | SMTP port (TLS) |
| `SMTP_USERNAME` | — | SMTP auth username |
| `SMTP_PASSWORD` | — | SMTP auth password |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `EMAIL_FROM` | — | Sender address |
| `EMAIL_SUBJECT_PREFIX` | `[AegisPass]` | Subject line prefix |

### SMS (Gammu / Twilio / Mock)

| Variable | Default | Description |
|---|---|---|
| `SMS_PROVIDER` | `mock` | `gammu`, `twilio`, or `mock` |
| `TWILIO_ACCOUNT_SID` | — | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | — | Twilio auth token |
| `TWILIO_FROM_NUMBER` | — | Twilio sender phone number |

### Company / Branding

| Variable | Default | Description |
|---|---|---|
| `COMPANY_NAME` | `AegisPass` | Display name |
| `APP_NAME` | `AegisPass` | Application title |
| `APP_TAGLINE` | `Self-service AD management` | Tagline |

> **Note:** All variables are optional for local development. Production deployments require at minimum `SECRET_KEY`, `AD_SERVER`, `AD_BASE_DN`, `AD_BIND_DN`, and `AD_BIND_PASSWORD`.

---

## Quick Start

### Using Docker (Recommended)

```bash
git clone https://github.com/OneByJorah/AegisPass.git
cd AegisPass

# Configure
cp .env.example .env
# Edit .env with your AD credentials and settings

# Build and run
docker compose up -d

# Open
open http://localhost:8000
```

### Local Development

```bash
git clone https://github.com/OneByJorah/AegisPass.git
cd AegisPass

python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt

cp .env.example .env
# Edit .env

python app.py
```

### Verify Health

```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

---

## Deployment

### Docker Compose

```yaml
services:
  aegispass:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

### Production Considerations

- Set `FLASK_ENV=production` and generate a strong `SECRET_KEY`.
- Place behind a reverse proxy (nginx, Caddy) with TLS termination.
- Configure a real SMTP server for email notifications.
- Switch `SMS_PROVIDER` to `twilio` or `gammu` for production SMS.
- Restrict `ALLOWED_HOSTS` to your domain.
- Enable LDAP over SSL (port 636) for AD communication.

---

## Security

- All actions logged to audit trail with user, timestamp, IP, and result.
- Tier-0 AD objects (Domain Admins, KRBTGT, Enterprise Admins, Schema Admins) are protected by safety guards.
- reCAPTCHA on login page to prevent brute-force attempts.
- Non-root Docker container via `appuser`.
- Secrets managed through environment variables, never committed to source control.

Report security vulnerabilities privately via [GitHub Security Advisories](https://github.com/OneByJorah/AegisPass/security/advisories/new).

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -m "Add my feature"`)
4. Push to branch (`git push origin feature/my-feature`)
5. Open a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**[AegisPass](https://github.com/OneByJorah/AegisPass)** · Built by [OneByJorah](https://github.com/OneByJorah)

</div>
