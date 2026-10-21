"""Number-grounding check (SPEC §11 layer 3).

Every percentage or number with ≥ 3 significant digits in the answer must
appear (within rounding) in some tool result of that run.
"""

from __future__ import annotations

import json
import re
from typing import Any

NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(\s*%)?(?:\s*(billion|million|bn|B|M|k|thousand)\b)?")
# A digit run broken by commas in the wrong places ("30,516426", "1,0005") is a mis-copied figure.
MALFORMED = re.compile(r"(?<![\w.,])\d+(?:,\d+)+(?![\d,])")
WELL_GROUPED = re.compile(r"\d{1,3}(?:,\d{3})+")
SCALE = {"billion": 1e9, "bn": 1e9, "B": 1e9, "million": 1e6, "M": 1e6, "k": 1e3, "thousand": 1e3}


def sig_digits(intpart: str, frac: str | None) -> int:
    digits = (intpart.replace(",", "") + (frac or "")).lstrip("0")
    if not frac:
        digits = digits.rstrip("0") or digits
    return len(digits)


def answer_numbers(text: str) -> list[tuple[str, float, int, float]]:
    """(token, value, decimals, scale) for each number in the answer that needs grounding."""
    out = []
    for m in NUM.finditer(text):
        intpart, frac, pct, scale_word = m.group(1), m.group(2), m.group(3), m.group(4)
        if not pct and sig_digits(intpart, frac) < 3:
            continue
        value = float(intpart.replace(",", "") + ("." + frac if frac else ""))
        out.append((m.group(0).strip(), value, len(frac or ""), SCALE.get(scale_word or "", 1.0)))
    return out


def tool_numbers(results: list[Any]) -> list[float]:
    nums: list[float] = []

    def walk(x: Any) -> None:
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            nums.append(float(x))
        elif isinstance(x, str):
            nums.extend(float(t.replace(",", "")) for t in re.findall(r"\d[\d,]*\.?\d*", x) if t.replace(",", "").replace(".", "").isdigit())
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    for r in results:
        walk(json.loads(r) if isinstance(r, str) and r[:1] in "{[" else r)
    return nums


def grounded(value: float, decimals: int, scale: float, pool: list[float]) -> bool:
    for v in pool:
        if scale != 1.0:
            if round(v / scale, decimals) == value:
                return True
        elif round(v, decimals) == value or abs(v - value) < 1e-9:
            return True
    return False


def malformed_numbers(text: str) -> list[str]:
    """Comma-grouped numbers whose grouping is wrong; they can never count as grounded."""
    return [m.group(0) for m in MALFORMED.finditer(text)
            if not WELL_GROUPED.fullmatch(m.group(0)) and len(m.group(0).replace(",", "")) >= 4]


def ungrounded_numbers(answer: str, tool_results: list[Any]) -> list[str]:
    pool = tool_numbers(tool_results)
    bad = malformed_numbers(answer)
    return bad + [tok for tok, v, d, s in answer_numbers(answer)
                  if not grounded(v, d, s, pool) and not any(tok in b for b in bad)]


# A bare run of 4+ digits that is not part of a grouped number, a decimal tail or a label like FY2030.
BARE = re.compile(r"(?<![\w.])(?<!\d,)\d{4,}(?:\.\d+)?(?!\d|,\d)")


def ungrouped_counts(text: str) -> list[str]:
    """Counts or amounts of 1,000 or more written without thousands separators ("1005"). Years 1900–2099
    and labels glued to letters (FY2030, Q1) are not counts. Tool results arrive grouped (app.agent.display),
    so a bare one means the model reformatted a figure."""
    return [m.group(0) for m in BARE.finditer(text)
            if not ("." not in m.group(0) and 1900 <= int(m.group(0)) <= 2099)]


# "N rows", "N quarters", "N distinct months", "N years": a whole count (grouped or not) right before its unit.
COUNT_PHRASE = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)\s+(?:distinct\s+)?(row|quarter|month|year)s?\b",
                          re.IGNORECASE)
# The tool's own words about its counts: the assumptions, `periods` ("100 quarters, 2001 Q2–2026 Q1") and each
# source's window ("12 months, Aug 2025–Jul 2026").
COUNT_TEXT_KEYS = {"assumptions", "periods", "window"}
TABLE_SEPARATOR = re.compile(r"\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?")


def _count(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", v):  # app.agent.display groups 1,000+
        return int(v.replace(",", ""))
    return None


def stated_counts(text: str) -> list[tuple[int, str, str]]:
    """(N, unit, phrase) for every "N rows/quarters/months/years" in the text; unit is singular, lower case."""
    return [(int(m.group(1).replace(",", "")), m.group(2).lower(), m.group(0)) for m in COUNT_PHRASE.finditer(text)]


def table_row_counts(text: str) -> set[int]:
    """Data rows of each markdown table in the text (header and separator lines not counted)."""
    counts: set[int] = set()
    rows: int | None = None  # None until a table's separator line is seen
    for line in [*text.splitlines(), ""]:
        s = line.strip()
        if s.startswith("|") and rows is None and TABLE_SEPARATOR.fullmatch(s) and "-" in s:
            rows = 0
        elif s.startswith("|") and rows is not None:
            rows += 1
        elif not s.startswith("|"):
            if rows is not None:
                counts.add(rows)
            rows = None
    return counts


def tool_counts(results: list[Any]) -> tuple[set[int], set[int], dict[str, set[int]]]:
    """What the tools say about counts: every row_count, the period_counts whose unit is unknown, and per
    unit the period_counts of that unit plus the N of each "N <unit>s" in assumptions, periods and windows."""
    rows: set[int] = set()
    periods: set[int] = set()
    said: dict[str, set[int]] = {}

    def walk(x: Any, text: bool = False) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                n = _count(v)
                if k == "row_count" and n is not None:
                    rows.add(n)
                elif k == "period_count" and n is not None:
                    # The count's unit is the one `periods` names ("100 quarters, …"), so it backs only that unit.
                    named = stated_counts(x["periods"]) if isinstance(x.get("periods"), str) else []
                    if named:
                        said.setdefault(named[0][1], set()).add(n)
                    else:
                        periods.add(n)
                walk(v, text or k in COUNT_TEXT_KEYS)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v, text)
        elif isinstance(x, str) and text:
            for n, unit, _ in stated_counts(x):
                said.setdefault(unit, set()).add(n)

    for r in results:
        walk(json.loads(r) if isinstance(r, str) and r[:1] in "{[" else r)
    return rows, periods, said


def misstated_counts(answer: str, tool_results: list[Any]) -> list[str]:
    """Row and period counts in the answer that nothing in the run backs.

    Each "N rows" / "N quarters" / "N months" / "N years" in the answer must equal one of:
    - the tool's row_count (for rows) or period_count (for quarters, months or years: the unit its `periods`
      names);
    - the number of data rows in a markdown table the answer itself shows ("the latest 12 quarters" above a
      12-row table);
    - an N the tool states with the same unit in its assumptions, `periods` or source window ("12 months,
      Aug 2025–Jul 2026" backs "12 months").
    The unit has to match: 100 rows over 25 quarters called "100 quarters" fails, although the tool says
    "100 rows" in its assumptions."""
    rows, periods, said = tool_counts(tool_results)
    tables = table_row_counts(answer)
    bad = []
    for n, unit, phrase in stated_counts(answer):
        allowed = (rows if unit == "row" else periods) | tables | said.get(unit, set())
        if n not in allowed:
            bad.append(phrase)
    return bad
