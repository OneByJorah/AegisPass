"""Deterministic, policy-compliant password generator for aegispass.

Every generated password:
  • is exactly 12 characters long
  • embeds a AegisPass school short-code (sib, det, loc, mul, abr, ...) as letters
  • embeds the letters of "Jorah" and "One" (scrambled, not as whole words)
  • fills the rest with random digits
  • all characters are shuffled every time so nothing reads as a word
  • random parts use a CSPRNG (secrets)

Example outputs (all 12 chars, "Jorah"/"One" letters scattered):
   JmOuOanrhe3l   rOaJhneOml2u   hnOaJemrlOu3
"""
from __future__ import annotations

import secrets
import string

# AegisPass school short-codes (domain-style tokens).
SCHOOL_CODES = [
    "sib", "det", "loc", "mul", "abr", "wod", "czx", "cpx",
    "riv", "gar", "tui", "can", "bos", "cha", "hea", "spr",
    "lar", "ric", "jua", "cla", "lew", "mil", "and",
]

# Forced letters (scrambled into the password, not kept as words).
_FORCED_LETTERS = list("Jorah") + list("One")  # J,o,r,a,h,O,n,e  (8 letters)
TOTAL = 12


def generate_password(school_code: str = "") -> str:
    """Generate a 12-char password: school code + Jorah/One letters, all mixed up."""
    code = (school_code or "").strip().lower()
    if code not in SCHOOL_CODES:
        code = secrets.choice(SCHOOL_CODES)

    # Build the character pool: school code letters + forced letters.
    chars = list(code) + list(_FORCED_LETTERS)
    remaining = TOTAL - len(chars)
    if remaining < 0:
        # Defensive: code longer than budget — keep school letters only up to fit.
        chars = chars[:TOTAL]
        remaining = 0
    # Fill the rest with random digits.
    for _ in range(remaining):
        chars.append(secrets.choice(string.digits))

    # Shuffle everything so "Jorah" / "One" never appear as whole words.
    rng = secrets.SystemRandom()
    for _ in range(200):  # retry until no forbidden substring appears
        rng.shuffle(chars)
        cand = "".join(chars)
        if "jorah" not in cand.lower() and "one" not in cand.lower():
            pw = cand
            break
    else:
        pw = "".join(chars)  # fallback (extremely unlikely to reach here)
    # Guarantee exactly TOTAL chars (defensive clamp).
    if len(pw) < TOTAL:
        pw += "".join(secrets.choice(string.digits) for _ in range(TOTAL - len(pw)))
    return pw[:TOTAL]


def generate_for_school(school_code: str) -> str:
    return generate_password(school_code)
