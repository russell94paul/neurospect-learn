#!/usr/bin/env python
"""
S1e configuration sweep — 48 engine runs × 8 post-hoc enforcement filters = 384 cells.

    python api/scripts/aura_s1e_sweep.py --bars api/docs/evidence/s1e/bars/packed \
        --out api/docs/evidence/s1e/sweep

The grid, the metrics and the reporting rule are PRE-REGISTERED in
`api/docs/evidence/s1e/sweep-preregistration.md`. Read that first — it is the thing
that stops this from being a search for a flattering number.

⛔ THIS IS A SENSITIVITY INSTRUMENT, NOT A SELECTION PROCEDURE.
384 cells against ~32 independent episodes will produce a best cell by chance. Every
cell is written out; none is adopted on expectancy alone; cells under 20 entries are
marked UNDERPOWERED and excluded from expectancy comparisons.

`total_r_ex_best` is recorded for every cell because the baseline was +4.84R total and
−7.57R without its single best trade. A cell that rests on one trade must show it.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

ENGINE = Path("api/scripts/aura_setup_engine.py")
SPAN = ("2023-01-03", "2025-04-30")

# ── The pre-registered grid ──────────────────────────────────────────────────
# AMENDMENT 1 (2026-08-15): (admitted_at_all_cycles, join_mode). Run 1's axis was
# INERT — admitting the leg changed no trade, because CHFUSD shares 0 of NQ's 3,794
# daily timestamps and the exact join can never match. `off x session_date` is
# skipped: with the leg unadmitted at D/W the join is a no-op.
AXIS_AURA_ASSET = [(False, "timestamp"), (True, "timestamp"), (True, "session_date")]
AXIS_WEEKLY_LOOKBACK = [12, 16, 20, 26]
AXIS_RETEST = ["report", "require_first", "session_first"]
AXIS_ZONE_REF = ["htf", "ltf"]

# ── The post-hoc enforcement layer ───────────────────────────────────────────
ENF_ZONE = [False, True]
ENF_MIN_RR = [0.0, 1.0]
ENF_WEEKLY = [False, True]

UNDERPOWERED_BELOW = 20


def planned_rr(rec) -> float | None:
    for ln in rec["lines"]:
        if ln["rule"] == "R35":
            m = re.search(r"([\d.]+)R PLANNED", ln["text"])
            if m:
                return float(m.group(1))
    return None


def has_branch(rec, prefix: str) -> bool:
    return any(b.startswith(prefix) for b in rec.get("branches", []))


def episode_key(rec):
    smt = rng = None
    for ln in rec["lines"]:
        if ln["rule"] == "R3" and smt is None:
            m = re.search(r"@ (\d{4}-\d{2}-\d{2})", ln["text"])
            smt = m.group(1) if m else ln["text"][:40]
        if ln["rule"] == "R4" and rng is None:
            m = re.search(r"range ([\d,\.]+-[\d,\.]+)", ln["text"])
            rng = m.group(1) if m else ln["text"][:40]
    return (rec.get("bias"), smt, rng)


def metrics(setups: list) -> dict:
    n = len(setups)
    if n == 0:
        return {"entries": 0, "episodes": 0, "underpowered": True}
    R = [s["outcome"]["realised_r"] for s in setups]
    wins = [r for r in R if r > 0]
    losses = [r for r in R if r <= 0]
    eps = {}
    for s in setups:
        eps.setdefault(episode_key(s), []).append(s["outcome"]["realised_r"])
    ep_tot = [sum(v) for v in eps.values()]
    return {
        "entries": n,
        "episodes": len(eps),
        "win_pct": round(100 * len(wins) / n, 1),
        "avg_win_r": round(st.mean(wins), 3) if wins else None,
        "avg_loss_r": round(st.mean(losses), 3) if losses else None,
        "expectancy_r": round(sum(R) / n, 4),
        "total_r": round(sum(R), 2),
        "median_r": round(st.median(R), 3),
        # the one-trade dependency check, recorded for EVERY cell
        "total_r_ex_best": round(sum(sorted(R)[:-1]), 2) if n > 1 else None,
        "episode_win_pct": round(100 * sum(1 for e in ep_tot if e > 0) / len(ep_tot), 1),
        "episode_mean_r": round(st.mean(ep_tot), 3),
        "underpowered": n < UNDERPOWERED_BELOW,
        "pct_violating_zone": round(100 * sum(1 for s in setups if has_branch(s, "R5/R32")) / n, 1),
        "pct_violating_retest": round(100 * sum(1 for s in setups if has_branch(s, "R30 -")) / n, 1),
        "pct_no_weekly": round(100 * sum(1 for s in setups if has_branch(s, "R18 -")) / n, 1),
        "pct_aura_asset_refused": round(
            100 * sum(1 for s in setups if has_branch(s, "R17  ")) / n, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    bar_args = []
    for res in ["W", "D", "240", "60", "15", "5"]:
        bar_args += ["--bars", str(a.bars / f"s1e-bars-{res}.json")]

    grid = list(itertools.product(AXIS_AURA_ASSET, AXIS_WEEKLY_LOOKBACK,
                                  AXIS_RETEST, AXIS_ZONE_REF))
    print(f"[sweep] {len(grid)} engine runs x "
          f"{len(ENF_ZONE)*len(ENF_MIN_RR)*len(ENF_WEEKLY)} enforcement filters "
          f"= {len(grid)*8} cells", flush=True)

    cells = []
    for i, ((aa, aaj), wk, rt, zr) in enumerate(grid, 1):
        label = (f"aa={'all' if aa else 'ltf'}/{aaj}·wk={wk}·rt={rt}·zone={zr}")
        with tempfile.TemporaryDirectory() as td:
            cmd = [sys.executable, str(ENGINE), *bar_args,
                   "--from", SPAN[0], "--to", SPAN[1], "--out", td,
                   "--weekly-lookback-weeks", str(wk),
                   "--retest-mode", rt, "--zone-ref", zr,
                   "--aura-asset-join", aaj,
                   "--selection-basis", "S1e pre-registered sweep; span fixed in advance"]
            if aa:
                cmd.append("--aura-asset-all-cycles")
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[sweep] {i:>2}/{len(grid)} FAILED {label}\n{r.stderr[-800:]}", flush=True)
                cells.append({"config": label, "error": r.stderr[-400:]})
                continue
            data = json.loads((Path(td) / "computed-setups.json").read_text())

        recs = data["records"]
        setups = [x for x in recs if x["kind"] == "SETUP"]
        rejects = {}
        for x in recs:
            if x["kind"] == "REJECTION":
                rejects[x.get("failing_rule")] = rejects.get(x.get("failing_rule"), 0) + 1

        base = metrics(setups)
        print(f"[sweep] {i:>2}/{len(grid)}  {label:<44} "
              f"n={base['entries']:>4} eps={base['episodes']:>3} "
              f"exp={base.get('expectancy_r', 0):+.3f}R tot={base.get('total_r', 0):+.2f}R",
              flush=True)

        for ez, rr, ew in itertools.product(ENF_ZONE, ENF_MIN_RR, ENF_WEEKLY):
            sel = setups
            if ez:
                sel = [s for s in sel if not has_branch(s, "R5/R32")]
            if rr > 0:
                sel = [s for s in sel if (planned_rr(s) or 0) >= rr]
            if ew:
                sel = [s for s in sel if not has_branch(s, "R18 -")]
            cells.append({
                "aura_asset_all_cycles": aa, "aura_asset_join": aaj,
                "weekly_lookback_weeks": wk,
                "retest_mode": rt, "zone_ref": zr,
                "enforce_zone": ez, "min_planned_rr": rr, "weekly_gate": ew,
                "config": label,
                "enforcement": f"gz={int(ez)}·rr={rr:g}·wg={int(ew)}",
                "rejections": rejects if not (ez or rr or ew) else None,
                **metrics(sel),
            })

    (a.out / "sweep-results.json").write_text(json.dumps({
        "preregistration": "api/docs/evidence/s1e/sweep-preregistration.md",
        "span": {"from": SPAN[0], "to": SPAN[1]},
        "underpowered_below": UNDERPOWERED_BELOW,
        "reporting_rule": "Every cell published. No cell adopted on expectancy alone. "
                          "384 cells against ~32 independent episodes WILL produce a "
                          "flattering winner by chance.",
        "cells": cells,
    }, indent=1), encoding="utf-8")
    print(f"[sweep] wrote {a.out / 'sweep-results.json'} — {len(cells)} cells", flush=True)


if __name__ == "__main__":
    main()
