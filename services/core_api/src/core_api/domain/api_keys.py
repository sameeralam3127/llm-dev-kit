"""Workspace API keys: format, generation and verification.

A key looks like ``ldk_<prefix>_<secret>``:

* ``prefix`` (12 letters and digits) is stored in clear and finds the row.
* ``secret`` (64 hex characters, 256 random bits) is never stored.

The database keeps ``HMAC-SHA-256(pepper, key)``. The pepper is a server secret
that never touches the database, so a stolen dump cannot be used to test
guesses offline. A slow hash such as argon2 protects *low-entropy* secrets
(passwords); a 256-bit random key cannot be guessed, so a fast keyed hash is
enough and keeps every request fast (decision 2).

The ``ldk_`` format is distinct from v2's ``sk-ldk-`` personal keys, so the two
can never be mistaken for each other.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string
from dataclasses import dataclass

KEY_PREFIX = "ldk_"
_ALPHANUMERIC = string.ascii_letters + string.digits
_FORMAT = re.compile(r"^ldk_([A-Za-z0-9]{12})_([0-9a-f]{64})$")


@dataclass(frozen=True, slots=True)
class NewKey:
    """A freshly generated key. ``plaintext`` is shown to its owner exactly once."""

    plaintext: str
    prefix: str
    digest: bytes


def generate(pepper: bytes) -> NewKey:
    """Create a new key and the digest to store for it."""
    prefix = "".join(secrets.choice(_ALPHANUMERIC) for _ in range(12))
    plaintext = f"{KEY_PREFIX}{prefix}_{secrets.token_hex(32)}"
    return NewKey(plaintext=plaintext, prefix=prefix, digest=digest(plaintext, pepper))


def parse_prefix(candidate: str) -> str | None:
    """Return the lookup prefix of a well-formed key, or ``None``."""
    match = _FORMAT.match(candidate)
    return match.group(1) if match else None


def digest(plaintext: str, pepper: bytes) -> bytes:
    """``HMAC-SHA-256(pepper, key)``: what the database stores."""
    return hmac.new(pepper, plaintext.encode(), hashlib.sha256).digest()


def matches(plaintext: str, stored: bytes, pepper: bytes) -> bool:
    """Compare in constant time, so response timing reveals nothing about the key."""
    return hmac.compare_digest(digest(plaintext, pepper), stored)
