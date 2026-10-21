"""Screenshot the Evidence charts in the real static export, with /api mocked from the test fixtures (no spend).

Usage (after `npm run build` in frontend/):
  uv run --project backend python scripts/evidence_screenshots.py frontend/out frontend/tests/fixtures docs/screenshots/p4-charts
"""

import functools
import http.server
import json
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

out_dir, fix_dir, shots = (pathlib.Path(p) for p in sys.argv[1:4])
shots.mkdir(parents=True, exist_ok=True)
fx = {n: json.loads((fix_dir / f"{n}.json").read_text()) for n in ["rank_airports", "airport_scorecard", "route_mix"]}

messages = [
    {"id": "u1", "role": "user", "parts": [{"type": "text", "text": "Rank New England airports, open the BOS scorecard and show the ANC long-haul share."}]},
    {
        "id": "a1",
        "role": "assistant",
        "parts": [
            {"type": "tool-rank_airports", "toolCallId": "t1", "state": "output-available", "input": {"states": ["CT", "MA", "ME", "NH", "RI", "VT"]}, "output": fx["rank_airports"]},
            {"type": "tool-airport_scorecard", "toolCallId": "t2", "state": "output-available", "input": {"iata": "BOS"}, "output": fx["airport_scorecard"]},
            {"type": "tool-route_mix", "toolCallId": "t3", "state": "output-available", "input": {"iata": "ANC"}, "output": fx["route_mix"]},
            {"type": "text", "text": "BOS ranks first in New England (Investment Opportunity Score 73.1). At ANC, 2.7% of passenger departures are Long-haul Flights (≥ 3,000 mi); cargo-inclusive it is 29.5%."},
        ],
    },
]
conv = {"id": "demo", "title": "Charts demo", "messages": messages}


def handle(route):
    url = route.request.url
    path = url.split("/api/", 1)[1].split("?")[0]
    if path == "session":
        body = {"authenticated": True}
    elif path == "conversations":
        body = [{"id": "demo", "title": "Charts demo"}]
    elif path.startswith("conversations/"):
        body = conv
    else:
        body = {}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
handler.log_message = lambda *a, **k: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for width, label in [(1440, "1440"), (390, "390")]:
        for theme in ["dark", "light"]:
            ctx = b.new_context(viewport={"width": width, "height": 900}, device_scale_factor=2 if width == 390 else 1)
            if theme == "light":
                ctx.add_init_script("try{localStorage.setItem('aiia-theme','light')}catch(e){}")
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))
            page.route("**/api/**", handle)
            page.goto(f"{base}/?c=demo")
            if width < 768:
                page.get_by_role("button", name="Mission").click()
            panel = page.get_by_test_id("mission-panel")
            panel.wait_for()
            page.get_by_test_id("ranking-pillar-chart").wait_for()
            page.wait_for_timeout(600)
            page.screenshot(path=str(shots / f"panel-{label}-{theme}.png"))
            for tool, chart in [("rank_airports", "ranking-pillar-chart"), ("airport_scorecard", "scorecard-pillar-chart"), ("route_mix", "route-mix-donuts")]:
                card = page.get_by_test_id(f"evidence-{tool}")
                card.scroll_into_view_if_needed()
                # Grow the viewport so the whole card fits, then capture it.
                h = card.bounding_box()["height"]
                page.set_viewport_size({"width": width, "height": max(900, int(h) + 200)})
                card.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                card.screenshot(path=str(shots / f"{tool}-{label}-{theme}.png"))
                assert page.get_by_test_id(chart).locator("svg").count() > 0, f"{chart} drew no svg at {label} {theme}"
                assert card.get_by_role("table").count() > 0
                page.set_viewport_size({"width": width, "height": 900})
            # Horizontal overflow check at this width.
            ow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert ow <= 0, f"horizontal overflow {ow}px at {label} {theme}"
            ctx.close()
    b.close()
srv.shutdown()
print("errors:", errors)
print("ok", sorted(x.name for x in shots.iterdir()))
