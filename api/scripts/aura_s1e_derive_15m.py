#!/usr/bin/env python
"""
Derive the missing NQ 15m history by aggregating NQ 5m — and PROVE the derivation.

    python api/scripts/aura_s1e_derive_15m.py --packed api/docs/evidence/s1e/bars/packed

Why this exists
---------------
Measured 2026-08-14: NQ's 15m series is capped at **4,492 bars from 2025-03-23**, while
NQ 5m reaches 2023-01-02 and ES/YM/CHFUSD all give ~57,000 15m bars back to 2023. The cap
is real, not lazy loading — it reproduces after repeated `setVisibleRange` nudges AND when
a window lying entirely in 2023 is requested directly. Two independent routes, same answer.

Three 5m bars tile one 15m bar exactly, so the missing history is recoverable by
aggregation. But an aggregation that is merely plausible is worth nothing here, so:

⭐ THE POSITIVE CONTROL: over the window where native 15m bars DO exist, the derived bars
are compared to them field by field. If the derivation is sound it must reproduce the
native series exactly. A mismatch fails the run rather than being averaged away.

Anything written by this script is marked `DERIVED`, never `MEASURED`.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

STEP = 900  # 15 minutes


def aggregate(rows: list[list]) -> dict[int, list]:
    """5m rows -> {bucket_start: [t, o, h, l, c]}, bucket = floor(t / 900) * 900."""
    buckets: dict[int, list[list]] = defaultdict(list)
    for r in rows:
        buckets[(int(r[0]) // STEP) * STEP].append(r)
    out: dict[int, list] = {}
    for b, rs in buckets.items():
        rs.sort(key=lambda r: r[0])
        out[b] = [b, rs[0][1], max(x[2] for x in rs), min(x[3] for x in rs), rs[-1][4]]
    return out, {b: len(rs) for b, rs in buckets.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packed", required=True, type=Path)
    ap.add_argument("--symbol", default="NQ")
    a = ap.parse_args()

    five = json.loads((a.packed / "s1e-bars-5.json").read_text())["resolutions"]["5"]
    p15 = a.packed / "s1e-bars-15.json"
    fifteen = json.loads(p15.read_text())
    native = fifteen["resolutions"]["15"][a.symbol]["rows"]

    derived, counts = aggregate(five[a.symbol]["rows"])
    native_by_t = {int(r[0]): r for r in native}

    # ── THE POSITIVE CONTROL ────────────────────────────────────────────────
    overlap = sorted(set(derived) & set(native_by_t))
    mismatches = []
    for t in overlap:
        d, n = derived[t], native_by_t[t]
        # compare o/h/l/c; only compare buckets the 5m series fully tiles
        if counts[t] != 3:
            continue
        if [round(x, 6) for x in d[1:5]] != [round(float(x), 6) for x in n[1:5]]:
            mismatches.append({"t": t, "derived": d[1:5], "native": [float(x) for x in n[1:5]]})

    full = [t for t in overlap if counts[t] == 3]
    print(f"[derive] {a.symbol}: native 15m bars      = {len(native):,}")
    print(f"[derive] {a.symbol}: derived 15m bars     = {len(derived):,}")
    print(f"[derive] {a.symbol}: overlapping buckets  = {len(overlap):,} "
          f"({len(full):,} fully tiled by three 5m bars)")
    print(f"[derive] {a.symbol}: MISMATCHES           = {len(mismatches)}")
    if mismatches:
        for m in mismatches[:5]:
            print("   ", m)
        raise SystemExit(
            f"REFUSING TO WRITE: {len(mismatches)} derived bars disagree with native bars. "
            "The aggregation is not sound and must not be used.")
    if not full:
        raise SystemExit("REFUSING TO WRITE: no fully-tiled overlapping bucket, so the "
                         "derivation was never actually tested.")

    # Native wins wherever it exists; derived fills only what is missing.
    merged = dict(derived)
    merged.update(native_by_t)
    rows = [merged[t] for t in sorted(merged)]

    fifteen["resolutions"]["15"][a.symbol] = {"res": "15", "rows": rows}
    prov = fifteen.setdefault("provenance", {})
    prov[f"{a.symbol}/15"] = {
        "basis": "DERIVED (aggregated from the MEASURED 5m series) + MEASURED where native exists",
        "reason": "NQ 15m is capped at 4,492 bars from 2025-03-23 at source; reproduced by two "
                  "independent probes (repeat nudges, and a window requested wholly in 2023).",
        "native_bars": len(native),
        "derived_bars_added": len(rows) - len(native),
        "positive_control": f"{len(full)} fully-tiled overlapping buckets compared field by "
                            f"field against native 15m bars: 0 mismatches",
    }
    p15.write_text(json.dumps(fifteen), encoding="utf-8")
    print(f"[derive] wrote {p15.name}: {a.symbol} 15m now {len(rows):,} bars "
          f"({len(rows) - len(native):,} derived, {len(native):,} native)")
    print(f"[derive] first -> last: {min(merged)} -> {max(merged)}")


if __name__ == "__main__":
    main()
