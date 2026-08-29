"""Assemble the Aura Protocol artifact: real-bar SVGs + schematics + rule text."""
import io, json, re, sys, pathlib

REPO = pathlib.Path(r"C:\Users\PaulRussell\repos\neurospect-learn")
SCR = pathlib.Path(__file__).parent
sys.path.insert(0, str(REPO / "api" / "scripts"))
from aura_figure_pack import svg_gaps, svg_ifvg  # noqa: E402

pack = json.load(io.open(REPO / "api/docs/evidence/s1b/figure-pack.json", encoding="utf-8"))
ltf = pack["figures"]["ltf_5m"]
rules = io.open(SCR / "rules-subset.json", encoding="utf-8").read()

# ── D2 · Range anatomy — schematic, definitional ────────────────────────────
RANGE = '''<svg class="sch" viewBox="0 0 1000 330" role="img" xmlns="http://www.w3.org/2000/svg"
 aria-label="Range anatomy: this model uses only the 0, 0.5 and 1 levels; the 0.25 and 0.75 quadrants belong to a different model and are not drawn.">
  <text class="hd" x="20" y="28">THE RANGE — high to low, by the expansive move</text>
  <rect class="band" x="120" y="56" width="420" height="98" fill="var(--stop)" fill-opacity=".12"/>
  <rect class="band" x="120" y="154" width="420" height="98" fill="var(--targ)" fill-opacity=".12"/>
  <line x1="120" y1="56" x2="540" y2="56" stroke-width="1.6"/>
  <line x1="120" y1="252" x2="540" y2="252" stroke-width="1.6"/>
  <line x1="120" y1="154" x2="540" y2="154" stroke-width="1.3" stroke-dasharray="6 4"/>
  <text x="552" y="60">1.0 · range high</text>
  <text x="552" y="158">0.5 · equilibrium</text>
  <text x="552" y="256">0.0 · range low</text>
  <text x="134" y="92" fill="var(--stop)">PREMIUM</text>
  <text x="134" y="128" fill="var(--stop)" font-size="9.5">sell half · lower your R:R here</text>
  <text x="134" y="190" fill="var(--targ)">DISCOUNT</text>
  <text x="134" y="226" fill="var(--targ)" font-size="9.5">buy half</text>
  <line class="dim" x1="120" y1="105" x2="540" y2="105" stroke-dasharray="2 6" stroke-width="1"/>
  <line class="dim" x1="120" y1="203" x2="540" y2="203" stroke-dasharray="2 6" stroke-width="1"/>
  <g stroke="var(--stop)" stroke-width="2.2">
    <line x1="700" y1="97" x2="716" y2="113"/><line x1="716" y1="97" x2="700" y2="113"/>
    <line x1="700" y1="195" x2="716" y2="211"/><line x1="716" y1="195" x2="700" y2="211"/>
  </g>
  <text class="dim" x="552" y="109">0.75</text>
  <text class="dim" x="552" y="207">0.25</text>
  <text x="726" y="109" fill="var(--stop)" font-size="10">not used</text>
  <text x="726" y="207" fill="var(--stop)" font-size="10">not used</text>
  <line x1="20" y1="286" x2="980" y2="286" stroke="var(--line)"/>
  <text x="20" y="308" fill="var(--stop)">NO QUADRANTS —</text>
  <text x="168" y="308">delete 0.236 / 0.382 / 0.618 / 0.786 from the fib tool. A fib left on its</text>
  <text x="20" y="323" class="dim">defaults silently imports another model’s framework onto your chart.  R5 — a flagged divergence.</text>
</svg>'''

# ── D5 · The gap family — schematic, definitional ───────────────────────────
def _c(x, top, bot, o, c, col):
    """one schematic candle: x centre, wick top/bot, body o..c"""
    a, b = (o, c) if o < c else (c, o)
    return (f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bot}" stroke="{col}" stroke-width="1.2"/>'
            f'<rect x="{x-6}" y="{a}" width="12" height="{max(2,b-a)}" fill="{col}" stroke="{col}"/>')

GAPFAM = f'''<svg class="sch" viewBox="0 0 1000 300" role="img" xmlns="http://www.w3.org/2000/svg"
 aria-label="The four gap types this model names: FVG, iFVG, NWOG and NDOG, with liquidity nested inside the gap as the target.">
  <g>
    <text class="hd" x="20" y="24">FVG</text>
    <text x="20" y="42" class="dim">bar 1 high &lt; bar 3 low</text>
    {_c(60,70,150,86,132,'var(--up)')}{_c(100,60,120,112,74,'var(--up)')}{_c(140,96,190,178,110,'var(--up)')}
    <rect x="46" y="86" width="108" height="24" fill="var(--gap)" fill-opacity=".22" stroke="var(--gap)"/>
    <line x1="46" y1="98" x2="154" y2="98" stroke="var(--gap)" stroke-dasharray="3 3" stroke-width="1.4"/>
    <text x="20" y="234" fill="var(--gap)">the dotted level is the</text>
    <text x="20" y="250" fill="var(--gap)">liquidity INSIDE the gap</text>
    <text x="20" y="268" class="dim">— that is the target, not</text>
    <text x="20" y="284" class="dim">the gap boundary. R12</text>
  </g>
  <line class="dim" x1="245" y1="16" x2="245" y2="284" stroke-dasharray="3 4"/>
  <g transform="translate(245,0)">
    <text class="hd" x="20" y="24">iFVG</text>
    <text x="20" y="42" class="dim">price CLOSED through it</text>
    {_c(60,70,150,86,132,'var(--up)')}{_c(100,60,120,112,74,'var(--up)')}{_c(140,96,190,178,110,'var(--up)')}
    {_c(180,100,200,110,192,'var(--dn)')}
    <rect x="46" y="86" width="148" height="24" fill="none" stroke="var(--qual)" stroke-width="1.6" stroke-dasharray="4 3"/>
    <text x="20" y="234" fill="var(--qual)">now an INVERSE FVG —</text>
    <text x="20" y="250" fill="var(--qual)">the preferred 5m entry</text>
    <text x="20" y="268" class="dim">A close, never a wick.</text>
    <text x="20" y="284" class="dim">R30 · R6</text>
  </g>
  <line class="dim" x1="490" y1="16" x2="490" y2="284" stroke-dasharray="3 4"/>
  <g transform="translate(490,0)">
    <text class="hd" x="20" y="24">NWOG</text>
    <text x="20" y="42" class="dim">new week opening gap</text>
    {_c(60,70,140,80,130,'var(--dn)')}
    <rect x="46" y="130" width="130" height="34" fill="var(--gap)" fill-opacity=".22" stroke="var(--gap)"/>
    {_c(150,150,215,164,206,'var(--up)')}
    <text x="46" y="238" class="dim">Fri close → Sun open</text>
    <text x="20" y="262" class="dim">Same treatment as an FVG —</text>
    <text x="20" y="278" class="dim">box it, target what is inside.</text>
  </g>
  <line class="dim" x1="735" y1="16" x2="735" y2="284" stroke-dasharray="3 4"/>
  <g transform="translate(735,0)">
    <text class="hd" x="20" y="24">NDOG</text>
    <text x="20" y="42" class="dim">new day opening gap</text>
    {_c(60,80,150,92,140,'var(--dn)')}
    <rect x="46" y="140" width="130" height="22" fill="var(--gap)" fill-opacity=".22" stroke="var(--gap)"/>
    {_c(150,150,210,160,200,'var(--up)')}
    <text x="46" y="238" class="dim">prior close → next open</text>
    <text x="20" y="262" fill="var(--stop)">These four only. No BPR,</text>
    <text x="20" y="278" fill="var(--stop)">no volume-imbalance. R11</text>
  </g>
</svg>'''

# ── D3 · M1→M12 as a dependency chain ───────────────────────────────────────
TIERS = [
    ("Structure", [("M1", "Swing points", "3-candle pivots", "short ray"),
                   ("M2", "SMT-qualify", "yellow vs grey", "recolour · GATE")]),
    ("The frame", [("M3", "The range", "largest expansive move", "ray, terminated"),
                   ("M4", "Anchor extremes", "qualified swings only", "ray"),
                   ("M5", "Zones", "0 / 0.5 / 1 only", "fib, bounded")]),
    ("The draw", [("M6", "Gaps", "FVG iFVG NWOG NDOG", "rectangle"),
                  ("M7", "Liquidity inside", "the internal level", "short segment"),
                  ("M8", "Draw on liquidity", "the one target", "segment"),
                  ("M9", "Confluence", "where gaps stack", "note")]),
    ("Execute", [("M10", "Cascade down", "→ 5m", "repeat M1–M2"),
                 ("M11", "Entry objects", "iFVG · stop · target", "position tool"),
                 ("M12", "Write invalidation", "on the chart", "text · GATE")]),
]


def chain_svg():
    W, rowh, top = 1000, 84, 34
    p = [f'<svg class="sch" viewBox="0 0 {W} {top + rowh*len(TIERS) + 16}" role="img" '
         'xmlns="http://www.w3.org/2000/svg" aria-label="The markup order M1 to M12 as a '
         'dependency chain in four tiers: structure, the frame, the draw, execute. Each step '
         'names the drawing primitive it must be made with.">']
    for ti, (tname, steps) in enumerate(TIERS):
        y = top + ti * rowh
        p.append(f'<text class="hd" x="46" y="{y-9}" font-size="11" fill="var(--muted)">{tname.upper()}</text>')
        n = len(steps)
        bw = (W - 20 - (n - 1) * 16) / n
        for si, (m, title, sub, prim) in enumerate(steps):
            x = 10 + si * (bw + 16)
            gate = "GATE" in prim
            stroke = "var(--qual)" if gate else "var(--line)"
            p.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="56" rx="2" '
                     f'fill="var(--surface)" stroke="{stroke}" stroke-width="{1.8 if gate else 1}"/>')
            p.append(f'<text x="{x+10:.0f}" y="{y+17:.0f}" font-size="10" fill="var(--muted)">{m}</text>')
            p.append(f'<text class="hd" x="{x+10:.0f}" y="{y+33:.0f}" font-size="12.5">{title}</text>')
            p.append(f'<text x="{x+10:.0f}" y="{y+48:.0f}" font-size="9.5" '
                     f'fill="{"var(--qual)" if gate else "var(--muted)"}">{prim}</text>')
            if si < n - 1:
                ax = x + bw
                p.append(f'<line x1="{ax+3:.0f}" y1="{y+28}" x2="{ax+11:.0f}" y2="{y+28}" '
                         'stroke="var(--muted)" stroke-width="1"/>')
                p.append(f'<polygon points="{ax+13:.0f},{y+28} {ax+8:.0f},{y+25} {ax+8:.0f},{y+31}" '
                         'fill="var(--muted)"/>')
        if ti < len(TIERS) - 1:
            p.append(f'<line x1="26" y1="{y+56}" x2="26" y2="{y+rowh-10}" stroke="var(--qual)" '
                     'stroke-width="1.2" stroke-dasharray="3 3"/>')
            p.append(f'<polygon points="26,{y+rowh-6} 23,{y+rowh-12} 29,{y+rowh-12}" fill="var(--qual)"/>')

    p.append("</svg>")
    return "\n".join(p)


src = io.open(SCR / "aura-protocol.src.html", encoding="utf-8").read()
part2 = io.open(SCR / "aura-protocol.part2.js", encoding="utf-8").read()
part3 = io.open(SCR / "aura-protocol.part3.js", encoding="utf-8").read()
part4 = io.open(SCR / "aura-protocol.part4.js", encoding="utf-8").read()
part5 = io.open(SCR / "aura-protocol.part5.js", encoding="utf-8").read()
# part5 (tools) before part4 (the runner), which calls mountTools()
src = src.replace("</script>", part2 + part3 + part5 + part4 + "\n</script>")

# __R##__ written in prose becomes a real rule chip; soft/flagged is read from the
# rulebook, never assigned by hand.
_R = json.loads(rules)
def _chip(m):
    n = m.group(1); r = _R.get(n)
    soft = " soft" if (r and (r["s"] or r["f"])) else ""
    return ('<button class="rc' + soft + '" data-r="' + n + '" type="button" '
            'aria-label="Rule ' + n + '">R' + n + '</button>')
src, _n = re.subn(r"__R(\d+)__", _chip, src)
print("  rule chips expanded in prose:", _n)

# the guided run's two views, every shape tagged with the step that draws it
gp = json.load(io.open(REPO / "api/docs/evidence/s1b/guided-pack.json", encoding="utf-8"))
for key, ph in (("htf", "__GUIDED_HTF__"), ("ltf", "__GUIDED_LTF__")):
    g = gp[key]
    src = src.replace(ph, '<svg viewBox="0 0 1000 430" role="img" '
        'xmlns="http://www.w3.org/2000/svg" aria-label="' + g["label"] + '">'
        + g["svg"] + "</svg>")
    print("  guided " + key + ": " + str(g["bars"]) + " bars, steps " + str(g["steps"]))

# the three marked-up worked examples, from real bars + the S1d shape spec
wf = json.load(io.open(SCR / "worked-figs.json", encoding="utf-8"))
HEIGHTS = {"dead": 400, "htf": 430, "ltf": 440, "zoom": 400}
for key, ph in (("dead", "__WX_DEAD__"), ("htf", "__WX_HTF__"),
                ("ltf", "__WX_LTF__"), ("zoom", "__WX_ZOOM__")):
    f = wf[key]
    svg = ('<svg viewBox="0 0 1000 ' + str(HEIGHTS[key]) + '" role="img" '
           'xmlns="http://www.w3.org/2000/svg" aria-label="' + f["label"] + '">'
           + f["svg"] + "</svg>")
    src = src.replace(ph, svg)
    note = ph.replace("__WX_", "__WXNOTE_")
    if f["escaped"]:
        src = src.replace(note, '<p class="wxnote"><b>Reported, not silently clamped:</b> '
                          + "; ".join(f["escaped"])
                          + '. A drawing that runs past its data asserts more than the chart shows.</p>')
    else:
        src = src.replace(note, "")
    print("  " + key + ": " + str(f["bars"]) + " bars, " + str(f["shapes"]) + " shapes, "
          + (str(len(f["escaped"])) + " reported" if f["escaped"] else "all inside window"))

def wrap(inner, label):
    return (f'<svg viewBox="0 0 1000 380" role="img" xmlns="http://www.w3.org/2000/svg" '
            f'aria-label="{label}">{inner}</svg>')

subs = {
    "__RULES_JSON__": rules,
    "__SVG_LINES__": wrap(svg_gaps(ltf, "lines"),
        "NQ 5-minute bars for 27 May 2025 with 15 gaps drawn as 30 infinite horizontal lines "
        "running the full width of the chart."),
    "__SVG_BOUNDED__": wrap(svg_gaps(ltf, "bounded"),
        "The same NQ 5-minute bars with the same 15 gaps drawn as rectangles bounded from the bar "
        "that formed each gap to the bar that mitigated it."),
    "__SVG_IFVG__": wrap(svg_ifvg(ltf, 4),
        "One bearish gap on real NQ bars: formed, mitigated, then closed through, at which point it "
        "becomes an inverse FVG."),
    "__SVG_RANGE__": RANGE,
    "__SVG_GAPFAM__": GAPFAM,
    "__SVG_CHAIN__": chain_svg(),
}
missing = [k for k in subs if k not in src]
if missing:
    raise SystemExit(f"placeholder(s) not found in source: {missing}")
for k, v in subs.items():
    src = src.replace(k, v)
left = [t for t in ("__RULES_JSON__", "__SVG_", "__WX_", "__WXNOTE_", "__R1__", "__GUIDED_") if t in src]
if left:
    raise SystemExit(f"unsubstituted placeholder remains: {left}")

out = SCR / "aura-protocol.html"
out.write_text(src, encoding="utf-8")
print(f"wrote {out} — {len(src)/1024:.0f} KB")
print(f"  candles in fig 1: {subs['__SVG_LINES__'].count('class=\"bd')} (expect {len(ltf['bars'])})")
print(f"  gap lines fig 1 : {subs['__SVG_LINES__'].count('gapline')} (expect {2*len(ltf['gaps']['items'])})")
print(f"  gap boxes fig 2 : {subs['__SVG_BOUNDED__'].count('gapbox')} (expect {len(ltf['gaps']['items'])})")
