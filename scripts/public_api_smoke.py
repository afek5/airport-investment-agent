"""One real, keyless call per query_public_api dataset through the live client (free, no LLM).

Run: uv run --project backend python scripts/public_api_smoke.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import live  # noqa: E402

CALLS = [
    ("bts_airport_month", dict(select="reporting_month,total_passengers,total_load_factor",
                               where="origin_airport_code='BOS'", order="reporting_month DESC", limit=3)),
    ("dot_airfare_pairs", dict(select="year,quarter,avg(fare) AS avg_fare,sum(passengers) AS pax_per_day",
                               where="(airport_1='BOS' AND airport_2='LAX') OR (airport_1='LAX' AND airport_2='BOS')",
                               group="year,quarter", order="year DESC,quarter DESC", limit=4)),
    ("dot_airfare_city_pairs", dict(where="city1 like 'Boston%' AND city2 like 'Los Angeles%'",
                                    order="year DESC,quarter DESC", limit=2)),
]


async def main() -> int:
    failed = 0
    for ds, kw in CALLS:
        r = await live.query_public_api(ds, **kw)
        ok = r.ad_hoc and r.data.row_count > 0 and r.data_confidence.level == "Medium"
        failed += not ok
        src = r.sources[0]
        print(f"{'OK ' if ok else 'BAD'} {ds}: {r.data.row_count} rows, truncated={r.data.truncated}, "
              f"confidence={r.data_confidence.level}, as_of={src.as_of}, window={src.window}")
        print("    " + r.data.sql.replace("\n", " | "))
        print("    columns:", r.data.columns)
        for row in r.data.rows[:4]:
            print("     ", row)
    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
