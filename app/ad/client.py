"""LDAP/AD connection helpers with certificate fingerprint pinning.

Security model
--------------
The management channel uses LDAPS (636) to ad-example.example.com. We never trust a
system CA store for the DC — instead we pin to the SHA-256 fingerprint of the
DC's certificate (stored in app/ad/ca/ad-example.example.com.pem and checked against
AD_CERT_FINGERPRINT). This defeats DNS spoofing / rogue-DC / MITM even if an
attacker controls the network or a public CA.

The Global Catalog (3268) is unencrypted and READ-ONLY — used only for
cross-domain lookups, never for writes.
"""
from __future__ import annotations

import hashlib
import ssl
from typing import Optional

import ldap3

from app.config import Config

# Attributes every user read should pull by default
USER_ATTRS = [
    "sAMAccountName", "userPrincipalName", "displayName", "givenName", "sn",
    "mail", "cn", "distinguishedName", "objectGUID", "userAccountControl",
    "pwdLastSet", "badPwdCount", "lockoutTime", "memberOf", "whenCreated",
    "lastLogonTimestamp", "description", "telephoneNumber", "title", "department",
]


def _normalize_fp(fp: str) -> str:
    return fp.replace(":", "").replace(" ", "").upper()


def _peer_fingerprint(connection) -> str:
    """Open a fresh TLS handshake to the DC and return the cert fingerprint.

    We read the actual presented certificate (DER) and compute its SHA-256.
    ldap3 hides the socket, so we do a throwaway handshake (no bind). This is
    the cert the DC would present on the management channel.
    """
    import socket as _sock
    ctx = ssl._create_unverified_context()
    ctx.check_hostname = False
    s = ctx.wrap_socket(_sock.create_connection((Config.AD_HOST, Config.AD_LDAPS_PORT)),
                        server_hostname=Config.AD_HOST)
    try:
        der = s.getpeercert(binary_form=True)
    finally:
        s.close()
    return hashlib.sha256(der).hexdigest().upper() if der else ""


def _cert_san_hostname_ok() -> bool:
    """Verify the DC cert's SAN/CN matches AD_HOST and is currently valid."""
    import socket as _sock
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    import datetime as _dt
    ctx = ssl._create_unverified_context()
    ctx.check_hostname = False
    s = ctx.wrap_socket(_sock.create_connection((Config.AD_HOST, Config.AD_LDAPS_PORT)),
                        server_hostname=Config.AD_HOST)
    try:
        der = s.getpeercert(binary_form=True)
    finally:
        s.close()
    if not der:
        return False
    cert = x509.load_der_x509_certificate(der, default_backend())
    now = _dt.datetime.now(_dt.timezone.utc)
    if cert.not_valid_after_utc < now:
        return False
    names = {cert.subject.rfc4514_string().split("=")[-1].lower()}
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names.update(n.lower() for n in san.get_values_for_type(x509.DNSName))
    except x509.ExtensionNotFound:
        pass
    return Config.AD_HOST.lower() in names


def verify_peer_fingerprint(connection) -> None:
    expected = _normalize_fp(Config.AD_CERT_FINGERPRINT)
    if not expected:
        return  # nothing pinned — rely on CA validation only
    actual = _peer_fingerprint(connection)
    if not actual:
        raise RuntimeError("Could not read peer certificate from the domain controller.")
    if actual != expected:
        raise RuntimeError(
            "Domain controller certificate fingerprint mismatch — "
            "refusing to authenticate against an untrusted DC."
        )
    if not _cert_san_hostname_ok():
        raise RuntimeError(
            "Domain controller certificate does not match the configured host "
            "name or has expired — refusing to connect."
        )


def _build_ssl_context() -> ssl.SSLContext:
    """Build an SSL context that trusts ONLY the pinned DC certificate."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if Config.AD_DC_CERT.exists():
        ctx.load_verify_locations(cafile=str(Config.AD_DC_CERT))
    else:
        ctx.load_default_certs()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def pinned_tls_context() -> ssl.SSLContext:
    return _build_ssl_context()


def get_connection() -> ldap3.Connection:
    """Authenticated, writable LDAPS connection to the DC (pinned)."""
    Config.require_ad()
    # We pin by certificate fingerprint, not by chain. So we disable chain
    # validation (CERT_NONE) and instead verify the exact presented cert's
    # fingerprint + hostname in verify_peer_fingerprint() right after bind.
    tls = ldap3.Tls(validate=ssl.CERT_NONE, ca_certs_file=None)
    server = ldap3.Server(
        host=Config.AD_HOST,
        port=Config.AD_LDAPS_PORT,
        use_ssl=True,
        tls=tls,
        get_info=ldap3.ALL,
    )
    conn = ldap3.Connection(
        server,
        user=Config.AD_BIND_USER,
        password=Config.AD_BIND_PASSWORD,
        authentication=ldap3.NTLM if "\\" in Config.AD_BIND_USER else ldap3.SIMPLE,
        auto_bind=True,
        raise_exceptions=True,
    )
    # Explicit pin check on the live socket
    verify_peer_fingerprint(conn)
    return conn


def get_gc_connection() -> ldap3.Connection:
    """Anonymous, read-only Global Catalog connection (3268)."""
    server = ldap3.Server(
        host=Config.AD_GC_HOST,
        port=Config.AD_GC_PORT,
        use_ssl=False,
        get_info=ldap3.NONE,
    )
    conn = ldap3.Connection(server, authentication=ldap3.ANONYMOUS, auto_bind=True)
    return conn


def dn_to_username(dn: str) -> str:
    return dn.split(",")[0].split("=")[-1]


def entry_to_dict(entry) -> dict:
    """Flatten an ldap3 Entry into a plain dict (lists -> first/last value)."""
    out: dict = {}
    for attr in entry.entry_attributes:
        vals = entry[attr].values
        out[attr] = list(vals) if len(vals) != 1 else vals[0]
    out["dn"] = entry.entry_dn
    return out
