"""Hashing determinístico dos bytes canônicos adquiridos."""

import hashlib


def sha256_hex(payload: bytes) -> str:
    """Calcula SHA-256 hexadecimal sem transformar o payload."""
    return hashlib.sha256(payload).hexdigest()
