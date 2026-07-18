# Legacy Integration Notes — PyPass & AD-Passreset-Portal

This directory holds **read-only reference clones** of two upstream self-service
AD password-reset projects. They are NOT compiled or run. They exist only so we
can reuse ideas, config shapes, UI copy, and (for PyPass) MIT-licensed static
assets.

Cloned with `git clone --depth 1` on 2026-07-18. Their `.git` directories were
removed afterwards (see "Cleanup" below) so they don't pollute the VIDE-AD-Manager
repo.

| Repo | URL | License | Lang | Status here |
|------|-----|---------|------|-------------|
| PyPass | https://github.com/ZioGuillo/PYPASS | MIT (© 2018 Joseph N. Mutumi) | Python / Flask | Cloned + assets reused |
| AD-Passreset-Portal | https://github.com/phibu/AD-Passreset-Portal | MIT (© 2024–2026 phibu) | C#/.NET 10 + React | Reference only (not compiled) |

---

## 1. What PyPass provides (verified by reading the source)

PyPass is a small Flask app (`app/app.py`, `app/model.py`, `app/forms.py`,
`app/settings.py`) that does exactly one thing: let a user change their own AD
password from a browser.

- **Self-service reset flow** (`app/app.py::reset`): a single route `/` and
  `/reset` (GET+POST). A WTForms form (`app/forms.py::passwdchangeform`) collects
  `username`, current `password`, `new_password` (min length 8), and
  `confirm_password` (must equal `new_password`).
- **LDAP reset mechanics** (`app/model.py::reset_passwd`, verified):
  1. Binds as an **admin/service account** (`conx()` → `ldap3` over LDAPS 636,
     NTLM auth, TLSv1.2, `validate=CERT_NONE`).
  2. Looks up the target user's DN via a search filter that accepts
     `userPrincipalName`, `sAMAccountName`, or `mail`
     (`search_userx()` → `(&(|(userPrincipalName=X)(samaccountname=X)(mail=X))(objectClass=person))`).
  3. Re-authenticates the user with their **current** password (`authenticate()`)
     and returns `False` if that fails — i.e. you must prove current creds before
     a reset.
  4. Sets the new password by writing the UTF-16-LE quoted string to the
     `unicodePwd` attribute with `MODIFY_REPLACE` — the standard AD password
     write.
  5. (Optional) Posts a Slack notification to the user via `slack_sdk`
     (`WebClient.chat_postMessage`), looking the user up in a json DB by email.
- **reCAPTCHA**: via Flask-WTF `RecaptchaField` in `forms.py`, toggled by
  `RECAPTCHA_ENABLED` + presence of both keys in `settings.py`. Injected into the
  template only when enabled (`reset.html`).
- **Health check**: `GET /health/ldap` socket-probes port 636 and returns
  `{"ok": bool}` — used by the front-end "LDAP status" pill.
- **UI**: Bootstrap-flavored templates with a light/dark theme toggle
  (`main.js` + `content.css` vars), an LDAP reachability indicator, and a 404
  page. These are PyPass-authored (MIT) and were the only assets we reused.

### Important discrepancy (verified)
The task brief stated VIDE-AD-Manager "handles password reset server-side in
`app/ad/operations.py` already." **This file does not exist.** The current
`app/ad/` tree contains only:
- `app/ad/client.py` — `ldap3` connection helpers with **certificate-fingerprint
  pinning** (`verify_peer_fingerprint`, `pinned_tls_context`, `get_connection`,
  `get_gc_connection`). This is a *superset* of PyPass's TLS handling: VIDE pins
  the DC cert SHA-256 and validates hostname/expiry, whereas PyPass uses
  `validate=CERT_NONE` (no verification).
- `app/ad/safety.py` — `assert_writable` / `assert_safe_to_delete` Tier-0
  protection denylists (blocks Administrator, krbtgt, Domain Admins, etc.).
- `app/config.py` — `Config` already has `SLACK_BOT_TOKEN`, `SLACK_ACTIVATION`,
  `RECAPTCHA_PUBLIC/PRIVATE_KEY`, `RECAPTCHA_ENABLED`, and full AD settings.

So VIDE has the **building blocks** for reset (secure connection + safety guards
+ config for Slack/reCAPTCHA) but **no reset route or `operations.py` yet**.
PyPass's `reset_passwd` is the reference implementation to port into VIDE, not a
file that already exists.

---

## 2. How VIDE-AD-Manager absorbs PyPass (plan, not yet implemented)

- **Reset logic**: port `model.py::reset_passwd` into `app/ad/operations.py`
  using VIDE's existing `get_connection()` (pinned TLS) instead of PyPass's
  unverified `conx()`. Keep the "authenticate with current password first" gate
  and the `unicodePwd` UTF-16-LE write. Wrap the modify in `safety.assert_writable`
  so Tier-0 accounts can never be reset via the self-service path.
- **reCAPTCHA**: VIDE's `Config` already carries the keys/flag — wire
  Flask-WTF `RecaptchaField` (or a v3 verify) into the reset form as PyPass does.
- **Slack notify**: reuse `Config.SLACK_BOT_TOKEN` / `SLACK_ACTIVATION` exactly
  like PyPass's `model.py`; VIDE already has the config shape.
- **UI patterns**: PyPass's `reset.html` (flashed messages, error feedback per
  field, reCAPTCHA slot) and the theme/status pill in `content.css`+`main.js`
  inform VIDE's future `app/templates/` reset page. Copied assets live under
  `app/static/pypass/` (see section 3).
- **Health check**: the `GET /health/ldap` pattern (port-636 socket probe) is a
  good fit for VIDE's existing health story; only the concept is borrowed.

---

## 3. Reused MIT assets

From `legacy/PyPass` (MIT, © Joseph N. Mutumi) into `app/static/pypass/`:

| Source file | Destination | Why safe |
|-------------|-------------|----------|
| `app/static/js/main.js` | `app/static/pypass/js/main.js` | PyPass-authored; theme toggle + LDAP-status poller + loader |
| `app/static/css/content.css` | `app/static/pypass/css/content.css` | PyPass-authored; form + theme CSS vars (light/dark) |
| `app/static/images/favicon.png` | `app/static/pypass/images/favicon.png` | PyPass-authored; site icon |

Deliberately **NOT** copied:
- `app/static/js/*.min.js` (jquery, bootstrap, owl.carousel, etc.) — third-party
  vendored libs, not PyPass-authored; pull from a CDN or pin your own versions.
- `app/static/fonts/*`, `app/static/css/{bootstrap,ionicons,flaticon,...}.css`,
  `*.woff/*.ttf/*.eot` — third-party licensed (SIL OFL / vendor), not MIT, and
  not authored by PyPass.
- `app/src/name.crt`, `app/src/slack_db.json`, `app/src/config.json` — secrets /
  local config, must not be reused.

---

## 4. AD-Passreset-Portal (reference only — NOT reused)

.NET 10 / ASP.NET Core + React 19. It was cloned for **concepts and README
copy**, never compiled. Useful ideas to borrow (conceptually):
- **Breach check** via HaveIBeenPwned k-anonymity (password never leaves server).
- **Portal-level lockout** after N wrong attempts (protects AD from lockout).
- **Password strength meter** (zxcvbn) + on-demand generator.
- **Expiry reminder emails** + "must-change-at-next-logon" clearing.
- **SIEM/syslog forwarding** (RFC 5424) of security events, rate limiting,
  hardened security headers (CSP/HSTS/X-Frame-Options DENY).
- **Flexible username formats** (SAM / UPN / mail) — already matches PyPass's
  search filter.

It contains **no raw CSS/JS/images to borrow** (front-end is React/TS, no
standalone static assets), so nothing was copied to `app/static/`. Code is C#
and not portable to VIDE's Flask stack.

---

## 5. Cleanup

After cloning, the upstream `.git` metadata was removed so they don't pollute
VIDE-AD-Manager's own git history:

```
rm -rf legacy/PyPass/.git legacy/AD-Passreset-Portal/.git
```

The source trees remain so the code stays readable as reference.
