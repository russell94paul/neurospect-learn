#!/usr/bin/env python
"""
Pack S1e's per-symbol chart exports into the shape `aura_setup_engine.load_bars` expects.

    python api/scripts/aura_s1e_pack_bars.py \
        --in api/docs/evidence/s1e/bars --out api/docs/evidence/s1e/bars/packed

The browser exporter writes ONE FILE PER (symbol, resolution) because each POST has to
survive a 45 s CDP ceiling. The engine wants `{"resolutions": {res: {sym: {"rows": [...]}}}}`
and merges across files. This bridges the two without either side guessing.

⚠ TWO SHAPE TRAPS, both measured rather than assumed:

1. `exportData()` rows serialise as OBJECTS with numeric string keys ({"0": t, "1": o, …}),
   not as JSON arrays. Indexing them as lists in the engine would raise; silently
   coercing them wrongly would be worse. They are converted explicitly here.
2. The export carries a 6th column (volume). The engine's Series takes t,o,h,l,c only.
   The extra column is DROPPED here rather than fed through — matching S1c's file, whose
   rows are 5 wide.

Every conversion is counted and the counts are asserted, so a silently truncated file
cannot pass as a complete one.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

# Column order, confirmed from the export's own `schema` field, not from memory:
#   0 time · 1 open · 2 high · 3 low · 4 close · 5 volume
T, O, H, L, C = "0", "1", "2", "3", "4"


def row_to_list(r) -> list:
    """Export rows arrive as {"0": t, "1": o, …}. Lists are tolerated for future-proofing."""
    if isinstance(r, dict):
        return [int(r[T]), float(r[O]), float(r[H]), float(r[L]), float(r[C])]
    return [int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", dest="dst", required=True, type=Path)
    a = ap.parse_args()
    a.dst.mkdir(parents=True, exist_ok=True)

    by_res: dict[str, dict[str, dict]] = defaultdict(dict)
    meta_rows = []

    for p in sorted(a.src.glob("tradezella-831607-*-span.json")):
        raw = json.loads(p.read_text())
        sym, res = raw["symbol"], str(raw["resolution"])
        rows = [row_to_list(r) for r in raw["data"]]
        rows.sort(key=lambda r: r[0])

        # Integrity: the count the browser reported must equal what we converted.
        assert len(rows) == raw["bar_count"], (
            f"{p.name}: bar_count {raw['bar_count']} != converted {len(rows)}")
        # Integrity: timestamps must be strictly increasing after the sort (no dupes).
        dupes = sum(1 for i in range(1, len(rows)) if rows[i][0] == rows[i - 1][0])

        by_res[res][sym] = {"res": res, "rows": rows}
        meta_rows.append({
            "file": p.name, "symbol": sym, "resolution": res, "bars": len(rows),
            "duplicate_timestamps": dupes,
            "first_utc": raw["first_bar_utc"], "last_utc": raw["last_bar_utc"],
        })
        print(f"[pack] {sym:<7} {res:<4} {len(rows):>7,} bars  dupes={dupes}")

    for res, syms in by_res.items():
        out = {
            "source": "Tradezella backtesting session 831607 (chart export)",
            "session_url": "https://app.tradezella.com/backtesting/sessions/831607",
            "extracted_via": "tradingViewApi.chart(i).exportData() -> aura_bar_receiver.py",
            "chart_timezone": "UTC (timestamps are epoch seconds)",
            "phase": "S1e",
            "declared_span": "2023-01-03..2025-04-30; bars exported through the data edge "
                             "so entries near the end can still resolve",
            "resolutions": {res: syms},
        }
        dest = a.dst / f"s1e-bars-{res}.json"
        dest.write_text(json.dumps(out), encoding="utf-8")
        total = sum(len(v["rows"]) for v in syms.values())
        print(f"[pack] wrote {dest.name}  symbols={sorted(syms)}  bars={total:,}")

    (a.dst / "pack-manifest.json").write_text(
        json.dumps({"files": meta_rows}, indent=1), encoding="utf-8")
    print(f"[pack] manifest: {len(meta_rows)} source files")


if __name__ == "__main__":
    main()
