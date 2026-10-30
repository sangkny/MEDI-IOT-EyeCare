"""Playwright Chromium E2E for Clinical Operations UI.

Requires:
  EYECARE_OPS_E2E_BASE (e.g. http://127.0.0.1:8000)
  playwright + chromium installed
Synthetic credentials only (doctor/doc123).
"""
from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

BASE = os.environ.get("EYECARE_OPS_E2E_BASE", "").rstrip("/")
CREDS_OK = ("doctor", "doc123")
CREDS_BAD = ("doctor", "wrong-password")


def _skip_if_unconfigured() -> None:
    if not BASE:
        pytest.skip("EYECARE_OPS_E2E_BASE 미설정")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright 미설치")


@pytest.fixture(scope="module")
def browser_page():
    _skip_if_unconfigured()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


def test_e2e_01_invalid_login(browser_page) -> None:
    page = browser_page
    page.goto(f"{BASE}/clinical-ops")
    page.fill("#username", CREDS_BAD[0])
    page.fill("#password", CREDS_BAD[1])
    page.click("#login-btn")
    page.wait_for_timeout(500)
    assert "실패" in (page.locator("#login-msg").inner_text() or "")
    assert page.locator("#login-view").is_visible()


def test_e2e_02_valid_login_and_logout(browser_page) -> None:
    page = browser_page
    page.goto(f"{BASE}/clinical-ops")
    page.fill("#username", CREDS_OK[0])
    page.fill("#password", CREDS_OK[1])
    page.click("#login-btn")
    page.wait_for_selector("#app-view:not(.hidden)", timeout=10000)
    assert page.locator("#who").inner_text()
    page.click("#logout-btn")
    page.wait_for_selector("#login-view:not(.hidden)")
    assert "로그아웃" in page.locator("#login-msg").inner_text()


def test_e2e_03_memory_token_not_in_storage(browser_page) -> None:
    page = browser_page
    page.goto(f"{BASE}/clinical-ops")
    page.fill("#username", CREDS_OK[0])
    page.fill("#password", CREDS_OK[1])
    page.click("#login-btn")
    page.wait_for_selector("#app-view:not(.hidden)", timeout=10000)
    local = page.evaluate("() => JSON.stringify(localStorage)")
    session = page.evaluate("() => JSON.stringify(sessionStorage)")
    assert "eyJ" not in local
    assert "eyJ" not in session
    page.click("#logout-btn")


def test_e2e_04_nav_shell_present(browser_page) -> None:
    page = browser_page
    page.goto(f"{BASE}/clinical-ops")
    page.fill("#username", CREDS_OK[0])
    page.fill("#password", CREDS_OK[1])
    page.click("#login-btn")
    page.wait_for_selector("#app-view:not(.hidden)", timeout=10000)
    for label in ("Dashboard", "Subjects", "eCRF", "Questionnaires", "Clinical Queries", "Data Locks", "Audit Trail", "Protocol Information"):
        assert page.get_by_role("link", name=label).count() >= 1
    page.click("#logout-btn")
