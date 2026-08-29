"""
aura_figure_pack.py — build the figure pack the Aura walkthrough artifact renders.

WHAT THIS IS
    A build-time generator. It slices REAL exported OHLC (Tradezella session 831607) into a
    compact JSON the artifact embeds and draws as inline SVG. No chart library, no network.

WHAT IT MAY EMIT, AND WHAT IT MAY NOT
    ✅ Real bars, verbatim from the export.
    ✅ Gaps (FVG / iFVG / NWOG / NDOG) — these are DEFINITIONAL arithmetic on OHLC
       (candle 1 high vs candle 3 low), not a detector verdict, so they are reproducible
       by anyone with the same bars.
    ⛔ NOT ranges, NOT SMT, NOT bias, NOT targets, NOT entries. Those come from detectors
       that were found WRONG on 2026-08-15 (two SMT objects conflated; cycles are
       quarterly-theory segments not timeframes; TP was the wrong object) and are still
       gated on Paul's TradingView validation. Anything from that family renders in the
       artifact as a SCHEMATIC of the rule, never as a claim about a specific chart.

    Every emitted figure therefore carries `basis: "MEASURED"` (bars) or
    `basis: "DERIVED"` (gaps, from bars by declared arithmetic). Nothing else ships.
"""
from __future__ import annotations

import argparse
import re
import datetime as dt
import io
import json
from pathlib import Path

EVID = Path(__file__).resolve().parents[1] / "docs" / "evidence"
BARS = EVID / "s1e" / "bars"
ET = dt.timezone(dt.timedelta(hours=-4))  # late-May 2025 is EDT; the export is UTC-4 throughout
TICK = 0.25  # NQ
MIN_GAP_TICKS = 4  # S1c's declared floor — a one-tick gap is not a PD array


def load_bars(symbol: str, res: str) -> tuple[list[tuple], dict]:
    path = BARS / f"tradezella-831607-{symbol}-{res}-span.json"
    doc = json.load(io.open(path, encoding="utf-8"))
    bars = [(r["0"], r["1"], r["2"], r["3"], r["4"]) for r in doc["data"]]
    bars.sort(key=lambda b: b[0])
    meta = {
        "symbol": doc["symbol"],
        "resolution": doc["resolution"],
        "source_file": path.name,
        "session_url": doc["session_url"],
        "exported_at_utc": doc["exported_at_utc"],
        "bar_count_in_file": doc["bar_count"],
    }
    return bars, meta


def et(ts: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts, ET)


def find_gaps(bars: list[tuple], lo_i: int, hi_i: int) -> list[dict]:
    """Definitional 3-candle FVGs. Bullish: bar1.high < bar3.low. Bearish: bar1.low > bar3.high.

    mitigated_at = first later bar that trades back INTO the gap.
    inverted_at  = first later bar that CLOSES through the far side (this is what makes an iFVG).
    """
    out: list[dict] = []
    for i in range(lo_i, min(hi_i, len(bars) - 2)):
        _, _, h1, l1, _ = bars[i]
        _, _, h3, l3, _ = bars[i + 2]
        if h1 < l3:
            kind, lo, hi = "bull", h1, l3
        elif l1 > h3:
            kind, lo, hi = "bear", h3, l1
        else:
            continue
        if (hi - lo) < MIN_GAP_TICKS * TICK:
            continue

        mit = inv = None
        for j in range(i + 3, len(bars)):
            _, _, hj, lj, cj = bars[j]
            if mit is None and lj <= hi and hj >= lo:
                mit = j
            if kind == "bull" and cj < lo:
                inv = j
                break
            if kind == "bear" and cj > hi:
                inv = j
                break
            if mit is not None and j > i + 400:
                break
        out.append(
            {
                "kind": kind,
                "formed_i": i + 2,          # the gap is knowable at the CLOSE of bar 3
                "lo": lo,
                "hi": hi,
                "ticks": round((hi - lo) / TICK),
                "mitigated_i": mit,
                "inverted_i": inv,
            }
        )
    return out


def slice_window(bars, start_et: dt.datetime, end_et: dt.datetime):
    s, e = start_et.timestamp(), end_et.timestamp()
    idx = [i for i, b in enumerate(bars) if s <= b[0] < e]
    return (idx[0], idx[-1] + 1) if idx else (0, 0)


def build(symbol: str, res: str, start: str, end: str, label: str) -> dict:
    bars, meta = load_bars(symbol, res)
    a, b = slice_window(
        bars,
        dt.datetime.fromisoformat(start).replace(tzinfo=ET),
        dt.datetime.fromisoformat(end).replace(tzinfo=ET),
    )
    if a == b:
        raise SystemExit(f"no bars in window {start}..{end} for {symbol} {res}")
    win = bars[a:b]
    gaps = [g for g in find_gaps(bars, a, b) if a <= g["formed_i"] < b]
    n = len(win)
    for g in gaps:  # re-base onto the window; anything past its right edge is STILL LIVE here
        g["formed_i"] -= a
        for k in ("mitigated_i", "inverted_i"):
            v = g[k]
            if v is None:
                g[k], g[k + "_beyond"] = None, False
            elif v - a >= n:
                g[k], g[k + "_beyond"] = None, True
            else:
                g[k], g[k + "_beyond"] = v - a, False
    return {
        "label": label,
        "basis": "MEASURED",
        "meta": meta | {"window_start_et": start, "window_end_et": end, "bars_in_window": len(win)},
        "bars": [[t, o, h, l, c] for (t, o, h, l, c) in win],
        "gaps": {"basis": "DERIVED", "method": "3-candle definitional; >=4 ticks", "items": gaps},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EVID / "s1b" / "figure-pack.json"))
    ap.add_argument("--list-gaps", action="store_true", help="print candidates and exit")
    args = ap.parse_args()

    if args.list_gaps:
        bars, _ = load_bars("NQ", "5m")
        a, b = slice_window(
            bars, dt.datetime(2025, 5, 26, tzinfo=ET), dt.datetime(2025, 5, 31, tzinfo=ET)
        )
        for g in find_gaps(bars, a, b):
            if g["mitigated_i"] is None:
                continue
            live = g["mitigated_i"] - g["formed_i"]
            print(
                f'{et(bars[g["formed_i"]][0]):%a %m-%d %H:%M} {g["kind"]:4s} '
                f'{g["lo"]:9.2f}-{g["hi"]:9.2f} {g["ticks"]:3d}t  live {live:3d} bars  '
                f'inverted={"y" if g["inverted_i"] else "n"}'
            )
        return

    pack = {
        "generator": "aura_figure_pack.py",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "declaration": (
            "Bars are MEASURED (verbatim export). Gaps are DERIVED by declared arithmetic. "
            "No range, SMT, bias, target or entry is emitted — those detectors are under repair "
            "and gated on TradingView validation (2026-08-15)."
        ),
        "figures": {
            "ltf_5m": build("NQ", "5m", "2025-05-27T08:00", "2025-05-27T16:00", "NQ 5m — Tue 27 May 2025, NY session"),
            "htf_60m": build("NQ", "60", "2025-05-19T00:00", "2025-05-31T00:00", "NQ 60m — two weeks to 30 May 2025"),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, separators=(",", ":")), encoding="utf-8")
    for k, f in pack["figures"].items():
        print(f'{k}: {f["meta"]["bars_in_window"]} bars, {len(f["gaps"]["items"])} gaps')
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────────────────────────────────────
# SVG rendering — done HERE, at build time, so the artifact's figures exist
# before any script runs. Coordinates are computed from the bars; nothing is
# eyeballed. See artifact-motion: "every coordinate that represents a quantity
# is computed from the number printed in the page".
# ─────────────────────────────────────────────────────────────────────────────

W, H, PADL, PADR, PADT, PADB = 1000, 380, 8, 56, 14, 26


def _scales(bars):
    lo = min(b[3] for b in bars)
    hi = max(b[2] for b in bars)
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    n = len(bars)
    xw = (W - PADL - PADR) / n
    def x(i): return PADL + i * xw + xw / 2
    def y(p): return PADT + (hi - p) / (hi - lo) * (H - PADT - PADB)
    return x, y, xw, lo, hi


def _candles(bars, x, y, xw):
    out = []
    bw = max(1.6, xw * 0.62)
    for i, (_, o, h, l, c) in enumerate(bars):
        cx = x(i)
        up = c >= o
        cls = "up" if up else "dn"
        yo, yc = y(o), y(c)
        top, bot = min(yo, yc), max(yo, yc)
        out.append(f'<line class="wk {cls}" x1="{cx:.1f}" y1="{y(h):.1f}" x2="{cx:.1f}" y2="{y(l):.1f}"/>')
        out.append(
            f'<rect class="bd {cls}" x="{cx-bw/2:.1f}" y="{top:.1f}" '
            f'width="{bw:.1f}" height="{max(0.9, bot-top):.1f}"/>'
        )
    return out


def _axis(y, lo, hi):
    out, step = [], 25.0
    while (hi - lo) / step > 8:
        step *= 2
    p = (int(lo / step) + 1) * step
    while p < hi:
        yy = y(p)
        out.append(f'<line class="grid" x1="{PADL}" y1="{yy:.1f}" x2="{W-PADR}" y2="{yy:.1f}"/>')
        out.append(f'<text class="ax" x="{W-PADR+6}" y="{yy+3.4:.1f}">{p:,.0f}</text>')
        p += step
    return out


def _clock(bars, x):
    out = []
    for i, b in enumerate(bars):
        t = et(b[0])
        if t.minute == 0 and t.hour % 2 == 0:
            out.append(f'<line class="grid v" x1="{x(i):.1f}" y1="{PADT}" x2="{x(i):.1f}" y2="{H-PADB}"/>')
            out.append(f'<text class="ax mid" x="{x(i):.1f}" y="{H-PADB+15}">{t:%H:%M}</text>')
    return out


def svg_gaps(fig, mode: str) -> str:
    """mode='lines'   → every gap as an INFINITE horizontal line (what Paul rejected)
       mode='bounded' → every gap as a rectangle formation → mitigation (chart-markup §0b)"""
    bars = fig["bars"]
    x, y, xw, lo, hi = _scales(bars)
    p = _axis(y, lo, hi) + _clock(bars, x)
    for g in fig["gaps"]["items"]:
        cls = "bull" if g["kind"] == "bull" else "bear"
        if mode == "lines":
            for price in (g["lo"], g["hi"]):
                p.append(f'<line class="gapline {cls}" x1="{PADL}" y1="{y(price):.1f}" x2="{W-PADR}" y2="{y(price):.1f}"/>')
        else:
            x0 = x(g["formed_i"]) - xw / 2
            end = g["mitigated_i"]
            x1 = (W - PADR) if end is None else x(end) + xw / 2
            live = end is None
            p.append(
                f'<rect class="gapbox {cls}{" live" if live else ""}" x="{x0:.1f}" y="{y(g["hi"]):.1f}" '
                f'width="{max(2.0, x1-x0):.1f}" height="{max(1.5, y(g["lo"])-y(g["hi"])):.1f}"/>'
            )
    p += _candles(bars, x, y, xw)
    return "\n".join(p)


def svg_ifvg(fig, gap_index: int) -> str:
    """One gap's life: formed → mitigated → CLOSED THROUGH (it is now an iFVG)."""
    g = fig["gaps"]["items"][gap_index]
    a = max(0, g["formed_i"] - 6)
    b = min(len(fig["bars"]), (g["inverted_i"] or g["formed_i"]) + 12)
    bars = fig["bars"][a:b]
    x, y, xw, lo, hi = _scales(bars)
    p = _axis(y, lo, hi)
    cls = "bull" if g["kind"] == "bull" else "bear"
    fi, mi, ii = g["formed_i"] - a, (g["mitigated_i"] or 0) - a, (g["inverted_i"] or 0) - a
    p.append(
        f'<rect class="gapbox {cls}" x="{x(fi)-xw/2:.1f}" y="{y(g["hi"]):.1f}" '
        f'width="{x(mi)+xw/2-(x(fi)-xw/2):.1f}" height="{max(1.5,y(g["lo"])-y(g["hi"])):.1f}"/>'
    )
    p.append(
        f'<rect class="gapbox inv" x="{x(mi)-xw/2:.1f}" y="{y(g["hi"]):.1f}" '
        f'width="{x(len(bars)-1)+xw/2-(x(mi)-xw/2):.1f}" height="{max(1.5,y(g["lo"])-y(g["hi"])):.1f}"/>'
    )
    p += _candles(bars, x, y, xw)
    marks = [(fi, "formed"), (mi, "mitigated"), (ii, "closed through → iFVG")]
    for row, (i, lab) in enumerate(marks):
        p.append(f'<line class="mark" x1="{x(i):.1f}" y1="{PADT}" x2="{x(i):.1f}" y2="{H-PADB}"/>')
        ly = PADT + 12 + row * 15          # one label per row, so they cannot collide
        anch = "end" if i > len(bars) * 0.62 else "start"
        dx = -6 if anch == "end" else 6
        p.append(f'<text class="lab" text-anchor="{anch}" x="{x(i)+dx:.1f}" y="{ly}">{lab}</text>')
    return "\n".join(p)


# ─────────────────────────────────────────────────────────────────────────────
# Marked-up worked examples.
#
# Draws REAL bars plus the shape geometry the S1d engine actually emitted
# (`s1d/chart-shapes-spec.json`) — same coordinates, same primitives, same rule
# attribution. Nothing here is re-derived; if a level is wrong on the chart it is
# wrong in the record too, which is the point of putting it in front of Paul.
#
# ⚠️ A shape whose span leaves the window is drawn to the edge AND reported, never
# silently clamped — that clamp is the exact S1d defect (13 of 33 shapes wrong
# while every success signal passed).
# ─────────────────────────────────────────────────────────────────────────────

RULE_STYLE = {           # follows chart-markup.md §0 colour convention
    "R3":  ("qual", "solid"),    "R4":  ("ink",  "solid"),
    "R5":  ("muted", "dash"),    "R6":  ("stop", "solid"),
    "R11": ("gap",  "box"),      "R12": ("gap",  "dot"),
    "R29": ("stop", "dash"),     "R30": ("targ", "solid"),
    "R33": ("stop", "solid"),    "R35": ("targ", "dash"),
}


def svg_markup(fig, shapes, *, label_rules=None, height=430, gutter=150,
               tag_steps=False):
    """fig: a figure dict from the pack. shapes: entries from chart-shapes-spec.json."""
    bars = fig["bars"]
    t0, t1 = bars[0][0], bars[-1][0]
    step = (bars[1][0] - bars[0][0]) if len(bars) > 1 else 300

    global W, H, PADR
    W_, H_, PADR_ = W, H, PADR
    W, H, PADR = 1000, height, gutter
    try:
        lo = min(b[3] for b in bars); hi = max(b[2] for b in bars)
        for s in shapes:                      # levels must fit, or the figure lies
            for p in s["points"]:
                lo, hi = min(lo, p["price"]), max(hi, p["price"])
        pad = (hi - lo) * 0.05
        lo, hi = lo - pad, hi + pad
        n = len(bars)
        xw = (W - PADL - PADR) / n
        def X(ts):
            i = (ts - t0) / step
            return PADL + max(-0.5, min(n + 0.5, i)) * xw + xw / 2
        def Y(p): return PADT + (hi - p) / (hi - lo) * (H - PADT - PADB)

        out, escaped = [], []
        # price grid
        stepp = 25.0
        while (hi - lo) / stepp > 9: stepp *= 2
        p = (int(lo / stepp) + 1) * stepp
        while p < hi:
            out.append(f'<line class="grid" x1="{PADL}" y1="{Y(p):.1f}" x2="{W-PADR}" y2="{Y(p):.1f}"/>')
            p += stepp

        # candles first, markup over them
        bw = max(1.4, xw * 0.6)
        for i, (_, o, h, l, c) in enumerate(bars):
            cx = PADL + i * xw + xw / 2
            cls = "up" if c >= o else "dn"
            yo, yc = Y(o), Y(c)
            out.append(f'<line class="wk {cls}" x1="{cx:.1f}" y1="{Y(h):.1f}" x2="{cx:.1f}" y2="{Y(l):.1f}"/>')
            out.append(f'<rect class="bd {cls}" x="{cx-bw/2:.1f}" y="{min(yo,yc):.1f}" '
                       f'width="{bw:.1f}" height="{max(0.9, abs(yc-yo)):.1f}"/>')

        labels = []
        buckets = {}          # step -> [element, ...]; None when not tagging
        def emit(el, mi):
            (buckets.setdefault(mi, []) if tag_steps else out).append(el)
        for s in shapes:
            rule = s["rule"]; tone, kind = RULE_STYLE.get(rule, ("muted", "solid"))
            a, b = s["points"][0], s["points"][-1]
            # A ray is SUPPOSED to run to the right edge, so that is not an escape.
            # What matters is an anchor the reader cannot see, or a bounded segment
            # whose end is off-window — then the drawing asserts more than it shows.
            if a["time"] < t0:
                escaped.append(f'{rule}: anchor at {et(a["time"]):%d %b %H:%M} is before this window')
            elif s["tool"] != "ray" and b["time"] > t1 + step:
                escaped.append(f'{rule}: ends {et(b["time"]):%d %b %H:%M}, after this window')
            xa, xb = X(a["time"]), X(b["time"])
            traded = bool(s.get("traded"))
            if s["tool"] == "rectangle":
                ya, yb = Y(a["price"]), Y(b["price"])
                emit(
                    f'<rect class="mk mk-{tone} mk-{kind}{" mk-traded" if traded else ""}" '
                    f'x="{min(xa,xb):.1f}" y="{min(ya,yb):.1f}" '
                    f'width="{max(2.0, abs(xb-xa)):.1f}" height="{max(1.4, abs(yb-ya)):.1f}"/>', s.get("_mi"))
            else:
                ray = s["tool"] == "ray"
                xe = (W - PADR) if ray else xb
                y = Y(a["price"])
                emit(
                    f'<line class="mk mk-{tone} mk-{kind}{" mk-ray" if ray else ""}" '
                    f'x1="{xa:.1f}" y1="{y:.1f}" x2="{xe:.1f}" y2="{y:.1f}"/>', s.get("_mi"))
                if not ray:   # a bounded segment ends where the level ended — show the stop
                    emit(f'<line class="mk-cap mk-{tone}" x1="{xe:.1f}" y1="{y-4:.1f}" '
                               f'x2="{xe:.1f}" y2="{y+4:.1f}"/>', s.get("_mi"))
            if label_rules is None or rule in label_rules or traded:
                txt = s["label"].split("] ")[-1].replace("**", "").strip()
                # the zone suffix is redundant here and overflows the gutter
                txt = re.sub(r"\s*\[(PREMIUM|DISCOUNT)\]\s*$", "", txt)
                labels.append((Y(a["price"]) if s["tool"] != "rectangle"
                               else (Y(a["price"]) + Y(b["price"])) / 2, rule, txt, tone, traded,
                               s.get("_mi")))

        # right gutter: one label per level, de-collided by nudging down the column
        labels.sort(key=lambda t: t[0])
        last = -99
        for y, rule, txt, tone, traded, mi in labels:
            y = max(y, last + 12.5); last = y      # de-collide across ALL steps at once
            emit(f'<line class="mk-lead mk-{tone}" x1="{W-PADR-4}" y1="{y:.1f}" '
                 f'x2="{W-PADR+4}" y2="{y:.1f}"/>', mi)
            emit(f'<text class="lv lv-{tone}{" lv-traded" if traded else ""}" '
                 f'x="{W-PADR+8}" y="{y+3.4:.1f}">{txt}</text>', mi)

        # time axis
        for i, b in enumerate(bars):
            t = et(b[0])
            if step >= 86400:     tick = t.weekday() == 0            # weekly marks on daily bars
            elif step >= 3600:    tick = t.hour == 9                 # one per session on hourly
            else:                 tick = t.minute == 0 and t.hour % 2 == 0
            if tick:
                x = PADL + i * xw + xw / 2
                out.append(f'<line class="grid v" x1="{x:.1f}" y1="{PADT}" x2="{x:.1f}" y2="{H-PADB}"/>')
                fmt = "%d %b" if step >= 3600 else "%H:%M"
                if step < 3600 and t.hour == 0: fmt = "%d %b"
                out.append(f'<text class="ax mid" x="{x:.1f}" y="{H-PADB+15}">{t:{fmt}}</text>')
        seen, uniq = set(), []
        for e in escaped:                 # same note three times is noise, not rigour
            if e not in seen:
                seen.add(e); uniq.append(e)
        if tag_steps:
            layers = "".join(
                f'<g class="mstep" data-mi="{mi}">' + "\n".join(els) + "</g>"
                for mi, els in sorted(buckets.items(), key=lambda kv: (kv[0] is None, kv[0]))
            )
            return "\n".join(out) + "\n" + layers, uniq
        return "\n".join(out), uniq
    finally:
        W, H, PADR = W_, H_, PADR_
