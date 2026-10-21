"""Build docs/deck.pptx (5 slides) with officecli from the screenshots in docs/deck/.

Run from the repo root:  python3 scripts/build_deck.py
It writes an officecli batch file, creates the deck, applies the batch, then validates it.
Every number on the slides comes from docs/examples.md or a deterministic tool result.
All three images are screenshots of the running app (docker compose up): g3-anchorage-app.png and
g1-new-england-app.png reopen saved G3 and G1 conversations; g1-ranking-pillars.png is the top of the
rank_airports Evidence card from that same G1 page.
"""
import json
import pathlib
import subprocess
import tempfile

GROUND, CARD, INK, MUTED, HAIR = "F7F6F2", "FFFFFF", "1B1A17", "66645E", "E2E0DA"
MOM, PRE, SCA, OK, WARN = "7C69A8", "A96C4C", "5C8A6E", "1D7F53", "93600A"
SERIF, SANS, MONO = "Georgia", "Arial", "Consolas"
W, H, M = 33.867, 19.05, 1.5

ops = [{"command": "set", "path": "/", "props": {"defaultFont": "Arial"}}]
slide_no = 0


def cm(v):
    return f"{v:.3f}cm"


def add(type_, props, parent=None):
    ops.append({"command": "add", "parent": parent or f"/slide[{slide_no}]", "type": type_, "props": props})


def text(name, t, x, y, w, h, *, font=SANS, size=18, color=INK, bold=False, align="left", valign="top",
         spacing=None, line_spacing=None):
    p = {"name": name, "text": t, "x": cm(x), "y": cm(y), "width": cm(w), "height": cm(h), "font": font,
         "size": str(size), "color": color, "bold": str(bold).lower(), "align": align, "valign": valign,
         "margin": "0", "fill": "none", "line": "none", "autoFit": "none"}
    if spacing:
        p["spacing"] = str(spacing)
    if line_spacing:
        p["lineSpacing"] = line_spacing
    add("shape", p)


PCOUNT = {}


def para(shape, t, *, size=18, color=INK, bold=False, space_before=None):
    key = (slide_no, shape)
    PCOUNT[key] = PCOUNT.get(key, 1) + 1
    p = {"text": t, "size": str(size), "color": color, "bold": str(bold).lower()}
    add("paragraph", p, parent=f"/slide[{slide_no}]/shape[@name={shape}]")
    if space_before:
        ops.append({"command": "set", "path": f"/slide[{slide_no}]/shape[@name={shape}]/paragraph[{PCOUNT[key]}]",
                    "props": {"spaceBefore": space_before}})


def box(name, x, y, w, h, *, fill=CARD, line=HAIR, preset="rect", line_width="0.75pt"):
    p = {"name": name, "x": cm(x), "y": cm(y), "width": cm(w), "height": cm(h), "fill": fill,
         "preset": preset}
    if line == "none":
        p["line"] = "none"
    else:
        p["line"] = line
        p["lineWidth"] = line_width
    add("shape", p)


def new_slide(n, label, title, notes):
    global slide_no
    slide_no += 1
    ops.append({"command": "add", "parent": "/", "type": "slide", "props": {"layout": "blank", "background": GROUND}})
    # Eyebrow: slide number and section, mono, muted.
    text("Eyebrow", f"{n:02d} / 05   ·   {label}", M, 1.1, 22, 0.6, font=MONO, size=11, color=MUTED)
    # Motif: the three Pillar colours, top right, on every slide.
    for i, c in enumerate([MOM, PRE, SCA]):
        box(f"Motif{i+1}", W - M - 1.5 + i * 0.55, 1.2, 0.4, 0.4, fill=c, line="none")
    if title:
        text("Title", title, M, 1.9, W - 2 * M, 1.9, font=SERIF, size=36, color=INK)
    text("Footer", "Airport Investment Intelligence Agent  ·  Snapshot built 2026-10-21", M, H - 1.0, 20, 0.5,
         font=MONO, size=10, color=MUTED)
    add("notes", {"text": notes})

new_slide(1, "THE PROBLEM", None,
          "An investor wants to know which US airports are the best candidates for terminal modernisation. "
          "No public dataset measures renovation profitability, so the agent works from an explicit Investment "
          "Thesis. Its three clauses become the three Pillars of the Investment Opportunity Score: Demand Momentum, "
          "Capacity Pressure and Market Scale, with default weights 0.35, 0.40 and 0.25. "
          "The score is a screening signal: it shortlists airports for a closer look and does not prove a "
          "renovation would pay off.")
text("Hero", "Where should the next terminal go?", M, 2.1, W - 2 * M, 2.2, font=SERIF, size=44)
text("Sub", "A chat agent that ranks the 402 US Primary Airports for terminal-modernisation investment. "
            "Deterministic tools compute every score from public FAA, BTS and Census data; the language model "
            "picks tools and explains.", M, 4.6, 29, 2.95, size=20, color=MUTED)
text("ThesisLabel", "INVESTMENT THESIS  ·  A RENOVATION IS MOST PROMISING WHERE…", M, 7.6, 25, 0.6,
     font=MONO, size=11, color=MUTED)
cw = (W - 2 * M - 2 * 0.76) / 3
cards = [
    ("Demand Momentum", MOM, "0.35", "demand is growing", "FAA forecast growth to FY2035 and CY2024→CY2025 enplanement growth"),
    ("Capacity Pressure", PRE, "0.40", "the infrastructure is already strained", "Load Factor, departures delayed ≥ 15 min, average taxi-out"),
    ("Market Scale", SCA, "0.25", "the market can monetise new capacity", "CY2025 enplanements and metro (CBSA) population"),
]
for i, (name, col, wt, clause, metrics) in enumerate(cards):
    x = M + i * (cw + 0.76)
    box(f"Card{i+1}", x, 8.4, cw, 6.5)
    box(f"Band{i+1}", x, 8.4, cw, 0.22, fill=col, line="none")
    text(f"Pillar{i+1}", name, x + 0.6, 9.0, cw - 1.2, 0.9, size=22, bold=True)
    text(f"Weight{i+1}", f"DEFAULT WEIGHT {wt}", x + 0.6, 10.0, cw - 1.2, 0.5, font=MONO, size=11, color=col)
    text(f"Clause{i+1}", f"…{clause}", x + 0.6, 10.75, cw - 1.2, 1.8, font=SERIF, size=20)
    text(f"Metrics{i+1}", metrics, x + 0.6, 12.6, cw - 1.2, 2.1, size=16, color=MUTED)
box("Strap", M, 15.4, W - 2 * M, 1.4, fill=INK, line="none")
text("StrapText", "The score screens candidates. It does not prove that a renovation would be profitable.",
     M + 0.7, 15.4, W - 2 * M - 1.4, 1.4, size=18, color=GROUND, valign="middle")

# ---------------------------------------------------------------- 2. Approach and architecture
new_slide(2, "APPROACH AND ARCHITECTURE", "From public data to an answer you can check",
          "Left to right. Offline scripts build a dated Snapshot of FAA, BTS and Census data as Parquet; Live Signals "
          "are fetched at question time and never change a score. Deterministic tools compute every score, share and "
          "Forecast Gap. The Pydantic AI agent on Claude Sonnet 5.5 only picks tools, states Assumptions and explains. "
          "The chat shows the answer, and the Mission panel shows each tool's data as tables and charts so every "
          "figure can be checked. Every tool returns the same envelope, and a live number-grounding test fails if an "
          "answer quotes a number that is not in that run's tool results.")
gap = 1.1
bw = (W - 2 * M - 3 * gap) / 4
flow = [
    ("PUBLIC DATA", "Snapshot + Live Signals",
     "FAA, BTS and Census data in a dated Parquet Snapshot, plus Live Signals at question time."),
    ("DETERMINISTIC TOOLS", "Every number computed here",
     "rank_airports\nairport_scorecard\ncompare_airports\nroute_mix\nunmet_demand\nquery_snapshot"),
    ("AGENT", "Pydantic AI agent",
     "Claude Sonnet 5.5 picks tools, states Assumptions and explains. It never computes a score."),
    ("CHAT + EVIDENCE", "The answer and its proof",
     "Next.js chat. The Mission panel shows Progress, Evidence tables and charts, and Trace."),
]
for i, (eb, head, body) in enumerate(flow):
    x = M + i * (bw + gap)
    box(f"Step{i+1}", x, 4.4, bw, 7.8, fill=INK if i == 2 else CARD, line="none" if i == 2 else HAIR)
    fg, mu = (GROUND, "CFCBC2") if i == 2 else (INK, MUTED)
    text(f"StepEb{i+1}", eb, x + 0.5, 4.9, bw - 1.0, 0.5, font=MONO, size=11, color=mu)
    text(f"StepHead{i+1}", head, x + 0.5, 5.6, bw - 1.0, 1.8, font=SERIF, size=20, color=fg)
    if i == 1:
        text(f"StepBody{i+1}", body, x + 0.5, 7.6, bw - 1.0, 4.3, font=MONO, size=13, color=fg, line_spacing="1.2x")
    else:
        text(f"StepBody{i+1}", body, x + 0.5, 7.6, bw - 1.0, 4.3, size=16, color=mu)
for i in range(3):
    ops.append({"command": "add", "parent": f"/slide[{slide_no}]", "type": "connector",
                "props": {"x": cm(M + (i + 1) * bw + i * gap), "y": cm(4.4 + 7.8 / 2), "width": cm(gap),
                          "height": "0cm", "shape": "straight", "color": INK, "lineWidth": "1.25pt", "tailEnd": "triangle"}})
text("EnvLabel", "EVERY TOOL RETURNS ONE ENVELOPE", M, 13.0, 20, 0.5, font=MONO, size=11, color=MUTED)
chips = ["data", "sources + As-of Dates", "assumptions", "data_confidence", "coverage", "caveats"]
cx = M
for i, c in enumerate(chips):
    wdt = 0.8 + len(c) * 0.3
    box(f"Chip{i+1}", cx, 13.65, wdt, 0.95, fill=CARD, line=HAIR, preset="roundRect")
    text(f"ChipText{i+1}", c, cx, 13.65, wdt, 0.95, font=MONO, size=13, align="center", valign="middle")
    cx += wdt + 0.35
text("Grounding", "A live number-grounding test runs the exam questions against the real model and fails if any "
                  "number in an answer is missing from that run's tool results.",
     M, 15.3, W - 2 * M, 1.7, size=18, color=INK)

# ---------------------------------------------------------------- 3. Scoring methodology
new_slide(3, "SCORING METHODOLOGY", "Seven percentiles, three Pillars, one score",
          "Each of seven metrics becomes a Percentile Score across the 402 Primary Airports, so a small airport "
          "compares with a large hub and outliers cannot stretch the scale. Pillars are weighted means of their "
          "metric percentiles. The Investment Opportunity Score is a weighted geometric mean of the Pillars, because "
          "the thesis is a conjunction: Martha's Vineyard has Demand Momentum 82.1 but Market Scale 28.4 and scores "
          "54.7. A missing metric is imputed at the median and the score is labelled Provisional with the imputed "
          "metrics named. Data Confidence is computed from Coverage and recency, never judged by the model. "
          "On the right is the rank_airports Evidence card from the running app answering exam question G1 "
          "(New England): BOS has Pillars 50.2, 86.1 and 95.3 and scores 73.1.")
iw = 7.0
ih = iw * 1212 / 718
ix = W - M - iw
lw = ix - 0.9 - M
text("PctLabel", "PERCENTILE SCORES (0–100) ACROSS 402 PRIMARY AIRPORTS  ·  WEIGHTS IN BRACKETS", M, 4.2, lw, 0.5,
     font=MONO, size=11, color=MUTED)
rows = [
    (MOM, "Demand Momentum", "0.35", "FAA TAF enplanement CAGR FY2024→FY2035 (0.60) · enplanement growth CY2024→CY2025 (0.40)"),
    (PRE, "Capacity Pressure", "0.40", "Load Factor, class F (0.40) · departures delayed ≥ 15 min (0.30) · average taxi-out (0.30)"),
    (SCA, "Market Scale", "0.25", "CY2025 enplanements (0.70) · 2025 metro (CBSA) population (0.30)"),
]
for i, (col, name, wt, mets) in enumerate(rows):
    y = 5.0 + i * 2.25
    box(f"RowSw{i+1}", M, y + 0.17, 0.4, 0.4, fill=col, line="none")
    text(f"RowName{i+1}", name, M + 0.8, y, 10, 0.8, size=18, bold=True)
    text(f"RowWt{i+1}", wt, M + lw - 3.2, y, 3.2, 0.8, font=MONO, size=16, color=col, align="right")
    text(f"RowMet{i+1}", mets, M + 0.8, y + 0.82, lw - 0.8, 1.2, size=14, color=MUTED)
box("Formula", M, 11.4, lw, 2.95)
text("FormulaLabel", "INVESTMENT OPPORTUNITY SCORE  ·  WEIGHTED GEOMETRIC MEAN", M + 0.6, 11.7, lw - 1.2, 0.5,
     font=MONO, size=11, color=MUTED)
text("FormulaText", "exp( Σ w × ln( max(Pillar, 1) ) )", M + 0.6, 12.25, lw - 1.2, 0.9, font=MONO, size=18)
text("FormulaNote", "A weak Pillar drags the score down: MVY has Demand Momentum 82.1 but Market Scale 28.4, and scores 54.7.",
     M + 0.6, 13.1, lw - 1.2, 1.15, size=14, color=MUTED)
box("ShotFrame", ix - 0.05, 4.2 - 0.05, iw + 0.1, ih + 0.1, fill=CARD, line=HAIR)
add("picture", {"src": "docs/deck/g1-ranking-pillars.png", "x": cm(ix), "y": cm(4.2),
                "width": cm(iw), "height": cm(ih),
                "alt": "rank_airports Evidence card in the running app for New England: Pillar bars per airport against the median (50), and BOS first with score 73.1 and Pillars 50.2, 86.1, 95.3"})
text("ShotCap", "Running app, G1 Mission panel: BOS Pillars 50.2 / 86.1 / 95.3 give 73.1.",
     ix, 4.2 + ih + 0.2, iw, 1.6, size=12, color=MUTED)
qw3 = (lw - 2 * 0.6) / 3
facts = [
    ("PROVISIONAL SCORE", WARN, "A missing metric is imputed at the median (50) and named; Coverage shows as e.g. 5 of 7."),
    ("DATA CONFIDENCE", OK, "Computed, never judged by the model: High at 7 of 7 Coverage; Medium if provisional, scenario or ad hoc."),
    ("WHAT IT IS NOT", INK, "Screens candidates; does not prove profitability. No project cost, gate utilisation or revenue data."),
]
for i, (lab, col, body) in enumerate(facts):
    x = M + i * (qw3 + 0.6)
    text(f"FactLab{i+1}", lab, x, 14.8, qw3, 0.5, font=MONO, size=11, color=col)
    text(f"FactBody{i+1}", body, x, 15.35, qw3, 2.5, size=13, color=INK)
qw = (W - 2 * M - 2 * 0.76) / 3

# ---------------------------------------------------------------- 4. Demo
new_slide(4, "DEMO  ·  THE RUNNING APP", "Exam questions answered, evidence alongside",
          "Both screenshots are the running app at 1440 by 900 in light theme, reopening saved conversations from "
          "the Recent chats rail. Left, exam question G3: 2.7% of Anchorage's scheduled passenger departures are "
          "Long-haul Flights, with the passenger-weighted 6.2% and cargo-inclusive 29.5% variants and the "
          "3,000-mile definition stated; the Mission panel shows the route_mix call and its donuts and table, "
          "Data Confidence High. Right, exam question G1: New England ranked by Investment Opportunity Score, "
          "BOS 73.1, BGR 72.4 and BTV 71.9 leading 16 ranked airports; the Mission panel shows the rank_airports "
          "call, the Pillar bars and the score table, Data Confidence Medium because HVN and PSM are Provisional.")
gap4 = 0.8
sw = (W - 2 * M - gap4) / 2
sh = sw * 1800 / 2880
shots = [
    ("G3 · ANCHORAGE LONG-HAUL SHARE", "docs/deck/g3-anchorage-app.png",
     "The running app answering 'What is the percentage of long haul flights out of Anchorage airport?': 2.7% of class F departures are Long-haul Flights; the Mission panel shows route_mix donuts at 2.7%, 6.2% and 29.5% and Data Confidence High",
     "2.7% of scheduled passenger departures are Long-haul (6.2% passenger-weighted, 29.5% cargo-inclusive). "
     "Mission panel: route_mix donuts and table, Data Confidence High."),
    ("G1 · NEW ENGLAND RANKING", "docs/deck/g1-new-england-app.png",
     "The running app answering 'Which airports in New England are strong candidates for terminal expansion?': a ranking table led by BOS 73.1, BGR 72.4 and BTV 71.9; the Mission panel shows rank_airports Pillar bars and the score table, Data Confidence Medium",
     "BOS 73.1, BGR 72.4 and BTV 71.9 lead 16 ranked airports. Mission panel: rank_airports Pillar bars "
     "and score table, Data Confidence Medium (HVN and PSM Provisional)."),
]
for i, (lab, src, alt, cap) in enumerate(shots):
    x = M + i * (sw + gap4)
    text(f"ShotLab{i+1}", lab, x, 4.2, sw, 0.5, font=MONO, size=11, color=MUTED)
    box(f"AppFrame{i+1}", x - 0.05, 4.9 - 0.05, sw + 0.1, sh + 0.1, fill=CARD, line=HAIR)
    add("picture", {"src": src, "x": cm(x), "y": cm(4.9), "width": cm(sw), "height": cm(sh), "alt": alt})
    text(f"ShotCap{i+1}", cap, x, 4.9 + sh + 0.35, sw, 2.4, size=14, color=INK)

# ---------------------------------------------------------------- 5. Tradeoffs, limitations, next steps
new_slide(5, "TRADEOFFS AND NEXT STEPS", "Tradeoffs, limits and next steps",
          "Tradeoffs: a dated Snapshot makes every score reproducible and the demo independent of API uptime, at the "
          "cost of staleness; Live Signals add evidence but never change a score. A geometric mean of percentiles "
          "penalises a weak Pillar, and median imputation has a known, disclosed bias. Pydantic AI runs the tool loop "
          "instead of a hand-written agent. Limitations: the score screens and does not prove profitability; "
          "percentiles favour small, fast-growing airports, as when doubling the growth weight lifts BID and WST into "
          "the New England top 10; delay data covers only reporting carriers' domestic flights. Next: backtest the "
          "weights against past terminal projects, add gate utilisation and ASPM data, schedule Snapshot refreshes, "
          "and build the designed voice call.")
cols = [
    ("TRADEOFFS", MUTED, INK, [
        ("Snapshot + Live Signals", "Reproducible scores and a demo that survives API outages; the cost is staleness."),
        ("Geometric mean of percentiles", "A weak Pillar hurts; outliers can't stretch the scale."),
        ("Median imputation, disclosed", "Pulls a Provisional Score toward the middle, always named."),
        ("Proven harness", "Pydantic AI runs the tool loop; no hand-written agent loop."),
    ]),
    ("LIMITATIONS", WARN, WARN, [
        ("Screens, doesn't prove", "Profitability needs project cost, gate utilisation, commercial revenue and feasibility."),
        ("Percentiles favour small, fast growers", "Doubling growth lifts BID and WST into the New England top 10."),
        ("Partial delay data", "On-Time covers reporting carriers' domestic flights only; Load Factor is not spill."),
    ]),
    ("NEXT STEPS", SCA, SCA, [
        ("Backtest the Pillar Weights", "against past terminal projects."),
        ("Add data", "gate utilisation and ASPM."),
        ("Schedule Snapshot refreshes", "so As-of Dates stay current."),
        ("Voice call", "designed over the same agent; not built."),
    ]),
]
for i, (lab, labcol, band, items) in enumerate(cols):
    x = M + i * (qw + 0.76)
    box(f"Col{i+1}", x, 4.2, qw, 13.1)
    box(f"ColBand{i+1}", x, 4.2, qw, 0.22, fill=band, line="none")
    text(f"ColLab{i+1}", lab, x + 0.6, 4.85, qw - 1.2, 0.5, font=MONO, size=11, color=labcol)
    name = f"ColBody{i+1}"
    text(name, items[0][0], x + 0.6, 5.7, qw - 1.2, 11.2, size=16, bold=True)
    para(name, items[0][1], size=16, color=MUTED)
    for head, body in items[1:]:
        para(name, head, size=16, bold=True, space_before="14pt")
        para(name, body, size=16, color=MUTED)

OUT = pathlib.Path("docs/deck.pptx")
subprocess.run(["officecli", "close", str(OUT)], capture_output=True)
OUT.unlink(missing_ok=True)
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(ops, f, ensure_ascii=False)
subprocess.run(["officecli", "create", str(OUT)], check=True, capture_output=True)
res = subprocess.run(["officecli", "batch", str(OUT), "--input", f.name, "--json"], capture_output=True, text=True)
pathlib.Path(f.name).unlink()
if not json.loads(res.stdout).get("success"):
    raise SystemExit(f"officecli batch failed: {res.stdout[:2000]}")
subprocess.run(["officecli", "close", str(OUT)], check=True, capture_output=True)
subprocess.run(["officecli", "validate", str(OUT)], check=True)
subprocess.run(["officecli", "view", str(OUT), "issues"], check=True)
print(f"wrote {OUT} ({len(ops)} officecli operations)")
