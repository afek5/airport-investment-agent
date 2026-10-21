"""Playwright smoke (SPEC §11 layer 4): access code → ask G3 → a streamed answer + an Evidence card
render → reload → the conversation persists. Needs the app running (make e2e starts docker compose)
and spends one real G3 answer. Run: make e2e.
"""

from __future__ import annotations

import os
import re
import time
import urllib.request

import pytest

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
G3 = "What is the percentage of long haul flights out of Anchorage airport?"
ANSWER_TIMEOUT_MS = 120_000


def wait_healthy(timeout_s: float = 90) -> None:
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=5) as r:
                if r.status == 200:
                    return
        except OSError as e:  # connection refused while the container starts
            last = e
        time.sleep(1)
    pytest.fail(f"{BASE_URL}/api/health not ready after {timeout_s:.0f}s: {last}")


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    if not os.environ.get("ACCESS_CODE"):
        pytest.skip("ACCESS_CODE not set (make e2e loads .env)")
    wait_healthy()
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_access_ask_g3_evidence_and_reload_persists(browser):
    from playwright.sync_api import expect

    ctx = browser.new_context(viewport={"width": 1440, "height": 900})  # fresh cookies: no session yet
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # 1. Access screen → wrong code is refused → right code unlocks the welcome state.
    page.goto(BASE_URL)
    expect(page.get_by_test_id("access-screen")).to_be_visible()
    page.locator("#access-code").fill("not-the-code")
    page.get_by_role("button", name="Continue").click()
    expect(page.locator("#access-error")).to_contain_text("isn't right")
    page.locator("#access-code").fill(os.environ["ACCESS_CODE"])
    page.get_by_role("button", name="Continue").click()
    expect(page.get_by_test_id("welcome")).to_be_visible()

    # 2. Ask G3 from its starter chip; the reply is a streamed Vercel AI UI-message stream.
    with page.expect_response(lambda r: r.url.endswith("/api/chat") and r.request.method == "POST") as chat:
        page.get_by_role("button", name=G3).click()
    resp = chat.value
    assert resp.status == 200
    assert resp.headers.get("content-type", "").startswith("text/event-stream")
    assert resp.headers.get("x-vercel-ai-ui-message-stream") == "v1"

    answer = page.get_by_test_id("assistant-message").last
    expect(answer).to_contain_text(re.compile(r"\d+(\.\d+)?%"), timeout=ANSWER_TIMEOUT_MS)
    expect(page.get_by_test_id("followups")).to_be_visible(timeout=ANSWER_TIMEOUT_MS)  # answer finished
    text = answer.inner_text()
    assert "3,000" in text or "3000" in text, "the Long-haul definition is not in the answer"
    assert "cargo" in text.lower()
    assert text.lower().count("assumptions & scope") <= 1, "the answer is shown twice"

    # 3. The Mission panel opened by itself on desktop and renders the route_mix Evidence card.
    panel = page.get_by_test_id("mission-panel")
    expect(panel).to_be_visible()
    expect(panel.get_by_test_id("evidence-route_mix")).to_be_visible()
    expect(panel.get_by_test_id("route-mix")).to_contain_text("%")

    # 4. The finished chat is saved (?c=<id>) and comes back after a reload.
    page.wait_for_url(re.compile(r"[?&]c="), timeout=15_000)
    conversation_url = page.url
    page.reload()
    expect(page.get_by_test_id("access-screen")).to_have_count(0)
    expect(page.locator("[data-role=user]").first).to_contain_text(G3, timeout=15_000)
    restored = page.get_by_test_id("assistant-message").last
    expect(restored).to_contain_text(re.compile(r"\d+(\.\d+)?%"))
    assert page.url == conversation_url
    expect(page.get_by_role("complementary", name="Recent chats")).to_contain_text("Anchorage")

    assert not errors, f"page errors: {errors}"
    ctx.close()
