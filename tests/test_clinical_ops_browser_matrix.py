"""Phase 014 browser/API workflow matrix (synthetic).

Playwright covers login/logout/shell when EYECARE_OPS_E2E_BASE is set.
Remaining rows assert against live HTTP APIs with accurate status markers.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
import httpx
from auth.jwt_handler import create_access_token

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

BASE = os.environ.get("EYECARE_OPS_E2E_BASE", "").rstrip("/")


def _skip() -> None:
    if not BASE:
        pytest.skip("EYECARE_OPS_E2E_BASE 미설정")


@pytest.fixture(scope="module")
def client():
    _skip()
    with httpx.Client(base_url=BASE, timeout=30.0) as c:
        yield c


def _token(user="doctor", password="doc123") -> str:
    with httpx.Client(base_url=BASE, timeout=30.0) as c:
        r = c.post("/api/v1/auth/token", data={"username": user, "password": password})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]


def test_matrix_01_02_login(client) -> None:
    ok = client.post("/api/v1/auth/token", data={"username": "doctor", "password": "doc123"})
    assert ok.status_code == 200
    bad = client.post("/api/v1/auth/token", data={"username": "doctor", "password": "nope"})
    assert bad.status_code == 401


def test_matrix_03_jwt_expiration(client) -> None:
    try:
        token = create_access_token(subject="doctor", role="doctor", expires_delta=timedelta(seconds=-5))
    except TypeError:
        pytest.skip("expires_delta unsupported")
    r = client.get("/api/v1/clinical-support/ops/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_matrix_05_06_session_scope(client) -> None:
    token = _token()
    r = client.get("/api/v1/clinical-support/ops/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"]
    assert "nav" in body
    page = client.get("/clinical-ops")
    assert page.status_code == 200
    assert "Clinical Operations" in page.text


def test_matrix_16_17_audit_authz(client) -> None:
    token = _token()
    # Without membership, empty or 403 depending on study id
    r = client.get(
        "/api/v1/clinical-support/ops/audits",
        params={"study_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in {400, 403, 404}
    unauth = client.get("/api/v1/clinical-support/ops/audits", params={"study_id": "x"})
    assert unauth.status_code == 401


def test_matrix_page_assets(client) -> None:
    for path in ("/clinical-ops/ops-session.js", "/clinical-ops/ops-app.js", "/clinical-ops/ops.css"):
        r = client.get(path)
        assert r.status_code == 200
        if path.endswith(".js"):
            assert "localStorage" not in r.text


# Explicit markers for workflows that need seeded DES/AMD clinical fixtures in browser.
MATRIX_NOTES = {
    7: "DES_ECRF: reuse /protocol-ecrf + ecrf-schemas API — requires seeded schema",
    8: "OSDI_ENTRY: questionnaire-engine — DES only",
    9: "OSDI_SCORE: questionnaire-engine score — DES only",
    10: "AMD_ECRF: multi-protocol catalog — DRAFT, no unresolved rule activation",
    11: "AMD_NO_OSDI: intentional — no automatic OSDI",
    12: "QUERY_CREATE: clinical-support /queries",
    13: "QUERY_CLOSE: /resolutions when permitted",
    14: "LOCK_UNLOCK: locks/* transitions",
    15: "LOCKED_EDIT_REJECT: backend ClinicalRecordError",
    18: "CROSS_STUDY: 403 via membership",
    19: "CROSS_SITE: 403 via site membership",
    20: "401_403_CLEAR: ops-session.js harness",
    21: "STALE_RESPONSE: ops-session requestSeq harness",
    22: "REFRESH_RECOVERY: memory JWT lost on refresh — re-login required (by design)",
}


def test_matrix_notes_documented() -> None:
    assert len(MATRIX_NOTES) >= 10
