
/* ── §04 worked examples ──────────────────────────────────────────────────
   The path each example took through the tree in §02, as a compact strip. These
   are transcribed from the engine's own rule log, not re-decided here. */
const PATHS = {
  dead: [
    ['R3',  'swing SMT-qualified'],
    ['R6',  'range still live?', 'no'],
    ['ASIDE', 'Stand aside — the range died on 12 May']
  ],
  friday: [
    ['R3',  'swing SMT-qualified'],
    ['R6',  'range live'],
    ['R7',  'SMT still current'],
    ['R18', 'nests across adjacent cycles?', 'no'],
    ['R24', 'Sequential Skip — 15m confirmed'],
    ['R30', '5m iFVG present'],
    ['R31', 'pre-09:30 taken', 'soft'],
    ['R29', 'invalidation defined'],
    ['R33', 'stop 27% of range', 'soft'],
    ['R35', 'target beyond entry'],
    ['R32', 'premium — correct for a short'],
    ['END', 'Sequential Skip — down-cycle']
  ]
};
document.querySelectorAll('.pathline[data-path]').forEach(el=>{
  const steps = PATHS[el.dataset.path] || [];
  el.innerHTML = '<span class="pstep" style="border:0;padding-left:0;color:var(--muted)">path through §02</span>' +
    steps.map(([r, txt, mode])=>{
      const cls = r==='ASIDE' ? 'pstep aside' : r==='END' ? 'pstep end'
                : mode==='soft' ? 'pstep soft' : 'pstep';
      const tag = (r==='ASIDE'||r==='END') ? '' : chip(r.slice(1)) + ' ';
      return '<span class="arw">→</span><span class="' + cls + '">' + tag + txt +
             (mode==='no' ? ' <b>— no</b>' : '') + '</span>';
    }).join('');
});

/* dOoMeR's own trades. No price levels are recorded in the corpus, so none are
   shown — the takeaway column is the value, and it is his wording, not ours. */
const CORPUS = [
 {id:'aura-24', t:'050726 — the double sequential skip',
  leaf:'Sequential Skip — down-cycle', cls:'end', rules:[24,30,33],
  setup:'A multi-day NQ long anchored on a yearly-then-quarterly HTF swing point with SMT, so pullbacks read as retracement rather than reversal — even through several daily and session cycles that failed to hold.',
  exec:'Entered on a confirmed inverse FVG after the double skip, stop at the low, held through repeated New-York checkpoints across nearly a full week.',
  take:'The clearest example of letting invalidated HTF bearish cycles justify continuing to hold. It also ends honestly: he closed early for an unrelated personal reason, not a technical signal — exits are not always signal-driven.'},

 {id:'aura-25', t:'Triad synchronisation — the trade taken on YM',
  leaf:'Cross-asset — same idea, different leg', cls:'end', rules:[25,34],
  setup:'A rare trade taken on YM instead of NQ, justified purely by triad synchronisation: a cracking correlation inside a shared FVG — ES and YM retrace, NQ does not — within a monthly/weekly range.',
  exec:'Entered on session-cycle close, stop at the anchoring low, moved to breakeven once in profit on an unfamiliar asset, trailed toward target overnight, stopped just short of full TP.',
  take:'The lesson outranks the trade: an "okay loss" is a setup matching previously-validated criteria that simply did not work; a "bad loss" is one taken from fear of missing a move.'},

 {id:'aura-18', t:'The weekly range — and a rule he broke himself',
  leaf:'Pre-session entry, against his own preference', cls:'soft', rules:[31,29],
  setup:'A late-February NQ/ES long framed off the full HTF cascade — a quarterly sequential SMT invalidated at a low with prior yearly still overhead, so only a shallow retracement was expected before continuation.',
  exec:'Placed a limit order inside an Asia-session gap, off-equilibrium — <b>violating his own "wait for New York" rule</b>. The ES leg missed its fill; NQ filled and worked out anyway. Later entries that same week are properly gated on session-cycle SMT.',
  take:'This is why R31 renders as a soft branch and not a gate. He broke it, said so, and it still worked — which is exactly what a preference is. It also walks a full week Mon→Thu and models a winning and a losing setup built from identical criteria.'},

 {id:'aura-19', t:'043026 — a high-impact news morning',
  leaf:'Standard nested-SMT entry', cls:'end', rules:[18,30],
  setup:'A news morning, with his news philosophy stated outright: he ignores the informational content and the outcome of a release entirely, and tracks only its <b>timing</b> — volatility timing matters more than narrative.',
  exec:'Read through an SMT fill — one correlated asset retraces into a shared FVG and another does not — with swing points qualified by SMT.',
  take:'A reminder that the model never asks what the news said. Treating a release as a clock rather than a story is what keeps the read mechanical.'}
];
document.getElementById('corpusTrades').innerHTML = CORPUS.map(c=>
 '<div style="border-top:1px solid var(--line);padding:17px 0 3px">'+
 '<div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin:0 0 9px">'+
   '<span class="tiern">'+c.id+'</span>'+
   '<span class="tiert">'+c.t+'</span>'+
   '<span class="pstep '+(c.cls==='soft'?'soft':'end')+'" style="font-family:Archivo,sans-serif;font-size:12px">'+c.leaf+'</span>'+
   '<span>'+chips(c.rules)+'</span>'+
 '</div>'+
 '<table class="ledger">'+
 '<tr><td>Setup</td><td>'+c.setup+'</td></tr>'+
 '<tr><td>Execution</td><td>'+c.exec+'</td></tr>'+
 '<tr><td>Takeaway</td><td>'+c.take+'</td></tr>'+
 '</table></div>').join('');
