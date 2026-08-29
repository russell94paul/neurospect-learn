
/* ═══════════════════════════════════════════════════════════════════════════
   §01 THE GUIDED RUN — one state machine drives the rail, the chart, the step
   card, the caption and the progress line. No second timer, nothing derived
   twice. Every level revealed on the chart is a recorded S1d shape; a step with
   no recorded artifact says so rather than showing an empty chart.
   ═══════════════════════════════════════════════════════════════════════════ */

const STEPS = [
 /* ── Prepare ───────────────────────────────────────────────────────────── */
 {ph:'Prepare', id:'SET', t:'Set the chart up once', art:'ACTION', view:'htf', rules:[16,31,1],
  do:'Three panes, one symbol each — <b>NQ · ES · YM</b>. Timezone <code>(UTC-4) New York</code>, session <code>Extended trading hours</code>, then <code>Apply to all</code>. Turn the <b>magnet on</b> and save a chart-settings template.',
  prim:'Chart settings · save as a template',
  says:'A swing point drawn two ticks off the actual high is a swing point you did not mark. The magnet is not a convenience.',
  warn:'The Aura Asset (6S) is a flagged fourth leg and is not offered in Tradezella. Do not block on it.'},

 {ph:'Prepare', id:'PRE', t:'Pre-market readiness', art:'ACTION', view:'htf', rules:[47,48,40,49], gate:true,
  do:'Circuit breakers written and <b>visible</b> — two-loss daily max, 2–3R daily stop, the ten-minute rule. Phone out of the room, chats closed. Prior session reviewed and today’s plan written <b>before</b> price moves.',
  prim:'Written down, not held in your head',
  says:'The gate is the three questions: what am I looking for, where, and what would make me stand aside? If you cannot answer all three, the session has not started.'},

 /* ── Frame the higher timeframe ────────────────────────────────────────── */
 {ph:'Frame', id:'M1', t:'Mark the swing points', art:'NOT-RECORDED', view:'htf', mi:1, rules:[1,2],
  do:'Mark the <b>3-candle pivots</b> on the timeframe you are framing. Candle 2 is the pivot — lower low then higher low for a swing low, the mirror for a swing high.',
  prim:'Short ray from the pivot — until it is swept, then it stops there',
  says:'Swing points are fractal: identical across every timeframe, and the mechanics do not change with resolution.',
  gap:'The engine recorded only the swing it went on to <i>qualify</i>, never the raw candidates it considered. So there is nothing to reveal here — the chart is not empty because the step is trivial, it is empty because this step was never instrumented.'},

 {ph:'Frame', id:'M2', t:'SMT-qualify them', art:'DRAWN', view:'htf', mi:2, rules:[3], gate:true,
  do:'Across <b>NQ · ES · YM</b>, mark which swings hold on all legs and which are swept on some. Recolour: <b>qualified → yellow</b>, unqualified → grey and thin.',
  prim:'Recolour · this is the filter everything downstream leans on',
  says:'The high at <b>21,562.25</b> on 20 May is the one that qualified. NQ took it by 21 ticks; <b>ES missed by 141 and YM by 234</b>. That divergence is the whole signal.'},

 {ph:'Frame', id:'M3', t:'Find the range', art:'DRAWN', view:'htf', mi:3, rules:[4,9],
  do:'Find the <b>largest expansive move between two swing points</b> — that move <i>is</i> the range. Draw its high and its low. Not a time-based range.',
  prim:'Ray from the anchoring pivot — terminated at the invalidating close, never past it',
  says:'<b>20,727.00 – 21,562.25</b>, 835.25 points, the expansive move 20 → 23 May. It was still live at the right edge, so these are drawn as rays that run on.',
  warn:'If the range is not obvious, zoom out until it is. Overlapping ranges are acceptable — do not force one.'},

 {ph:'Frame', id:'M4', t:'Anchor the extremes', art:'UNRESOLVED', view:'htf', mi:4, rules:[8],
  do:'Anchor the range extremes on <b>SMT-qualified swings only</b>. Where a candidate looks false across the triad, prefer the high or low <b>actually swept on all three legs</b> over the most extreme one.',
  prim:'Ray · anchored, not eyeballed',
  says:'Here neither extreme was swept on every leg, and a materially different all-legs-swept candidate exists for each.',
  gap:'<b>Rule 8 contradicts itself.</b> Its two sentences cannot both be satisfied by one swing, so the engine reports both candidates and refuses to re-anchor. That refusal is deliberate — a clean answer here would be invented.'},

 {ph:'Frame', id:'M5', t:'Discount, equilibrium, premium', art:'DRAWN', view:'htf', mi:5, rules:[5],
  do:'Use the <b>Fib Retracement</b> tool with <b>only 0, 0.5 and 1 enabled</b>. Delete 0.236 / 0.382 / 0.618 / 0.786 from the tool’s settings first.',
  prim:'Fib or shaded box — bounded to the range’s own span',
  says:'Equilibrium sits at <b>21,144.62</b>. The short was taken at 0.74 of the range — in premium, the correct side.',
  warn:'A fib left on its defaults silently imports another model’s framework onto your chart. This model uses no quadrants.'},

 /* ── Draw down ─────────────────────────────────────────────────────────── */
 {ph:'Draw', id:'M6', t:'Box every gap', art:'DRAWN', view:'ltf', mi:6, rules:[11],
  do:'Box every <b>FVG, iFVG, NWOG and NDOG</b> sitting in the range’s premium (for a short) or discount (for a long). Only these four types.',
  prim:'Rectangle — formation bar → mitigation bar; if still live, to the current edge only',
  says:'Fifteen qualified on the size floor, plus the <b>NDOG</b> at 21,371.25–21,385.00 that formed at the 18:00 open. Four more were excluded for being under four ticks.',
  warn:'No BPR. No volume-imbalance vocabulary. The four types are the whole list.'},

 {ph:'Draw', id:'M7', t:'Mark the liquidity inside them', art:'DRAWN', view:'ltf', mi:7, rules:[12,13],
  do:'Mark the swing high or low nested <b>inside</b> each gap. <b>That internal level is the target</b> — not the gap boundary.',
  prim:'Short bounded segment inside the box',
  says:'<b>21,342.00</b>, found inside the gap with no zoom-in needed. When none is visible: look left for a resting untaken level, or zoom in until a lower-timeframe swing appears inside the same gap.'},

 {ph:'Draw', id:'M8', t:'Mark the draw on liquidity', art:'DRAWN', view:'htf', mi:8, rules:[12,35],
  do:'Mark the <b>one target you are actually playing for</b>: the extreme of the timeframe being played, refined to the liquidity-within-a-gap in the range’s discount (long) or premium (short).',
  prim:'Bounded segment · one target, not a wish list',
  says:'<b>20,727.00</b> — the range extreme. 2.7R planned against a 225.75-point stop.',
  warn:'This level is on the 60-minute view. On the 5-minute frame it sits 615 points away and cannot be drawn without flattening everything else.'},

 {ph:'Draw', id:'M9', t:'Note the confluence', art:'NOT-RECORDED', view:'ltf', mi:9, rules:[14],
  do:'Note where gaps <b>overlap</b> (NWOG × FVG), where look-left liquidity and liquidity-inside stack, and where a gap sits near equilibrium. These raise a gap’s probability additively.',
  prim:'A note, not a drawing',
  says:'A 4-hour bearish gap at 21,447.25–21,485.25 formed on 29 May and paired with the daily cycle — reported as supporting confirmation, never as a gate.',
  gap:'The engine reports cross-cycle pairing but never scored confluence as a quantity, so there is no shape to reveal. Rule 14 says these stack; nothing here measures by how much.'},

 {ph:'Draw', id:'M10', t:'Cascade down to the entry timeframe', art:'ACTION', view:'ltf', rules:[27],
  do:'Walk down: Monthly → Weekly → Daily/Session → 4H → 15m → <b>5m</b>. Repeat M1 and M2 <b>at the entry timeframe only</b> — do not re-mark the whole higher-timeframe structure.',
  prim:'Change resolution · re-run two steps, not twelve',
  says:'The 4-hour did not confirm. The 15-minute did, at 29 May 14:45 — which is what makes this a Sequential Skip rather than a standard nested entry.',
  warn:'One resolution cannot hold both a month-long range and a five-minute box. That is why this is a cascade and not a single chart.'},

 /* ── Execute ───────────────────────────────────────────────────────────── */
 {ph:'Execute', id:'M11', t:'Draw the entry objects', art:'DRAWN', view:'ltf', mi:11, rules:[30,33],
  do:'On the 5-minute: the <b>iFVG</b> in the bias direction, the <b>stop</b> at the invalidation level, and the <b>target</b>.',
  prim:'Bounded segments or the position tool — the trade’s lifetime, not the whole session',
  says:'Entry <b>21,341.75</b> at 08:05, retesting a zone <b>1.5 points wide</b>. Stop <b>21,567.50</b>, the swept high of the qualifying SMT — risk 225.75 points.',
  warn:'That stop is 27% of the range, over the declared 25% flag. Rule 34’s answer is the same idea on a correlated leg with a tighter gap.'},

 {ph:'Execute', id:'M12', t:'Write the invalidation on the chart', art:'DRAWN', view:'ltf', mi:12, rules:[29], gate:true,
  do:'Write it as a <b>text label on the chart</b>, not only in your head: <i>if price does this, the idea is wrong.</i>',
  prim:'Text label · on the chart',
  says:'<b>A close beyond 21,567.50 kills this short.</b> The framework supplies the next question to ask; it is not a licence to enter without one.'},

 {ph:'Execute', id:'D0', t:'Take the entry decision', art:'ACTION', view:'ltf', rules:[30,29,35], decide:true, branch:true,
  do:'Walk the gates in order. Every one of them can end in <b>stand aside</b>, and that is a result.',
  prim:'The decision tree in §02',
  says:'This session’s path ran: qualified swing → range live → SMT current → no nesting → <b>Sequential Skip</b> → iFVG present → pre-09:30 taken (soft) → invalidation defined → stop 27% → target beyond entry → premium. Eleven nodes to one entry.'},

 {ph:'Execute', onlyIfTaken:true, id:'SIZE', t:'Size the risk', art:'ACTION', view:'ltf', rules:[39,43,52,50], gate:true,
  do:'Risk <b>1–2% of total capital</b>, computed in <b>R</b>, never in dollars. Do the negative visualisation — pre-accept the loss before you take it.',
  prim:'Position size · in R',
  says:'The gate is three questions: does this fit my plan, did I define this setup in advance, and am I trading the market rather than my P&L?'},

 /* ── After ─────────────────────────────────────────────────────────────── */
 {ph:'After', onlyIfTaken:true, id:'MAN', t:'Manage what you are in', art:'ACTION', view:'ltf', rules:[35,45],
  do:'Recalculate risk <b>from the current price, not from entry</b>. Hold at least 1:1 from here. Trail as structure develops.',
  prim:'Re-measure, do not re-hope',
  says:'Expect price <b>not</b> to run cleanly to target — new ranges and SMT will form on the way. A move to breakeven is not "free"; that is the lie rule 45 exists to name.'},

 {ph:'After', onlyIfTaken:true, id:'EXIT', t:'Exit at plan', art:'ACTION', view:'ltf', rules:[36,43,35],
  do:'Exit at the higher-timeframe range’s equilibrium, <b>or</b> hold for liquidity in its discount or extreme. Record the outcome in <b>R</b>.',
  prim:'The plan you already wrote',
  says:'This one never resolved. It ran <b>1.20R in favour and 0.41R against</b>, then the bars ran out — a measurement gap, not a breakeven and not a loss.'},

 {ph:'After', id:'REV', t:'Review, and log what you did not take', art:'ACTION', view:'ltf', rules:[53,49],
  do:'Journal the trades <b>and every missed or cancelled setup</b>, with a screenshot and your emotional state. Then the five-minute check: did I follow my plan, what happened if not, one thing to do better.',
  prim:'The per-trade card in §05',
  says:'Four of the five days in this week were stand-asides. A day correctly stood aside is a record, not a blank — and no instrument you currently have keeps them.'}
];

const ART = {
 'DRAWN':        {k:'drawn',  l:'Drawn on the chart'},
 'NOT-RECORDED': {k:'notrec', l:'Not recorded'},
 'UNRESOLVED':   {k:'unres',  l:'Unresolved in the rulebook'},
 'ACTION':       {k:'act',    l:'Action — nothing to draw'}
};

const RS = 'aura-run-v1';
let run = {i:0, done:{}, view:null, aside:null};
try{ run = Object.assign(run, JSON.parse(localStorage.getItem(RS)||'{}')); }catch(e){}
function saveRun(){ try{ localStorage.setItem(RS, JSON.stringify(run)); }catch(e){} }

const railEl = document.getElementById('rail');
const cardEl = document.getElementById('stepCard');
const wrapEl = document.getElementById('chartWrap');

/* the rail is built once; only state classes change per step */
railEl.innerHTML = (()=>{
  let html = '', ph = null;
  STEPS.forEach((s,ix)=>{
    if(s.ph !== ph){ ph = s.ph; html += '<p class="railph">'+ph+'</p>'; }
    html += '<button class="rstep" data-ix="'+ix+'" type="button">'+
      '<span class="rdot"></span>'+
      '<span class="rid">'+s.id+'</span>'+
      '<span class="rt">'+s.t+'</span>'+
      (s.gate?'<span class="rgate" title="hard gate">◆</span>':'')+
      '</button>';
  });
  return html;
})();

function stepView(s){ return run.view || s.view; }

function renderRun(){
  const i = Math.max(0, Math.min(STEPS.length-1, run.i));
  run.i = i;
  const s = STEPS[i];

  /* rail state */
  railEl.querySelectorAll('.rstep').forEach(b=>{
    const ix = +b.dataset.ix;
    const st = STEPS[ix];
    const na = run.aside==='aside' && st.onlyIfTaken;
    b.className = 'rstep' + (ix===i?' active':'') + (run.done[st.id]&&!na?' done':'')
                + (na?' na':'')
                + (ix<i && !run.done[st.id] && !na ? ' skipped':'');
    b.title = na ? 'Not applicable — you stood aside' : '';
  });

  /* chart: correct view, and every shape up to this step */
  const v = stepView(s);
  wrapEl.querySelectorAll('.chart').forEach(c=>c.classList.toggle('on', c.dataset.v===v));
  document.querySelectorAll('.vbtn').forEach(b=>b.classList.toggle('sel', b.dataset.view===v));
  const upto = STEPS.slice(0, i+1).reduce((m,x)=> x.mi ? Math.max(m,x.mi) : m, 0);
  wrapEl.querySelectorAll('.mstep').forEach(g=>{
    g.classList.toggle('shown', +g.dataset.mi <= upto);
    g.classList.toggle('justnow', s.mi && +g.dataset.mi === s.mi);
  });
  document.getElementById('stageLab').textContent =
    v==='htf' ? 'NQ 60-minute · 19–30 May 2025' : 'NQ 5-minute · 29 May 17:30 → 30 May 10:30';
  document.getElementById('stageNote').innerHTML = s.mi
    ? 'Everything drawn up to and including <b>'+s.id+'</b> is showing. Earlier steps stay on the chart — that is what makes the next one readable.'
    : 'Nothing new is drawn at this step. The chart holds the markup you have already made.';

  /* the step card */
  const a = ART[s.art];
  cardEl.innerHTML =
    '<div class="scardhd">'+
      '<span class="sph">'+s.ph+'</span>'+
      '<span class="sid">'+s.id+'</span>'+
      '<h3>'+s.t+'</h3>'+
      (s.gate?'<span class="gatetag">hard gate</span>':'')+
      '<span class="artpill '+a.k+'">'+a.l+'</span>'+
    '</div>'+
    '<p class="sdo">'+s.do+'</p>'+
    '<div class="smeta">'+
      '<span class="sprim">'+s.prim+'</span>'+
      '<span class="srules">'+chips(s.rules)+'</span>'+
    '</div>'+
    (s.warn?'<p class="swarn">'+s.warn+'</p>':'')+
    '<div class="ssays"><span class="ssayshd">On this session</span>'+s.says+'</div>'+
    (s.gap?'<div class="sgap"><span class="ssayshd">Why nothing appears</span>'+s.gap+'</div>':'')+
    (s.decide?'<p class="sdecide">Work it in <a href="#decide">§03 — the entry decision</a>, then say how it ended.</p>':'')+
    (s.branch?'<div class="branchbox">'+
      '<span class="ssayshd">How did the gates end?</span>'+
      '<div class="opts">'+
        '<button class="opt" data-br="taken" type="button">Every gate passed \u2014 I am taking it'+
          '<span class="why">continue to sizing and management</span></button>'+
        '<button class="opt" data-br="aside" type="button">A gate failed \u2014 I am standing aside'+
          '<span class="why">the common outcome \u00b7 four of five days in this week</span></button>'+
      '</div>'+
      (run.aside==='aside'?'<p class="asidenote"><b>Stood aside.</b> Sizing, management and exit '+
        'are not applicable, so the run goes straight to the review \u2014 because <b>a day correctly '+
        'stood aside is a record, not a blank.</b> '+chip(51)+'</p>':'')+
      (run.aside==='taken'?'<p class="takennote"><b>Taken.</b> The remaining steps apply.</p>':'')+
    '</div>':'');

  /* controls + progress */
  document.getElementById('runPrev').disabled = i===0;
  const mk = document.getElementById('runMark');
  const last = i===STEPS.length-1;
  mk.textContent = (s.branch && !run.aside) ? 'Choose an outcome first'
                 : run.done[s.id] ? (last?'Marked — finish':'Marked — next →')
                                  : (last?'Mark it, finish':'Mark it, next →');
  mk.disabled = !!(s.branch && !run.aside);
  mk.classList.toggle('ismarked', !!run.done[s.id]);
  const n = Object.keys(run.done).filter(k=>run.done[k]).length;
  document.getElementById('runProg').innerHTML =
    'Step <b>'+(i+1)+'</b> of '+STEPS.length+' · '+n+' marked'+
    (n===STEPS.length?' · session complete':'');
  const act = railEl.querySelector('.rstep.active');
  if(act && railEl.scrollHeight > railEl.clientHeight + 4){
    const rt = act.offsetTop - railEl.offsetTop, rb = rt + act.offsetHeight;
    if(rt < railEl.scrollTop || rb > railEl.scrollTop + railEl.clientHeight){
      railEl.scrollTo({top: rt - railEl.clientHeight/2 + act.offsetHeight,
                       behavior: STILL ? 'auto' : 'smooth'});
    }
  }
  saveRun();
}

cardEl.addEventListener('click', e=>{
  const b = e.target.closest('.opt[data-br]'); if(!b) return;
  run.aside = b.dataset.br;
  // stay on this step: the consequence of standing aside is worth reading before
  // the run skips three steps on your behalf. "Mark it, next" then advances.
  renderRun();
});
railEl.addEventListener('click', e=>{
  const b = e.target.closest('.rstep'); if(!b) return;
  run.i = +b.dataset.ix; renderRun();
});
document.querySelectorAll('.vbtn').forEach(b=>b.addEventListener('click', ()=>{
  run.view = (run.view===b.dataset.view) ? null : b.dataset.view; renderRun();
}));
document.getElementById('runPrev').addEventListener('click', ()=>{ run.i--; run.view=null; renderRun(); });
document.getElementById('runSkip').addEventListener('click', ()=>{
  run.i = Math.min(STEPS.length-1, run.i+1); run.view=null; renderRun(); });
document.getElementById('runMark').addEventListener('click', ()=>{
  const s = STEPS[run.i];
  if(s.branch && !run.aside){ renderRun(); return; }   // answer the branch first
  run.done[s.id] = true;
  let n = run.i + 1;
  if(run.aside==='aside'){ while(n < STEPS.length && STEPS[n].onlyIfTaken) n++; }
  if(n < STEPS.length){ run.i = n; run.view = null; }
  renderRun();
});
document.getElementById('runReset').addEventListener('click', ()=>{
  run = {i:0, done:{}, view:null, aside:null}; renderRun(); });
renderRun();
