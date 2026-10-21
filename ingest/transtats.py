"""Stdlib-only client for the BTS TranStats download form (ASP.NET POST).

GET the form to read __VIEWSTATE / __EVENTVALIDATION, then POST the wanted
field names set to "on". Unknown field names are dropped silently by the
server, so callers verify the CSV header afterwards.
See docs/research/data-sources.md §1b, §3 and §E.
"""

from __future__ import annotations

import http.cookiejar
import os
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

FORM_URL = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ={vq}&QO_fu146_anzr=Nv4%20Pn44vr45"

# Dataset codes on the TranStats form
T100_SEGMENT_ALL = "FMG"
ONTIME_REPORTING = "FGJ"


def _hidden(page: str, name: str) -> str:
    m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', page) or re.search(rf'id="{name}" value="([^"]*)"', page)
    return m.group(1) if m else ""


def download(vq: str, year: int, period: int | str, fields: list[str], out: Path,
             timeout: int = 900, geography: str = "All") -> Path:
    """Download one period of a TranStats table to ``out`` (a zip). Atomic write."""
    url = FORM_URL.format(vq=vq)
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0 (airport-investment-agent ingest)")]
    page = op.open(url, timeout=120).read().decode("utf-8", "ignore")
    data = {
        "__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
        "__VIEWSTATE": _hidden(page, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _hidden(page, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": _hidden(page, "__EVENTVALIDATION"),
        "txtSearch": "", "cboGeography": geography, "cboYear": str(year),
        "cboPeriod": str(period), "btnDownload": "Download",
    }
    for f in fields:
        data[f] = "on"
    resp = op.open(url, data=urllib.parse.urlencode(data).encode(), timeout=timeout)
    body = resp.read()
    tmp = out.with_suffix(out.suffix + ".part")
    tmp.write_bytes(body)
    if not zipfile.is_zipfile(tmp):
        head = body[:200].decode("utf-8", "ignore")
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"not a zip ({len(body)} bytes): {head!r}")
    os.replace(tmp, out)
    return out


def csv_header(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as f:
            return f.readline().decode("utf-8-sig").strip().split(",")


def months_between(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Inclusive list of (year, month) from start to end."""
    y, m = start
    out = []
    while (y, m) <= end:
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def download_months(vq: str, months: list[tuple[int, int]], fields: list[str], dest: Path,
                    prefix: str, required: list[str], existing: dict[tuple[int, int], Path] | None = None,
                    retries: int = 3) -> None:
    """Download each month to dest/{prefix}_{YYYY}_{MM}.zip, skipping valid existing files."""
    dest.mkdir(parents=True, exist_ok=True)
    existing = existing or {}
    for (y, m) in months:
        out = dest / f"{prefix}_{y}_{m:02d}.zip"
        src = existing.get((y, m))
        if not out.exists() and src is not None and src.exists():
            out.write_bytes(src.read_bytes())
            print(f"[{prefix}] {y}-{m:02d} copied from {src}", flush=True)
        if out.exists() and zipfile.is_zipfile(out) and set(required) <= set(csv_header(out)):
            print(f"[{prefix}] {y}-{m:02d} present, skip", flush=True)
            continue
        for attempt in range(1, retries + 1):
            t0 = time.time()
            try:
                download(vq, y, m, fields, out)
                hdr = csv_header(out)
                missing = set(required) - set(hdr)
                if missing:
                    raise RuntimeError(f"missing columns {sorted(missing)}")
                print(f"[{prefix}] {y}-{m:02d} ok {out.stat().st_size} bytes in {time.time()-t0:.0f}s", flush=True)
                break
            except Exception as e:  # noqa: BLE001 - log and retry
                print(f"[{prefix}] {y}-{m:02d} attempt {attempt} failed after {time.time()-t0:.0f}s: {e}", flush=True)
                if out.exists() and not (zipfile.is_zipfile(out) and set(required) <= set(csv_header(out))):
                    out.unlink()
                time.sleep(10 * attempt)
        else:
            print(f"[{prefix}] {y}-{m:02d} FAILED after {retries} attempts", flush=True)
    print(f"[{prefix}] done", flush=True)
