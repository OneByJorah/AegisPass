# Security Policy — aegispass

This document describes the threat model, the certificate-pinning approach, how
secrets are handled, the safety denylist, and how to rotate the pinned Domain
Controller certificate. It is intended for operators and auditors.

---

## 1. Threat model

aegispass is an internal tool that writes to a production Active Directory
domain (`example.com`). The primary adversary classes we defend against are:

| Threat                                   | Mitigation                                                        |
|------------------------------------------|-------------------------------------------------------------------|
| Network MITM / rogue Domain Controller   | **SHA-256 certificate fingerprint pinning** on LDAPS `636`.       |
| DNS spoofing to a fake DC                | Pin is by exact cert fingerprint + hostname/SAN check, not by name resolution. |
| Leak of internal topology via the UI     | Login status panel reports only booleans (reachable / pin OK / SSO) — never hostnames, IPs, DNs, or the fingerprint value. |
| Accidental destruction of Tier-0 objects | Built-in denylist + `assert_writable` / `assert_safe_to_delete` guards. |
| Over-broad write surface                 | `AD_WRITE_SCOPE_OU` confines all writes/deletes to allowed OUs.   |
| Compromise of the web tier               | App trusts only `REMOTE_USER` from the fronting proxy; no direct exposure; loopback-only bind. |
| Credential theft from the repo           | Bind credentials live only in gitignored `.env`; never in source. |

**Out of scope / assumptions**

- The fronting proxy (nginx/Apache with `mod_auth_gssapi`) is trusted to
  authenticate users and set `REMOTE_USER` correctly.
- The DC itself and its private key are trusted (standard AD trust boundary).
- The operator machine used to edit `.env` is trusted.

---

## 2. Certificate fingerprint pinning

The management channel to the DC uses **LDAPS on port 636**. We do **not** rely
on the operating system CA store or on hostname-only validation, because both
can be defeated by an attacker who controls a public CA or the local network.

Instead, aegispass pins to the **SHA-256 fingerprint** of the DC's leaf
certificate:

1. The configured fingerprint lives in `AD_CERT_FINGERPRINT` (colon-separated
   hex, e.g. `AB:CD:…:EF`).
2. On every bind, `app/ad/client.py → verify_peer_fingerprint()` opens a fresh
   TLS handshake to the DC, reads the **actual presented certificate (DER)**,
   and computes its SHA-256.
3. If the computed fingerprint does **not** equal the pinned value, the
   connection is refused with *"Domain controller certificate fingerprint
   mismatch — refusing to authenticate against an untrusted DC."*
4. The cert's **SAN/CN is additionally checked** against `AD_HOST` and its
   validity period is verified (`_cert_san_hostname_ok()`). Expired or
   hostname-mismatched certs are refused.
5. The SSL context (`_build_ssl_context()`) also loads the pinned public cert
   from `app/ad/ca/ad-example.example.com.pem` and sets `CERT_REQUIRED` + hostname
   checking.

This means a successful LDAP bind is only possible against the exact DC
certificate whose fingerprint was pinned — defeating rogue-DC, MITM, and
cert-swap attacks even if an attacker controls DNS or a CA.

---

## 3. `.env` handling

- **All secrets are environment-driven.** `app/config.py` reads everything from
  the environment (via `python-dotenv` loading the project-root `.env`).
- **`.env` is gitignored.** The repository `.gitignore` excludes `.env`, `*.key`,
  `*.pem`, and `app/ad/ca/*.pem` (except the tracked `.gitkeep`). Committed
  secrets are therefore structurally prevented.
- **`.env.example` is safe to commit** — it contains only placeholders and
  non-secret defaults.
- **File permissions.** Deploy `.env` as `0600` owned by the service account.
- **Rotation.** Rotate `AD_BIND_PASSWORD` and `SECRET_KEY_FLASK` by editing
  `.env` and restarting the service. Never paste secrets into chat, tickets, or
  commit messages.

---

## 4. Safety denylist (`app/ad/safety.py`)

Every write path must call `assert_writable(dn)` and every delete path must call
`assert_safe_to_delete(dn)` before touching the directory.

- **Protected by default** (Tier-0 / built-ins): `Administrator`, `krbtgt`,
  `Guest`, `Domain Admins`, `Enterprise Admins`, `Schema Admins`,
  `Administrators`, `Cert Publishers`, `Domain Controllers`,
  `Read-Only Domain Controllers`, `Group Policy Creator Owners`,
  `RAS and IAS Servers`, `Enterprise Read-Only Domain Controllers`,
  `Denied RODC Password Replication Group`, `Protected Users`, and the
  `OU=Domain Controllers`, `CN=Users`, `CN=Builtin`, and `OU=Service Accounts`
  containers.
- **`AD_PROTECT_DENYLIST`** — comma-separated extra DNs/names that are always
  forbidden, merged with the built-in set.
- **`AD_WRITE_SCOPE_OU`** — comma-separated OUs. When set, writes/deletes are
  allowed **only** under those OUs, for *all* objects (not just Tier-0). This is
  the strongest guard and is **recommended for production**.

The denylist is evaluated case-insensitively and matches by exact DN, by
`sAMAccountName`/CN, and by OU containment, so even renamed-but-equivalent
objects remain protected.

---

## 5. TLS notes & ports

| Port | Protocol | Direction | Usage                                | Encrypted? |
|------|----------|-----------|--------------------------------------|------------|
| 636  | LDAPS    | Writable  | All user/group management & password operations. Pinned by SHA-256. | **Yes (TLS, pinned)** |
| 3268 | Global Catalog | Read-only | Cross-domain searches / lookups. Never used for writes. | No (anonymous RO) |

- **636 is the only channel that can modify the directory**, and it is pinned.
- **3268 (Global Catalog) is read-only and unencrypted** by design in AD; it is
  used strictly for searches and must never receive write requests. The app's
  `get_gc_connection()` binds anonymously and only ever issues search
  operations.
- Keep the DC's LDAPS certificate with a strong key (≥ RSA 2048 / ECDSA P-256)
  and a sane validity window.

---

## 6. Rotating the pinned certificate

When the DC's LDAPS certificate is renewed (or you move to a new DC), update the
pin:

1. **Obtain the new cert's SHA-256 fingerprint** from the DC (colon-separated):

   ```bash
   # From a trusted host with openssl:
   openssl s_client -connect ad-example.example.com:636 2>/dev/null \
     | openssl x509 -noout -fingerprint -sha256
   ```

   Or verify what the app would compute against the live DC:

   ```bash
   # compare against the value printed by scripts/_ad_discover.py
   python scripts/_ad_discover.py
   ```

2. **Update `AD_CERT_FINGERPRINT`** in `.env` to the new value.

3. **(Optional) Refresh the pinned public cert** used by the SSL context:

   ```bash
   openssl s_client -connect ad-example.example.com:636 2>/dev/null \
     | openssl x509 -outform PEM > app/ad/ca/ad-example.example.com.pem
   ```

   (`app/ad/ca/*.pem` is gitignored; keep it on the deployment host only.)

4. **Validate before restarting in prod:**

   ```bash
   python scripts/_ad_test_bind.py
   # Expect: BOUND OK as <bind-user> ... RESULT: PASS
   ```

5. **Restart the service** (`sudo systemctl restart aegispass`, or
   recreate the container). If the fingerprint is wrong, the app will refuse to
   bind and log a *fingerprint mismatch* error — fail closed, never silently.

---

## 7. Responsible disclosure

We take security reports seriously. **Please do not open public GitHub issues for
vulnerabilities.**

- Email: **security@aegispass.example.com** (PGP encouraged)
- Alternatively, contact the AegisPass IT security team through the internal ticketing
  system, marked *Confidential – Security*.

We will acknowledge receipt within **3 business days**, provide a remediation
timeline, and coordinate disclosure. Credit will be given to reporters who wish
to be named.

---

## 8. Reporting checklist for operators

- [ ] `.env` is `0600` and gitignored; no secrets in git history.
- [ ] `AD_WRITE_SCOPE_OU` is set in production.
- [ ] `AD_CERT_FINGERPRINT` matches the current DC cert (verified via
      `_ad_test_bind.py`).
- [ ] gunicorn binds `127.0.0.1:8000` only; nginx/Apache fronts it with TLS.
- [ ] `mod_auth_gssapi` sets `REMOTE_USER`; the app is not directly reachable.
- [ ] The login status panel shows no internal names/IPs to clients.
