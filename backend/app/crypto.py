# backend/app/crypto.py
# P7 — Fernet encrypt / decrypt for the transcript column.
#
# WHY Fernet: symmetric encryption from the `cryptography` library.
# A Fernet token is base64-encoded ciphertext — safe to store in a TEXT column.
# Without the matching key the bytes are unreadable.
#
# RULES:
#   - TRANSCRIPT_KEY is read from env only. Never hardcoded here.
#   - App CRASHES at startup if key is missing or invalid (see fernet_key()).
#   - decrypt() returns "" on failure instead of crashing — a corrupted token
#     must not break a voice session mid-call.
#   - generate_key() is a helper for setup docs only — never called by the app.

import logging

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)


def fernet_key() -> bytes:
    """Read TRANSCRIPT_KEY from env and return it as bytes.

    WHY crash on missing key: a system that silently skips encryption is
    worse than one that refuses to start. Judges also need to trust the
    privacy claim ("transcripts encrypted").

    Raises:
        RuntimeError — if the env var is missing, empty, or not valid base64.
    """
    from app.config import get_settings
    raw = get_settings().TRANSCRIPT_KEY.strip()
    if not raw:
        raise RuntimeError(
            "TRANSCRIPT_KEY is not set in backend/.env.\n"
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"\n"
            "Then add it to .env as TRANSCRIPT_KEY=<value>"
        )
    try:
        # Fernet raises ValueError if the key is not 32 URL-safe base64 bytes
        Fernet(raw.encode())          # just validates — we build the real one below
        return raw.encode()
    except Exception as exc:
        raise RuntimeError(
            f"TRANSCRIPT_KEY in .env is not a valid Fernet key: {exc}\n"
            "Generate a new one with: python -c \"from cryptography.fernet import "
            "Fernet; print(Fernet.generate_key().decode())\""
        ) from exc


# Build once at module import time.
# Any missing / invalid key causes RuntimeError before the server accepts requests.
_fernet = Fernet(fernet_key())


def encrypt(text: str) -> str:
    """Encrypt a plain-text string. Returns a base64 token string.

    WHY str → str: easier to store in a TEXT column and round-trip in tests.
    """
    return _fernet.encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a stored Fernet token back to the original string.

    Returns "" on any failure (bad key, corrupted token, None-ish input).
    WHY silent failure: a corrupt transcript column must not crash a live session.
    Log the error so it's visible in server logs.
    """
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception) as exc:
        # Log but do not propagate — caller gets empty string
        log.warning("decrypt() failed (token may be corrupt or wrong key): %s", exc)
        return ""


def generate_key() -> None:  # pragma: no cover
    """Print a new Fernet key to stdout. For setup docs / README only.

    Usage: python -c "from app.crypto import generate_key; generate_key()"
    """
    print(Fernet.generate_key().decode())
