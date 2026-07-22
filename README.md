# AegisPass

Self-service Active Directory password reset and identity management portal — LDAPS-backed, scoped admin console, audit logging.

![status](https://img.shields.io/badge/status-active-FFB300?style=flat-square)
![language](https://img.shields.io/badge/python-3.11+-0d0d0c?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-FFB300?style=flat-square)

## Overview

AegisPass is a secure, self-service Active Directory password reset and identity management portal. End users can reset and expire their own passwords, enroll recovery factors, and Domain Admins get a scoped directory console — all over pinned LDAPS with no blind trust of system CAs.

## Features

- Self-service password change for regular users
- Admin dashboard with real-time KPIs, directory health, and activity status
- User, Group, and OU management (restricted to configured write scopes)
- Audit logging of privileged actions
- Pinned TLS to the domain controller — no blind trust of system CAs
- Safety denylist protects Tier-0 accounts and built-in containers
- Dark Amber Cyberpunk branding (accent #FFB300, JetBrains Mono)

## Architecture / Tech Stack

- **Backend**: Flask + Gunicorn (Python 3.11+)
- **Directory**: LDAPS / Global Catalog
- **Reverse Proxy**: Nginx (production)
- **Deployment**: systemd service, Docker

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your AD configuration, then chmod 600 .env

# Development
SESSION_COOKIE_SECURE=False python -c "from app import app; app.run(host='127.0.0.1', port=8000)"
```

For production, use `systemd/aegispass.service` and `deploy/nginx-aegispass.conf`.

## Configuration

| Variable | Description |
|----------|-------------|
| `SECRET_KEY_FLASK` | Flask session signing key |
| `AD_HOST` | Domain controller hostname |
| `AD_LDAPS_PORT` | LDAPS port (default: `636`) |
| `AD_BIND_USER` | Service account DN |
| `AD_BIND_PASSWORD` | Service account password |

See `.env.example` for full options.

## License

MIT — see [LICENSE](LICENSE).

---
Part of the JorahOne / J1 ecosystem — self-service AD identity management for enterprise environments.
