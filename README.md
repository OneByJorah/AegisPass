# AegisPass

![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Stack: Flask | LDAPS](https://img.shields.io/badge/stack-Flask%20%7C%20LDAPS-blue)

A secure, self-service Active Directory password reset and identity management portal. AegisPass lets end users reset/expire their own passwords, enroll recovery factors, and gives Domain Admins a scoped directory console — all over pinned LDAPS.

> Branded in the **Dark Amber Cyberpunk** style (accent `#FFB300`, JetBrains Mono).

## Features

- **Self-service password change** for regular users.
- **Admin dashboard** with real-time KPIs, directory health, and activity status.
- **User, Group, and OU management** (restricted to configured write scopes).
- **Audit logging** of privileged actions.
- **Pinned TLS** to the domain controller — no blind trust of system CAs.
- **Safety denylist** protects Tier-0 accounts and built-in containers.

## Tech Stack

- Python 3.11+
- Flask + Gunicorn
- LDAPS / Global Catalog
- Nginx reverse proxy (production)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with real values, then chmod 600 .env

SESSION_COOKIE_SECURE=False python -c "from app import app; app.run(host='127.0.0.1', port=8000)"
```

For production, use the provided `systemd/aegispass.service` and `deploy/nginx-aegispass.conf` behind Nginx with TLS.

## Usage

```bash
# Development
SESSION_COOKIE_SECURE=False python -c "from app import app; app.run(host='127.0.0.1', port=8000)"

# Production / systemd
./deploy/install.sh
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY_FLASK` | — | Flask session signing key |
| `AD_HOST` | `ad-example.example.com` | Domain controller hostname |
| `AD_LDAPS_PORT` | `636` | LDAPS port |
| `AD_BIND_USER` | — | Service account DN |
| `AD_BIND_PASSWORD` | — | Service account password |
| `AD_BASE_DN` | — | Active Directory base DN |
| `AD_WRITE_SCOPE_OU` | — | Comma-separated allowed write OUs |
| `DOMAIN_ADMINS_GROUP` | — | Domain Admins group DN |
| `ADMIN_TAB_ENABLED` | `True` | Enable admin tab |
| `SMS_PROVIDER` | `none` | none \| mock \| gammu \| twilio |
| `RECAPTCHA_ENABLED` | `False` | Enable reCAPTCHA v3 |

See `.env.example` for the full list.

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Report vulnerabilities privately to **info@jorahone.com** or use GitHub Security Advisories. See [SECURITY.md](SECURITY.md) for details.

## License

MIT © Jhonattan L. Jimenez
