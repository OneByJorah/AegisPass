<div align="center">
  <img src="https://img.shields.io/badge/ASP.NET-512BD4?style=for-the-badge&logo=dotnet&logoColor=white">
  <img src="https://img.shields.io/badge/Active%20Directory-0078D4?style=for-the-badge&logo=microsoft&logoColor=white">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white">
</div>

<br>

<div align="center">
  <h1>AegisPass</h1>
  <p><strong>Self-Service AD Password Reset Portal</strong></p>
  <p>LDAPS, admin console, and audit logging for Active Directory.</p>
  <p>
    <a href="#features">Features</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#contributing">Contributing</a>
  </p>
</div>

---

## Screenshot

![AegisPass Dashboard](docs/screenshot.png)
*Self-service Active Directory password reset portal.*

## Features

- **Self-Service Reset** — Employees reset their own AD password.
- **LDAPS Support** — Secure LDAP connections to Active Directory.
- **Admin Console** — Manage users, OUs, and portal settings.
- **Audit Logging** — Track all password reset attempts.
- **Policy Enforcement** — Enforces AD password policies.
- **Email Notifications** — Alert admins of failed attempts.
- **ASP.NET Core** — Modern .NET backend.
- **Docker Support** — Easy deployment.

## Quick Start

```bash
git clone https://github.com/OneByJorah/AegisPass.git
cd AegisPass

cp .env.example .env
docker compose up -d
```

Open **http://localhost:5000** in your browser.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AD_LDAP_SERVER` | — | Domain controller hostname |
| `AD_LDAP_PORT` | `636` | LDAPS port |
| `AD_BASE_DN` | — | Base DN for user searches |
| `AD_SERVICE_ACCOUNT` | — | Service account username |
| `AD_SERVICE_PASSWORD` | — | Service account password |
| `ADMIN_EMAIL` | — | Admin email for notifications |
| `PORT` | `5000` | Application port |

## Project Structure

```
AegisPass/
├── Controllers/
│   ├── HomeController.cs
│   ├── PasswordController.cs
│   └── AdminController.cs
├── Services/
│   ├── ActiveDirectoryService.cs
│   ├── AuditService.cs
│   └── EmailService.cs
├── Views/                   # Razor views
├── wwwroot/                 # Static assets
├── docker-compose.yml
└── README.md
```

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

## Security

For security concerns, see [SECURITY.md](SECURITY.md). Please report vulnerabilities to **info@jorahone.com** — do not use public issues.

## License

MIT © Jhonattan L. Jimenez

---

<div align="center">
  <p>Self-service Active Directory password reset.</p>
  <p><a href="https://github.com/OneByJorah">@OneByJorah</a></p>
</div>
