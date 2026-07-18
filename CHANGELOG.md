# Changelog

All notable changes to **aegispass** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-07-18

### Initial release

First public/internal release of aegispass, integrating the PyPass and
AD-Passreset-Portal upstream projects with the existing AegisPass self-service portal
clone under a single, security-hardened Flask application.

#### Added
- **Secure LDAP management channel** to the `example.com` Domain Controller
  (`ad-example.example.com`, `<DC-IP>`) over **LDAPS 636** with **SHA-256
  certificate fingerprint pinning** (`AD_CERT_FINGERPRINT`). Connections to a
  non-matching DC are refused (fail-closed).
- **Read-only Global Catalog** support on port **3268** for cross-domain
  searches and lookups (never used for writes).
- **SSO login** via Kerberos/Negotiate (`mod_auth_gssapi` on nginx/Apache) with
  a **password-form fallback** for non-domain-joined clients.
- **Non-sensitive login status panel** reporting AD reachability, TLS-pin
  validity, and SSO availability without leaking internal hostnames/IPs.
- **User management**: create, read, update, disable/enable, unlock, delete.
- **Password operations**: reset, set, and force-change-at-next-logon.
- **Group management**: create, read, add/remove members, and copy group
  memberships between users.
- **OU browser** for navigating the directory tree.
- **Safety denylist** (`app/ad/safety.py`) protecting Tier-0 / privileged
  objects (`Administrator`, `krbtgt`, `Domain Admins`, `Enterprise Admins`,
  `Domain Controllers` OU, and other built-ins) via `assert_writable()` and
  `assert_safe_to_delete()` guards.
- **Configurable write scope** (`AD_WRITE_SCOPE_OU`) confining all writes/deletes
  to explicitly allowed organizational units.
- **`.env`-based configuration** — bind credentials and the Flask secret key are
  stored only in a gitignored `.env` (template shipped as `.env.example`).
- **Deployment support**: venv + gunicorn + nginx/systemd, and Docker.
- **Credentials verification helper** (`scripts/_ad_test_bind.py`) to validate
  the pinned LDAPS bind before launch.
- Optional integrations: Slack notifications and reCAPTCHA on public forms.
- **Upstream integration & attribution**: PyPass (ZioGuillo), AD-Passreset-Portal
  (phibu), and the AegisPass self-service portal clone, preserved under `legacy/` and
  credited in the README; all under the MIT License.

#### Security
- Certificate pinning defeats rogue-DC / MITM / DNS-spoofing even against a
  compromised public CA or network.
- Global Catalog channel is strictly read-only.
- Every mutating operation passes through the Tier-0 denylist and (when set) the
  write-scope guard.
- `REMOTE_USER` from the trusted fronting proxy is the only accepted identity
  source; the app binds loopback-only (`127.0.0.1:8000`).

[1.0.0]: https://github.com/AegisPass-vi/aegispass/releases/tag/v1.0.0
