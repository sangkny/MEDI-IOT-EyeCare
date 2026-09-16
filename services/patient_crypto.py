"""Patient name encryption-at-rest for MEDI /patients API (Fernet).

Screening path (mvp/clinical-screening) does NOT store patient names —
this module applies only when Patient records are created via /patients.

Key injection:
  MEDI_PATIENT_ENCRYPTION_KEY = url-safe base64 Fernet key (32 url-safe bytes)

Generate (do not commit output):
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Never log the key or plaintext names.
"""
from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("services.patient_crypto")

_PREFIX = "fernet:v1:"


def _fernet() -> Fernet | None:
    raw = (os.getenv("MEDI_PATIENT_ENCRYPTION_KEY") or "").strip()
    if not raw:
        return None
    return Fernet(raw.encode("utf-8") if isinstance(raw, str) else raw)


def encrypt_patient_name(plaintext: str) -> str:
    """Encrypt name for storage. Without key, refuse in production-ish modes."""
    f = _fernet()
    if f is None:
        mode = (os.getenv("MEDI_ENV") or os.getenv("APP_ENV") or "development").lower()
        if mode in {"production", "pilot", "staging"}:
            raise RuntimeError("MEDI_PATIENT_ENCRYPTION_KEY required for patient name storage")
        # Development fallback: store with explicit marker (not claimed as AES)
        log.warning("patient_name_stored_without_encryption key_absent=true")
        return f"plaintext:dev:{plaintext}"
    token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt_patient_name(stored: str | None) -> str | None:
    if not stored:
        return None
    if stored.startswith("plaintext:dev:"):
        return stored[len("plaintext:dev:") :]
    if not stored.startswith(_PREFIX):
        # Legacy plaintext rows (pre-MVP-04C)
        return stored
    f = _fernet()
    if f is None:
        raise RuntimeError("MEDI_PATIENT_ENCRYPTION_KEY required to decrypt stored names")
    try:
        return f.decrypt(stored[len(_PREFIX) :].encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("invalid encrypted patient name token") from exc


def encryption_status() -> dict:
    return {
        "key_configured": _fernet() is not None,
        "algorithm": "fernet_aes128_cbc_hmac",
        "library": "cryptography.fernet",
        "applies_to": "patients.name_encrypted via /patients API",
        "screening_path": "not_applicable_no_name_storage",
    }
