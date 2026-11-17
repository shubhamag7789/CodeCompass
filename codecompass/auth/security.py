from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Tuple


PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> Tuple[str, str]:
    """Generates a secure salt and PBKDF2-HMAC-SHA256 hash for the given password."""
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return pw_hash, salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Verifies a password against the stored salt and hash using timing-safe comparison."""
    if not password or not salt or not expected_hash:
        return False
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return hmac.compare_digest(pw_hash, expected_hash)


def generate_session_token() -> str:
    """Generates a cryptographically strong 64-character bearer session token."""
    return secrets.token_hex(32)


RECOVERY_WORD_LIST = (
    "anchor", "beacon", "breeze", "canyon", "castle", "cipher", "comet", "compass",
    "crater", "crystal", "delta", "eagle", "ember", "falcon", "forest", "galaxy",
    "glacier", "harbor", "horizon", "island", "jasper", "jungle", "jupiter", "lagoon",
    "lantern", "matrix", "meteor", "nebula", "nexus", "oasis", "orbit", "phoenix",
    "planet", "prism", "pulsar", "quantum", "radar", "river", "rocket", "shadow",
    "shield", "sierra", "signal", "silver", "solar", "stream", "summit", "timber",
    "topaz", "torrent", "valley", "vector", "vertex", "vortex", "voyage", "zenith",
)


def generate_recovery_passphrase(word_count: int = 4) -> str:
    """Generates a memorable, cryptographically secure multi-word recovery passphrase."""
    chosen = [secrets.choice(RECOVERY_WORD_LIST) for _ in range(word_count)]
    return "-".join(chosen)


