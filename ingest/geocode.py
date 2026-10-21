"""CBSA (metro/micro area) per airport via the Census Geocoder coordinates endpoint.

Keyless. Results are cached in data/raw/geocoder.json, keyed by FAA LocID, so a
rebuild only calls the API for airports that are new or whose coordinates moved.
An airport outside every CBSA is cached as {"cbsa_code": null}; only network or
HTTP failures are retried on the next run.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
LAYERS = "Metropolitan Statistical Areas,Micropolitan Statistical Areas"


def _query(lat: float, lon: float, retries: int = 3) -> dict:
    params = urllib.parse.urlencode({
        "x": f"{lon:.6f}", "y": f"{lat:.6f}", "benchmark": "Public_AR_Current",
        "vintage": "Current_Current", "layers": LAYERS, "format": "json",
    })
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{GEOCODER_URL}?{params}",
                                         headers={"User-Agent": "airport-investment-agent ingest"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                geos = json.load(resp)["result"]["geographies"]
            for layer, lsad in (("Metropolitan Statistical Areas", "Metropolitan Statistical Area"),
                                ("Micropolitan Statistical Areas", "Micropolitan Statistical Area")):
                if geos.get(layer):
                    g = geos[layer][0]
                    return {"lat": lat, "lon": lon, "cbsa_code": g["GEOID"], "cbsa_name": g["NAME"], "lsad": lsad}
            return {"lat": lat, "lon": lon, "cbsa_code": None, "cbsa_name": None, "lsad": None}
        except Exception as e:  # noqa: BLE001 - retried, then reported by the caller
            last = e
            time.sleep(2 * (attempt + 1))
    return {"lat": lat, "lon": lon, "error": str(last)}


def cbsa_for(points: dict[str, tuple[float, float]], cache_path: Path, workers: int = 8) -> dict[str, dict]:
    """Map FAA LocID -> {cbsa_code, cbsa_name, lsad} (or {"error": ...}) for every point given."""
    cache: dict[str, dict] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = {k: (lat, lon) for k, (lat, lon) in points.items()
            if k not in cache or "error" in cache[k]
            or abs(cache[k]["lat"] - lat) > 1e-4 or abs(cache[k]["lon"] - lon) > 1e-4}
    if todo:
        print(f"  geocoder: querying {len(todo)} airports (cache has {len(cache)})", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for key, res in zip(todo, ex.map(lambda p: _query(*p), todo.values())):
                cache[key] = res
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(dict(sorted(cache.items())), indent=1) + "\n")
    return {k: cache[k] for k in points}
