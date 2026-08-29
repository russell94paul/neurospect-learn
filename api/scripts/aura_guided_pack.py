"""
aura_guided_pack.py — the guided-run figure pack.

Renders the two views a session is worked on (HTF 60m and LTF 5m) with EVERY
recorded S1d shape present in the DOM from the start, each tagged with the markup
step (M1-M12) that draws it. The page then reveals them step by step; nothing is
generated at runtime, so what the reader sees is always the recorded geometry.

⛔ Grammar rule (living-systems-ui #2): a step that produced no artifact must not
look like a step that produced one. Steps carry an artifact state —

    DRAWN         the engine emitted shapes; they appear on the chart
    NOT-RECORDED  a real step of the protocol the engine emitted nothing for
                  (it records the SMT-QUALIFIED swing, never the raw candidates)
    UNRESOLVED    the rulebook contradicts itself and the engine refused to pick

— and the page legends all three. A blank chart at a NOT-RECORDED step is a
measurement gap, not an empty instruction.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aura_figure_pack as A  # noqa: E402

EVID = Path(__file__).resolve().parents[1] / "docs" / "evidence"
SPEC = json.load(io.open(EVID / "s1d" / "chart-shapes-spec.json", encoding="utf-8"))
DRAW = SPEC["draw"]

# Which markup step draws which recorded shape. Indices are into SPEC["draw"];
# the mapping follows chart-markup.md §1 M1-M12, not our convenience.
STEP_OF_SHAPE = {
    12: 2,                                   # M2  the SMT-qualified swing high
    7: 3, 8: 3,                              # M3  range high / low
    9: 5, 10: 5, 11: 5,                      # M5  premium / discount / equilibrium
    **{i: 6 for i in range(13, 28)},         # M6  NDOG + every qualifying iFVG
    28: 7,                                   # M7  liquidity nested inside the gap
    31: 8,                                   # M8  the draw on liquidity (the target)
    29: 11, 30: 11,                          # M11 entry and stop
    32: 12,                                  # M12 invalidation, written on the chart
}

HTF_STEPS = {2, 3, 5, 8}          # levels that live on the 60-minute frame
LTF_STEPS = {6, 7, 11, 12}        # levels that live on the 5-minute frame


def build_view(name, symbol, res, start, end, idx_list, label, **kw):
    """One render. Each shape carries the step that draws it, so the gutter can
    de-collide every label against every other label — across steps, not within."""
    fig = A.build(symbol, res, start, end, label)
    shapes = []
    for i in idx_list:
        sh = dict(DRAW[i])
        sh["_mi"] = STEP_OF_SHAPE[i]
        shapes.append(sh)
    svg, escaped = A.svg_markup(fig, shapes, tag_steps=True, **kw)
    return {
        "svg": svg,
        "label": label,
        "bars": len(fig["bars"]),
        "steps": sorted({s["_mi"] for s in shapes}),
        "escaped": escaped,
    }


def main() -> None:
    out = {
        "htf": build_view(
            "htf", "NQ", "60", "2025-05-19T00:00", "2025-05-31T00:00",
            sorted(HTF_STEPS and [i for i, s in STEP_OF_SHAPE.items() if s in HTF_STEPS]),
            "NQ 60-minute — the higher-timeframe frame, 19–30 May 2025",
            label_rules={"R4", "R5", "R3", "R35"}, height=430, gutter=200),
        "ltf": build_view(
            "ltf", "NQ", "5m", "2025-05-29T17:30", "2025-05-30T10:30",
            sorted([i for i, s in STEP_OF_SHAPE.items() if s in LTF_STEPS]),
            "NQ 5-minute — the entry frame, 29 May 17:30 → 30 May 10:30",
            label_rules={"R11", "R12", "R30", "R29"}, height=430, gutter=210),
    }
    p = EVID / "s1b" / "guided-pack.json"
    p.write_text(json.dumps(out), encoding="utf-8")
    for k, v in out.items():
        print(f'{k}: {v["bars"]} bars · steps {v["steps"]} · '
              f'{"; ".join(v["escaped"]) if v["escaped"] else "all shapes inside window"}')
    print(f"wrote {p} ({p.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
