"""Build the three marked-up worked-example figures from real bars + the S1d shape spec."""
import io, json, sys, pathlib
REPO = pathlib.Path(r"C:\Users\PaulRussell\repos\neurospect-learn")
sys.path.insert(0, str(REPO / "api" / "scripts"))
import aura_figure_pack as A

SPEC = json.load(io.open(REPO/"api/docs/evidence/s1d/chart-shapes-spec.json", encoding="utf-8"))
DRAW = SPEC["draw"]
def by(idx): return [DRAW[i] for i in idx]

FIGS = {}
def build(key, sym, res, a, b, idx, label, **kw):
    fig = A.build(sym, res, a, b, label)
    svg, escaped = A.svg_markup(fig, by(idx), **kw)
    FIGS[key] = dict(svg=svg, escaped=escaped, bars=len(fig["bars"]), label=label,
                     shapes=len(idx))
    print(f"{key:8} {label}")
    print(f"         {len(fig['bars'])} bars · {len(idx)} shapes · "
          f"{'escaped window: '+ '; '.join(escaped) if escaped else 'all shapes inside the window'}")

# 1 — the dead range that produced four identical stand-asides, and the close that killed it
build("dead", "NQ", "D", "2025-04-22T00:00", "2025-05-23T00:00", [0,1,2,3,4,5,6],
      "NQ daily — the range that died on 12 May, and four stand-asides that followed",
      label_rules={"R4","R5","R3","R6"}, height=400, gutter=210)

# 2 — Friday's trade, HTF: the live range, its zones, the qualifying swing, entry/stop/target
build("htf", "NQ", "60", "2025-05-19T00:00", "2025-05-31T00:00", [7,8,9,10,11,12,29,30,31],
      "NQ 60-minute — the live range, and where the short was taken inside it",
      label_rules={"R4","R5","R3","R30","R33","R35"}, height=430, gutter=200)

# 3 — Friday's trade, LTF: every iFVG the engine boxed, and the one it traded
#     R33 (stop 21,567.50) and R35 (target 20,727) are BOTH excluded. The stop alone
#     is 225.75 pts — wider than this whole day's range — so including either would
#     flatten every iFVG box to a hairline. That exclusion is R27's cascade problem,
#     and the page says so rather than quietly cropping.
build("ltf", "NQ", "5m", "2025-05-29T17:00", "2025-05-30T17:00",
      [13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29],
      "NQ 5-minute — 15 boxed iFVGs in premium, and the one that was traded",
      label_rules={"R30","R12"}, height=440, gutter=190)

# 4 — the entry magnified. The traded iFVG is 1.5 points wide (6 ticks); on the
#     day view above it is ~2px tall, which is itself the honest fact about the
#     precision this model asks for.
build("zoom", "NQ", "5m", "2025-05-29T19:30", "2025-05-30T10:30",
      [15,16,17,23,24,25,26,27,28,29],
      "NQ 5-minute, magnified — the traded iFVG, its retest, and the entry",
      label_rules={"R11","R12","R30"}, height=400, gutter=210)

io.open("worked-figs.json","w",encoding="utf-8").write(json.dumps(FIGS))
print("\nwrote worked-figs.json")
