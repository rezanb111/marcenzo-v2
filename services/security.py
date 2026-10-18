"""
Security helpers: PBKDF2 password hashing, captcha, constant-time compare, rate limit.
"""
from __future__ import annotations

import hashlib
import secrets
import random
import time
from typing import Tuple, Dict

_rate_buckets: Dict[str, list] = {}


def generate_salt(length: int = 16) -> str:
    return secrets.token_hex(length)


def hash_password(password: str, salt: str, iterations: int = 120_000) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return dk.hex()


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    if not salt or not stored_hash:
        return False
    calc = hash_password(password, salt)
    return secrets.compare_digest(calc, stored_hash)


def generate_math_captcha() -> Tuple[str, int]:
    a = random.randint(5, 25)
    b = random.randint(3, 15)
    op = random.choice(["+", "-", "*"])
    if op == "+":
        ans = a + b
        q = f"{a} + {b}"
    elif op == "-":
        if a < b:
            a, b = b, a
        ans = a - b
        q = f"{a} - {b}"
    else:
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        ans = a * b
        q = f"{a} × {b}"
    return q, ans


def generate_mixed_captcha() -> Tuple[str, str]:
    word = "MARCENZO"
    idx = random.randint(0, len(word) - 1)
    letter = word[idx].lower()
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    math_ans = a + b
    q = f"Type the letter at position {idx + 1} of '{word}' followed by {a}+{b} (no spaces)"
    expected = f"{letter}{math_ans}"
    return q, expected


def rate_limit(key: str, max_hits: int = 8, window_sec: float = 10.0) -> bool:
    """Return True if ALLOWED, False if rate-limited."""
    now = time.monotonic()
    bucket = _rate_buckets.setdefault(key, [])
    cutoff = now - window_sec
    bucket[:] = [t for t in bucket if t >= cutoff]
    if len(bucket) >= max_hits:
        return False
    bucket.append(now)
    return True


def mask_address(addr: str) -> str:
    if not addr or len(addr) < 12:
        return "—"
    return f"{addr[:6]}…{addr[-4:]}"


def mask_tx(tx: str) -> str:
    if not tx or len(tx) < 14:
        return tx or "—"
    return f"{tx[:10]}…{tx[-6:]}"
