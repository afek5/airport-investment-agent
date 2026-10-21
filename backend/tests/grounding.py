"""Number-grounding check (SPEC §11 layer 3).

Every percentage or number with ≥ 3 significant digits in the answer must
appear (within rounding) in some tool result of that run.
"""

from __future__ import annotations

import json
import re
from typing import Any

NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(\s*%)?(?:\s*(million|M|k|thousand)\b)?")
SCALE = {"million": 1e6, "M": 1e6, "k": 1e3, "thousand": 1e3}


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


def ungrounded_numbers(answer: str, tool_results: list[Any]) -> list[str]:
    pool = tool_numbers(tool_results)
    return [tok for tok, v, d, s in answer_numbers(answer) if not grounded(v, d, s, pool)]
