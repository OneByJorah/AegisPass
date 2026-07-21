# Security Policy — AegisPass

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | ✅ |
| Older   | ❌ |

## Reporting a Vulnerability

Please do **not** open public GitHub issues for security vulnerabilities.

- Email: **info@jorahone.com**
- Or use GitHub Security Advisories

Please include:

- Type of issue and affected files
- Steps to reproduce
- Suggested impact
- Proof-of-concept if available

We will acknowledge receipt within **3 business days** and coordinate disclosure.

## Security Model

- All secrets live in `.env` (gitignored, chmod 600).
- The DC certificate fingerprint is pinned via `AD_CERT_FINGERPRINT`.
- Writable operations are confined to `AD_WRITE_SCOPE_OU`.
- Tier-0 objects are protected by a built-in safety denylist.
- Gunicorn binds to `127.0.0.1` only; terminate TLS at Nginx.
