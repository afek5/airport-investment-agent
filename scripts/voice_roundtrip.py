"""One real voice round trip (SPEC §10), driven headless: a spoken G3 WAV → Call → gpt-live-1 → delegation →
/api/voice/analyst (Claude + route_mix) → session.commentary.append → spoken answer → session.close.

Spends one gpt-live-1 call (under 90 s, always closed with session.close) and one Claude answer.

    say -o q.wav --data-format=LEI16@48000 "[[slnc 5000]] What is the percentage of long haul flights out of \
Anchorage airport? [[slnc 60000]]"
    set -a && . ./.env && set +a && uv run --project backend python scripts/voice_roundtrip.py q.wav OUT_DIR

The app must be running (docker compose up --build, or make dev) at E2E_BASE_URL (default http://localhost:8000).
Writes OUT_DIR/events.json (every data-channel event in and out, the SDP bodies and secrets left out) and
screenshots. Prints a summary; the exit status is 0 only when every step of the round trip was seen.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
MAX_CALL_S = 85  # the step's budget: every real call stays under 90 s

# Records every "oai-events" message in both directions, before the app's own handlers run.
HOOK = """
(() => {
  window.__voiceLog = [];
  const t0 = performance.now();
  const rec = (dir, raw) => {
    let ev; try { ev = JSON.parse(raw); } catch { ev = { raw: String(raw).slice(0, 200) }; }
    window.__voiceLog.push({ t_ms: Math.round(performance.now() - t0), dir, ev });
  };
  const orig = RTCPeerConnection.prototype.createDataChannel;
  RTCPeerConnection.prototype.createDataChannel = function (label, opts) {
    const ch = orig.call(this, label, opts);
    window.__voiceChannel = ch;
    const send = ch.send.bind(ch);
    ch.send = (data) => { rec("out", data); return send(data); };
    ch.addEventListener("message", (e) => rec("in", e.data));
    return ch;
  };
})();
"""


def close_for_sure(page) -> None:
    """Whatever happened above, the call ends with session.close (and we wait for session.closed)."""
    page.evaluate("""async () => {
      const ch = window.__voiceChannel;
      const closed = () => (window.__voiceLog || []).some((e) => e.ev && e.ev.type === "session.closed");
      if (!ch || closed()) return;
      if (ch.readyState === "open" && !(window.__voiceLog || []).some((e) => e.ev && e.ev.type === "session.close")) {
        ch.send(JSON.stringify({ type: "session.close" }));
      }
      for (let i = 0; i < 150 && !closed() && ch.readyState === "open"; i++) await new Promise((r) => setTimeout(r, 100));
    }""")


def redact(obj, secrets: list[str]):
    s = json.dumps(obj)
    for secret in secrets:
        if secret:
            s = s.replace(secret, "[REDACTED]")
    s = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-[REDACTED]", s)
    return json.loads(s)


def main(wav: str, out: str) -> int:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    code = os.environ["ACCESS_CODE"]
    secrets = [code, os.environ.get("OPENAI_API_KEY", ""), os.environ.get("ANTHROPIC_API_KEY", "")]
    analyst: dict = {}
    session_http: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-audio-capture={Path(wav).resolve()}", "--autoplay-policy=no-user-gesture-required",
        ])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, permissions=["microphone"])
        ctx.add_init_script(HOOK)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def on_response(r):
            if r.url.endswith("/api/voice/analyst"):
                try:
                    analyst.update(status=r.status, body=r.json())
                except Exception as e:  # noqa: BLE001
                    analyst.update(status=r.status, error=str(e))
            elif r.url.endswith("/api/voice/session"):
                try:
                    j = r.json()
                    session_http.update(status=r.status, session_id=j.get("session_id"),
                                        answer_sdp_bytes=len(j.get("sdp", "")), max_call_s=j.get("max_call_s"),
                                        error=j.get("error"), message=j.get("message"))
                except Exception as e:  # noqa: BLE001
                    session_http.update(status=r.status, error=str(e))
        page.on("response", on_response)

        page.goto(BASE_URL)
        page.locator("#access-code").fill(code)
        page.get_by_role("button", name="Continue").click()
        expect(page.get_by_test_id("welcome")).to_be_visible()
        call_button = page.get_by_role("button", name="Start a voice call")
        expect(call_button).to_be_visible(timeout=10_000)
        page.screenshot(path=out_dir / "01-call-button.png")

        started = time.monotonic()
        call_button.click()
        try:
            log = lambda: page.evaluate("window.__voiceLog")
            shot_thinking = False
            spoke_answer_at = None
            while time.monotonic() - started < MAX_CALL_S:
                page.wait_for_timeout(500)
                events = log()
                types = [e["ev"].get("type") for e in events]
                if "session.delegation.created" in types and not shot_thinking:
                    page.wait_for_timeout(1500)
                    page.screenshot(path=out_dir / "02-pulling-the-numbers.png")
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.wait_for_timeout(300)
                    page.screenshot(path=out_dir / "02b-in-call-390.png")
                    page.set_viewport_size({"width": 1440, "height": 900})
                    shot_thinking = True
                if "session.commentary.append" in types:
                    i = types.index("session.commentary.append")
                    after = "".join(e["ev"].get("delta", "") for e in events[i:]
                                    if e["ev"].get("type") == "session.output_transcript.delta")
                    if "%" in after or "percent" in after.lower():
                        last_delta = max(e["t_ms"] for e in events if e["ev"].get("type") == "session.output_transcript.delta")
                        now_ms = page.evaluate("Math.round(performance.now())")
                        spoke_answer_at = spoke_answer_at or time.monotonic()
                        if now_ms - last_delta > 3000 or time.monotonic() - spoke_answer_at > 25:
                            break
                if "session.closed" in types:
                    break
            page.screenshot(path=out_dir / "03-answer-spoken.png")
            end = page.get_by_test_id("call-bar").get_by_role("button", name="End", exact=True)
            try:
                if end.count() and end.is_enabled():
                    end.click()  # the app sends session.close and waits for session.closed
                expect(page.get_by_test_id("call-bar")).to_have_count(0, timeout=20_000)
            finally:
                close_for_sure(page)
            duration_s = round(time.monotonic() - started, 1)
            page.wait_for_timeout(500)
            events = log()
        except BaseException:
            close_for_sure(page)  # never leave a live call open
            raise

        evidence = page.get_by_test_id("evidence-route_mix")
        evidence_visible = evidence.count() > 0 and evidence.first.is_visible()
        if evidence_visible:
            evidence.first.scroll_into_view_if_needed()
        page.screenshot(path=out_dir / "04-evidence-route-mix.png")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(400)
        page.screenshot(path=out_dir / "05-phone-390.png")
        browser.close()

    # Keep the SDPs out of the log; they are long and identify the network path.
    record = {"base_url": BASE_URL, "duration_s": duration_s, "page_errors": errors,
              "voice_session_http": session_http,
              "analyst_http": {"status": analyst.get("status"),
                               "tools": (analyst.get("body") or {}).get("tools"),
                               "text": (analyst.get("body") or {}).get("text"),
                               "elapsed_ms": (analyst.get("body") or {}).get("elapsed_ms"),
                               "route_mix_shares": _shares(analyst.get("body") or {})},
              "evidence_route_mix_visible": evidence_visible,
              "events": events}
    record = redact(record, secrets)
    (out_dir / "events.json").write_text(json.dumps(record, indent=2))

    types = [e["ev"].get("type") for e in events]
    deleg = next((e["ev"] for e in events if e["ev"].get("type") == "session.delegation.created"), {})
    comm = next((e["ev"] for e in events if e["ev"].get("type") == "session.commentary.append"), {})
    acked = any(e["ev"].get("type") == "session.commentary.appended"
                and e["ev"].get("client_event_id") == comm.get("event_id") for e in events)
    said = "".join(e["ev"].get("delta", "") for e in events if e["ev"].get("type") == "session.output_transcript.delta")
    heard = "".join(e["ev"].get("delta", "") for e in events if e["ev"].get("type") == "session.input_transcript.delta")
    checks = {
        "session.started": "session.started" in types,
        "input transcript": bool(heard.strip()),
        "session.delegation.created": bool(deleg),
        "analyst called route_mix": "route_mix" in (record["analyst_http"]["tools"] or []),
        "commentary.append delegation_id matches": bool(comm) and comm.get("delegation_id") == (deleg.get("delegation") or {}).get("id"),
        "session.commentary.appended (acked)": acked,
        "output transcript contains 2.7%": "2.7%" in said or "2.7 percent" in said.lower(),
        "Evidence route_mix visible": evidence_visible,
        "session.close sent": "session.close" in types,
        "session.closed received": "session.closed" in types,
        "under 90 s": duration_s < 90,
    }
    print(json.dumps({"heard": heard, "said": said, "duration_s": duration_s, "checks": checks}, indent=2))
    return 0 if all(checks.values()) else 1


def _shares(body: dict) -> dict | None:
    for p in body.get("parts") or []:
        if p.get("type") == "tool-route_mix":
            d = (p.get("output") or {}).get("data") or {}
            return {k: (d.get(k) or {}).get("share_pct") for k in ("passenger_departures", "passenger_weighted", "cargo_inclusive_departures")}
    return None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
