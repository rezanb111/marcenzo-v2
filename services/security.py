"""
Security helpers: PBKDF2 password hashing, captcha generation.
"""
from __future__ import annotations

import hashlib
import secrets
import random
from typing import Tuple


def generate_salt(length: int = 16) -> str:
    return secrets.token_hex(length)


def hash_password(password: str, salt: str, iterations: int = 100_000) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return dk.hex()


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    return hash_password(password, salt) == stored_hash


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
