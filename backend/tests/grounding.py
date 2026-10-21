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


COUNT_PHRASE = re.compile(r"\b(\d[\d,]*)\s+(?:distinct\s+)?(rows?|quarters?|months?)\b", re.IGNORECASE)


def misstated_counts(text: str, row_counts: set[int], period_counts: set[int]) -> list[str]:
    """Row and period counts the answer states differently from the tool (query_public_api).

    "N rows" must be a row_count the tool returned. "N quarters/months" must be a period_count, or a
    subset of the periods returned (e.g. "the latest 12 quarters" of 100), and never a row_count that
    differs from every period_count (100 rows over 37 quarters called "100 quarters")."""
    bad = []
    for m in COUNT_PHRASE.finditer(text):
        n, unit = int(m.group(1).replace(",", "")), m.group(2).lower()
        if unit.startswith("row"):
            ok = n in row_counts
        else:
            ok = n in period_counts or (bool(period_counts) and n < max(period_counts) and n not in row_counts)
        if not ok:
            bad.append(m.group(0))
    return bad
