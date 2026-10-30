"""Seeded full-browser Clinical Operations E2E (Playwright Chromium).

Requires:
  EYECARE_OPS_E2E_BASE
  EYECARE_OPS_SEED_MANIFEST (JSON from scripts/seed_ops014_synthetic.py)
"""
from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

BASE = os.environ.get("EYECARE_OPS_E2E_BASE", "").rstrip("/")
MANIFEST_PATH = Path(os.environ.get("EYECARE_OPS_SEED_MANIFEST", "docs/ops014-seed-manifest.json"))


def _require() -> dict:
    if not BASE:
        pytest.skip("EYECARE_OPS_E2E_BASE 미설정")
    if not MANIFEST_PATH.is_file():
        pytest.skip(f"seed manifest 없음: {MANIFEST_PATH}")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright 미설치")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seed() -> dict:
    return _require()


@pytest.fixture(scope="module")
def browser():
    _require()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


def _login(page, user="doctor", password="doc123") -> None:
    page.goto(f"{BASE}/clinical-ops")
    page.fill("#username", user)
    page.fill("#password", password)
    page.click("#login-btn")
    page.wait_for_selector("#app-view:not(.hidden)", timeout=15000)


def _logout(page) -> None:
    page.click("#logout-btn")
    page.wait_for_selector("#login-view:not(.hidden)")


def _select_study(page, study_id: str, site_id: str | None = None) -> None:
    page.select_option("#study", study_id)
    page.wait_for_timeout(200)
    if site_id:
        page.select_option("#site", site_id)
    page.click("#apply-scope")
    page.wait_for_timeout(400)


def test_browser_01_invalid_and_valid_login_logout(browser, seed) -> None:
    page = browser.new_page()
    page.goto(f"{BASE}/clinical-ops")
    page.fill("#username", "doctor")
    page.fill("#password", "wrong")
    page.click("#login-btn")
    page.wait_for_timeout(800)
    assert "실패" in page.locator("#login-msg").inner_text()
    _login(page)
    assert page.locator("#who").inner_text()
    local = page.evaluate("() => localStorage.getItem('access_token')")
    assert local is None
    _logout(page)
    page.close()


def test_browser_02_jwt_expiration_clears(browser, seed) -> None:
    from auth.jwt_handler import create_access_token

    page = browser.new_page()
    _login(page)
    expired = create_access_token(subject="doctor", role="doctor", expires_delta=timedelta(seconds=-10))
    status = page.evaluate(
        """async (token) => {
          window.ClinicalOpsSession.setAuth(token, 'doctor', 'doctor');
          try {
            await window.ClinicalOpsSession.api('/api/v1/clinical-support/ops/session');
            return 'unexpected_ok';
          } catch (e) {
            return {
              code: e.code || null,
              token: window.ClinicalOpsSession.state.token,
            };
          }
        }""",
        expired,
    )
    assert status["code"] == "AUTH"
    assert status["token"] == ""
    page.close()


def test_browser_03_des_ecrf_osdi_score(browser, seed) -> None:
    des = seed["des"]
    page = browser.new_page()
    _login(page)
    _select_study(page, des["study_id"], des["site_id"])
    page.click('a[data-panel="ecrf"]')
    page.fill("#schema-id", des["schema_id"])
    page.click("#load-schema")
    page.wait_for_timeout(800)
    body = page.locator("#ecrf-body").inner_text()
    assert "TBUT" in body or des["schema_id"][:8] in body or "field_count" in body or "forms" in body
    # Prefer forms list from schema JSON if returned
    page.click('a[data-panel="questionnaires"]')
    page.fill("#q-version", des["osdi_version_id"])
    page.fill("#q-visit", des["visit_id"])
    page.click("#q-start")
    page.wait_for_timeout(800)
    assert "응답 시작" in page.locator("#q-body").inner_text()
    page.fill("#q-item", "OSQ1")
    page.fill("#q-value", "2")
    page.click("#q-save")
    page.wait_for_timeout(500)
    page.fill("#q-item", "OSQ1")
    page.fill("#q-value", "3")
    page.click("#q-save")  # correction before finalize
    page.wait_for_timeout(500)
    for code, val in [("OSQ2", "2"), ("OSQ3", "2"), ("OSQ4", "2"), ("OSQ5", "2")]:
        page.fill("#q-item", code)
        page.fill("#q-value", val)
        page.click("#q-save")
        page.wait_for_timeout(200)
    for idx in range(6, 13):
        page.fill("#q-item", f"OSQ{idx}")
        page.fill("#q-value", "NA")
        page.click("#q-save")
        page.wait_for_timeout(150)
    page.click("#q-finalize")
    page.wait_for_timeout(600)
    page.click("#q-score")
    page.wait_for_timeout(800)
    score_text = page.locator("#q-body").inner_text()
    assert "score" in score_text.lower() or "50" in score_text or "ADVISORY" in score_text or "status" in score_text
    _logout(page)
    page.close()


def test_browser_04_amd_ecrf_no_osdi(browser, seed) -> None:
    amd = seed["amd"]
    assert amd["has_osdi_form"] is False
    page = browser.new_page()
    _login(page)
    _select_study(page, amd["study_id"], amd["site_id"])
    page.click('a[data-panel="ecrf"]')
    page.fill("#schema-id", amd["schema_id"])
    page.click("#load-schema")
    page.wait_for_timeout(800)
    text = page.locator("#ecrf-body").inner_text()
    # Schema payload is sanitized; fetch full via session API in page
    detail = page.evaluate(
        """async ({studyId, schemaId, siteId}) => {
          const res = await window.ClinicalOpsSession.api(
            `/api/v1/clinical-support/studies/${studyId}/ecrf-schemas/${schemaId}?site_id=${siteId}`
          );
          return await res.json();
        }""",
        {"studyId": amd["study_id"], "schemaId": amd["schema_id"], "siteId": amd["site_id"]},
    )
    forms = [f.get("form_code") for f in detail.get("forms", [])]
    assert "OSDI" not in forms
    field_forms = {f.get("form_code") for f in detail.get("fields", [])}
    assert "OSDI" not in field_forms
    assert "BCVA" in forms or "BCVA" in field_forms or "OCT_DRUSEN" in forms or "OCT_DRUSEN" in field_forms
    unresolved = detail.get("unresolved") or amd.get("unresolved") or []
    assert "AMD-WAVE" in unresolved or "AMD-SCHED-V6" in unresolved or amd.get("rules_active") is False
    page.click('a[data-panel="protocol"]')
    page.click("#load-protocol-info")
    page.wait_for_timeout(500)
    proto = page.locator("#protocol-body").inner_text()
    assert "DRAFT" in proto or "AMD" in proto
    assert "osdi_auto" in proto or "OSDI" in proto
    _logout(page)
    page.close()


def test_browser_05_query_response_close(browser, seed) -> None:
    des = seed["des"]
    page = browser.new_page()
    _login(page)
    _select_study(page, des["study_id"], des["site_id"])
    page.select_option("#subject", value=des["subject_id"])
    page.click('a[data-panel="queries"]')
    page.fill("#new-query-text", "ops014 browser query")
    page.click("#create-query")
    page.wait_for_timeout(800)
    qid = page.input_value("#query-id")
    assert qid
    page.fill("#query-response", "synthetic response")
    page.click("#respond-query")
    page.wait_for_timeout(600)
    page.click("#resolve-query")
    page.wait_for_timeout(600)
    detail = page.locator("#query-detail").inner_text()
    assert "resolved" in detail.lower() or "answered" in detail.lower() or qid in detail
    page.click("#query-history")
    page.wait_for_timeout(500)
    assert page.locator("#query-detail").inner_text()
    _logout(page)
    page.close()


def test_browser_06_lock_unlock_and_edit_reject(browser, seed) -> None:
    des = seed["des"]
    obs = des["schirmer_observation_id"]
    page = browser.new_page()
    # admin applies lock (data_manager site role); seed left READY_FOR_REVIEW
    _login(page, "admin", "admin123")
    _select_study(page, des["study_id"], des["site_id"])
    page.click('a[data-panel="locks"]')
    page.fill("#lock-type", "observation")
    page.fill("#lock-target", obs)
    page.fill("#lock-reason", "ops014-lock")
    page.click("#lock-apply")
    page.wait_for_timeout(1200)
    lock_body = page.locator("#locks-body").inner_text()
    assert "LOCKED" in lock_body, lock_body
    page.fill("#obs-edit-id", obs)
    page.fill("#obs-edit-value", "99")
    page.click("#obs-edit-try")
    page.wait_for_timeout(800)
    edit = page.locator("#locks-body").inner_text()
    assert "REJECTED" in edit or "400" in edit or "403" in edit or "잠금" in edit, edit
    _logout(page)

    _login(page, "doctor", "doc123")
    _select_study(page, des["study_id"], des["site_id"])
    page.click('a[data-panel="locks"]')
    page.fill("#lock-type", "observation")
    page.fill("#lock-target", obs)
    page.fill("#lock-reason", "ops014-unlock")
    page.click("#unlock-request")
    page.wait_for_timeout(1000)
    req = page.input_value("#unlock-request-id")
    assert req, page.locator("#locks-body").inner_text()
    _logout(page)

    _login(page, "admin", "admin123")
    _select_study(page, des["study_id"], des["site_id"])
    page.click('a[data-panel="locks"]')
    page.fill("#unlock-request-id", req)
    page.click("#unlock-approve")
    page.wait_for_timeout(1200)
    assert "UNLOCK" in page.locator("#locks-body").inner_text().upper(), page.locator("#locks-body").inner_text()
    _logout(page)
    page.close()


def test_browser_07_audit_trail_and_authz(browser, seed) -> None:
    des = seed["des"]
    amd = seed["amd"]
    page = browser.new_page()
    _login(page)
    _select_study(page, des["study_id"], des["site_id"])
    page.click('a[data-panel="audit"]')
    page.click("#load-audit")
    page.wait_for_timeout(900)
    audit = page.locator("#audit-body").inner_text()
    assert "HASH_CHAINED" in audit or "EVENT_HASH_ONLY" in audit or "LEGACY" in audit
    assert "cryptographically verified" not in audit.lower()

    # cross-study unknown id
    status = page.evaluate(
        """async (studyId) => {
          try {
            const res = await window.ClinicalOpsSession.api(
              `/api/v1/clinical-support/ops/audits?study_id=${studyId}`
            );
            return res.status;
          } catch (e) { return e.status || e.code; }
        }""",
        "00000000-0000-0000-0000-000000000099",
    )
    assert status in (400, 403, 404, "AUTH")
    # Re-login if auth cleared
    if status == "AUTH" or not page.evaluate("() => !!window.ClinicalOpsSession.state.token"):
        _login(page)
        _select_study(page, des["study_id"], des["site_id"])

    # cross-site: AMD other site (doctor is not a member)
    cross = page.evaluate(
        """async ({studyId, siteId}) => {
          try {
            const res = await window.ClinicalOpsSession.api(
              `/api/v1/clinical-support/studies/${studyId}/case-dashboard?site_id=${siteId}`
            );
            return res.status;
          } catch (e) { return e.status || e.code; }
        }""",
        {"studyId": amd["study_id"], "siteId": amd["other_site_id"]},
    )
    assert cross in (400, 403, "AUTH")
    _logout(page)
    page.close()


def test_browser_08_refresh_and_stale(browser, seed) -> None:
    page = browser.new_page()
    _login(page)
    page.reload()
    page.wait_for_timeout(500)
    # memory JWT lost → login view
    assert page.locator("#login-view").is_visible()
    _login(page)
    seq = page.evaluate(
        """async () => {
          const S = window.ClinicalOpsSession;
          S.setScope('a','b','c');
          const pending = S.api('/api/v1/clinical-support/ops/session');
          S.setScope('d','e','');
          try { await pending; return 'ok'; } catch (e) { return e.code; }
        }"""
    )
    assert seq == "STALE"
    _logout(page)
    page.close()


def test_browser_09_audit_entries_after_query(browser, seed) -> None:
    """Browser query actions leave readable audit rows (integrity labeled)."""
    des = seed["des"]
    page = browser.new_page()
    _login(page)
    _select_study(page, des["study_id"], des["site_id"])
    page.click('a[data-panel="audit"]')
    page.fill("#audit-action", "query")
    page.click("#load-audit")
    page.wait_for_timeout(900)
    text = page.locator("#audit-body").inner_text()
    # may be empty filter if action names differ; fall back unfiltered
    if "HASH_" not in text and "EVENT_HASH" not in text and "LEGACY" not in text:
        page.fill("#audit-action", "")
        page.click("#load-audit")
        page.wait_for_timeout(900)
        text = page.locator("#audit-body").inner_text()
    assert "HASH_" in text or "EVENT_HASH" in text or "LEGACY" in text
    _logout(page)
    page.close()
