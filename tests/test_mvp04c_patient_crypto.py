"""MEDI patient crypto unit tests (no real PHI)."""
from __future__ import annotations

import os

from cryptography.fernet import Fernet


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("MEDI_PATIENT_ENCRYPTION_KEY", key)
    # Import after env set — module reads env at call time
    from services.patient_crypto import decrypt_patient_name, encrypt_patient_name

    stored = encrypt_patient_name("TestSubject")
    assert stored.startswith("fernet:v1:")
    assert "TestSubject" not in stored
    assert decrypt_patient_name(stored) == "TestSubject"


def test_dev_fallback_without_key(monkeypatch):
    monkeypatch.delenv("MEDI_PATIENT_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("MEDI_ENV", "development")
    from services.patient_crypto import encrypt_patient_name

    stored = encrypt_patient_name("DevName")
    assert stored.startswith("plaintext:dev:")


def test_prod_refuses_without_key(monkeypatch):
    monkeypatch.delenv("MEDI_PATIENT_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("MEDI_ENV", "production")
    from services.patient_crypto import encrypt_patient_name

    try:
        encrypt_patient_name("X")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
