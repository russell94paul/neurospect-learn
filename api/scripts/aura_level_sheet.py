#!/usr/bin/env python
"""
Level sheet — compose range + PD arrays + ERL into ONE zone-tagged, readable sheet.

    python api/scripts/aura_level_sheet.py \
        --range api/docs/evidence/s1e/range/ltf/range.json \
        --pd    api/docs/evidence/s1e/pd/pd-arrays.json \
        --erl   api/docs/evidence/s1e/erl/erl.json \
        --out   api/docs/evidence/s1e/levels

⭐ WHY THIS EXISTS
Four detectors now emit objects independently (`aura_range`, `aura_pd_arrays`, `aura_erl`,
`aura_swing_smt`). Paul's acceptance test is LEVEL CORRECTNESS read against a chart
(2026-08-15: *"the main goal is that you get the entry levels correct"*), and that cannot be
checked from four JSON files. This produces one price-ordered sheet a human can compare to
the chart line by line.

WHAT IT ADDS RATHER THAN RESTATES
- **Zone tagging** — every object gets DISCOUNT / EQUILIBRIUM / PREMIUM against the supplied
  range. ⚠ WHICH range matters: rule 30 says discount/premium "of the **LTF** range", and
  the old engine measured against the HTF one. That single choice flipped S1d's entry from
  premium to discount, so the range file used is named in the output.
- **IRL vs ERL** — internal range liquidity (a gap's nested swing, `gaps.md`'s "precise
  target") versus external (previous D/W/M extremes). Paul takes half off at the nearest
  IRL, so the sheet marks which side of the pair each level is.

⛔ NO QUADRANTS (rule 5). ⛔ No entry is selected — that needs bias from the cycle detector
still awaiting validation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def zone_of(price: float, low: float, high: float) -> str:
    if high == low:
        return "EQUILIBRIUM"
    p = (price - low) / (high - low)
    if abs(p - 0.5) < 1e-9:
        return "EQUILIBRIUM"
    if price < low or price > high:
        return "OUTSIDE"
    return "DISCOUNT" if p < 0.5 else "PREMIUM"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", dest="rng", required=True, type=Path)
    ap.add_argument("--pd", required=True, type=Path)
    ap.add_argument("--erl", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--unmitigated-only", action="store_true",
                    help="drop gaps already mitigated — they are no longer draws on price")
    a = ap.parse_args()

    R = json.loads(a.rng.read_text())
    rr = R["range"]
    low, high = rr["low"], rr["top_effective"]
    eq = rr["eq"]

    rows = []

    # ── ERL: external range liquidity ────────────────────────────────────────
    for lv in json.loads(a.erl.read_text())["levels"]:
        if lv["side"] == "eq":
            continue
        rows.append({
            "price": lv["price"], "object": lv["label"], "class": "ERL",
            "detail": f"prev {lv['period']} {lv['side']}, from {lv['source_period']}",
            "state": "BROKEN" if lv["broken_t"] else "resting",
            "zone": zone_of(lv["price"], low, high),
        })

    # ── PD arrays, and the IRL nested inside them ────────────────────────────
    pd = json.loads(a.pd.read_text())
    for g in pd["gaps"]:
        if a.unmitigated_only and g["mitigated_t"]:
            continue
        sub = f" [{g['subtype']}]" if g.get("subtype") else ""
        rows.append({
            "price": g["mid"], "object": f"{g['kind']}{sub}", "class": "PD-ARRAY",
            "detail": (f"{g['direction']} {g['bottom']:,.2f}-{g['top']:,.2f} "
                       f"({g['size_ticks']:.0f}t)"
                       + (f", overlaps {len(g['overlaps'])}" if g["overlaps"] else "")),
            "state": ("mitigated" if g["mitigated_t"] else
                      "inverted" if g["inverted_t"] else "unfilled"),
            "zone": zone_of(g["mid"], low, high),
        })
        if g["internal_liquidity"] is not None:
            rows.append({
                "price": g["internal_liquidity"], "object": "IRL", "class": "IRL",
                "detail": f"inside {g['kind']}, found by {g['liquidity_route']}",
                "state": "target",
                "zone": zone_of(g["internal_liquidity"], low, high),
            })

    # ── the range's own structure ────────────────────────────────────────────
    for price, name in ((high, "RANGE.HIGH"), (eq, "RANGE.EQ"), (low, "RANGE.LOW")):
        rows.append({"price": price, "object": name, "class": "RANGE",
                     "detail": f"{rr['direction']} range, {rr['size']:,.2f} pts",
                     "state": "live" if not rr["invalidated_t"] else "invalidated",
                     "zone": zone_of(price, low, high)})

    rows.sort(key=lambda r: -r["price"])

    counts: dict = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    zones: dict = {}
    for r in rows:
        zones[r["zone"]] = zones.get(r["zone"], 0) + 1

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "level-sheet.json").write_text(json.dumps({
        "range_file": str(a.rng),
        "range": {"low": low, "eq": eq, "high": high,
                  "resolution": R["resolution"], "span": R["span"],
                  "ambiguous_r9": rr["ambiguous"]},
        "zone_reference_note": ("rule 30 specifies discount/premium of the LTF range; the "
                               "old engine used the HTF range and that single choice flipped "
                               "S1d's entry from PREMIUM to DISCOUNT"),
        "quadrants": "NOT EMITTED — rule 5",
        "counts_by_class": counts,
        "counts_by_zone": zones,
        "levels": rows,
    }, indent=1), encoding="utf-8")

    print(f"[sheet] range {low:,.2f} / EQ {eq:,.2f} / {high:,.2f}   "
          f"({R['resolution']}, R9 ambiguous={rr['ambiguous']})")
    print(f"[sheet] objects: {counts}")
    print(f"[sheet] by zone: {zones}")
    print()
    print(f"  {'price':>11}  {'zone':<11} {'class':<9} {'object':<22} {'state':<10} detail")
    print(f"  {'-'*11}  {'-'*11} {'-'*9} {'-'*22} {'-'*10} {'-'*40}")
    for r in rows[:45]:
        print(f"  {r['price']:>11,.2f}  {r['zone']:<11} {r['class']:<9} "
              f"{r['object']:<22} {r['state']:<10} {r['detail'][:44]}")
    if len(rows) > 45:
        print(f"  … {len(rows) - 45} more (full sheet in level-sheet.json)")
    print(f"[sheet] -> {a.out / 'level-sheet.json'}")


if __name__ == "__main__":
    main()
