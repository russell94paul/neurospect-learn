
/* ═══════════════════════════════════════════════════════════════════════════
   TOOLS — arithmetic on the rules already on this page.
   Every tool cites the rule it implements and shows the formula it used. None
   of them asserts an edge, a win rate or an expectancy: where a number would
   have to be measured, the tool asks you for it and says so.
   ═══════════════════════════════════════════════════════════════════════════ */

const CONTRACT = {NQ:20, ES:50, YM:5};      // $ per index point, standard specs
const n = v => (v===''||v==null||isNaN(+v)) ? null : +v;
const money = v => '$' + v.toLocaleString(undefined,{maximumFractionDigits:2});
const pts = v => v.toLocaleString(undefined,{maximumFractionDigits:2});

const TOOLS = {
 size:{
  t:'Position sizer', rules:[39,43,33],
  why:'R39 sizes off <b>total capital — broker plus savings</b>, not the broker balance. That is the trap the rule exists to name; sizing off the broker balance alone silently multiplies your real risk.',
  f:[['cap','Total capital (broker + savings)','number',20000],
     ['pct','Risk per trade %','number',2],
     ['entry','Entry','number',21341.75],
     ['stop','Stop','number',21567.50],
     ['sym','Instrument','select',['NQ','ES','YM']]],
  run:v=>{
    const cap=n(v.cap), pct=n(v.pct), e=n(v.entry), s=n(v.stop), mult=CONTRACT[v.sym]||20;
    if([cap,pct,e,s].some(x=>x===null)) return null;
    const dist=Math.abs(e-s), R=cap*pct/100, per=dist*mult;
    const rows=[['1R — the amount at risk', money(R), `${pct}% of ${money(cap)}`],
      ['Stop distance', pts(dist)+' pts', `|${pts(e)} − ${pts(s)}|`],
      ['Risk per contract', money(per), `${pts(dist)} pts × $${mult}/pt (${v.sym})`],
      ['Size', per>0 ? (R/per).toFixed(2)+' contracts' : '—', 'R ÷ risk per contract']];
    const w=[];
    if(pct<1||pct>2) w.push(`R39 puts per-trade risk at <b>1–2%</b> of total capital. ${pct}% is outside that.`);
    if(per>R) w.push(`One contract risks ${money(per)}, more than your whole 1R of ${money(R)} — R34 says take the same idea on a correlated leg with a tighter stop rather than sizing below one unit.`);
    return {rows,w};
  }},

 rr:{
  t:'R:R and the break-even win rate', rules:[44,32],
  why:'R44: <b>a win rate without its R:R is meaningless.</b> This computes the win rate you would need just to break even — nothing here claims you achieve it.',
  f:[['entry','Entry','number',21341.75],['stop','Stop','number',21567.50],['tgt','Target','number',20727.00],
     ['win','Your win rate % (optional)','number','']],
  run:v=>{
    const e=n(v.entry),s=n(v.stop),t=n(v.tgt);
    if([e,s,t].some(x=>x===null)) return null;
    const risk=Math.abs(e-s), rew=Math.abs(t-e);
    if(!risk) return null;
    const rr=rew/risk, be=1/(1+rr)*100;
    const w=[];
    if((t>e)!==(s<e)) w.push('Target and stop are on the <b>same side</b> of entry. R35 requires the target to lie beyond entry in the bias direction — as written this is not a tradeable plan.');
    if(rr<1) w.push('Below 1:1. R32 notes that entering against the preferred half of a range forces a lower R:R ceiling — check where in the range you are.');
    const rows=[['Risk', pts(risk)+' pts', `|entry − stop|`],
      ['Reward', pts(rew)+' pts', `|target − entry|`],
      ['R:R', rr.toFixed(2)+' : 1', 'reward ÷ risk'],
      ['Break-even win rate', be.toFixed(1)+'%', '1 ÷ (1 + R:R)'],
      ['You need to win', 'more than '+be.toFixed(1)+'%', 'just to break even at this R:R']];
    const wp=n(v.win);
    if(wp!==null && wp>=0 && wp<=100){
      // R44 in full, using YOUR win rate. Assumes wins land at target and losses at
      // stop — state it, because a partial exit breaks the assumption.
      const exp=(wp/100)*rr - (1-wp/100)*1;
      rows.push(['Expectancy at '+wp+'%', (exp>=0?'+':'')+exp.toFixed(3)+'R per trade',
                 '(win% × '+rr.toFixed(2)+'R) − (loss% × 1R)']);
      rows.push(['Verdict', exp>0?'positive — an edge, IF that win rate is real':'negative at this win rate', 'R44']);
      w.push('That expectancy is computed from <b>a win rate you supplied</b>, and assumes every win lands at target and every loss at stop. It is arithmetic, not evidence — <b>no win rate has been established for this model</b>, and a partial exit breaks the assumption.');
    }
    return {rows, w};
  }},

 zone:{
  t:'Where in the range am I?', rules:[5,32],
  why:'Only <b>0, 0.5 and 1</b> exist in this model. The 0.25 / 0.75 quadrants belong to a different framework and are a flagged divergence — this tool will not print them.',
  f:[['hi','Range high','number',21562.25],['lo','Range low','number',20727.00],
     ['px','Price','number',21341.75],['dir','Direction','select',['short','long']]],
  run:v=>{
    const hi=n(v.hi),lo=n(v.lo),px=n(v.px);
    if([hi,lo,px].some(x=>x===null)||hi===lo) return null;
    const f=(px-lo)/(hi-lo);
    const zone = f>0.5 ? 'PREMIUM' : f<0.5 ? 'DISCOUNT' : 'EQUILIBRIUM';
    const good = (v.dir==='short'&&f>0.5)||(v.dir==='long'&&f<0.5);
    const w = good ? [] : [`Entering ${v.dir} from ${zone.toLowerCase()} is the <b>wrong half</b> for that direction. R32: lower the R:R ceiling accordingly — price may retrace to equilibrium and stop you before a larger target.`];
    return {rows:[['Position in range', (f*100).toFixed(1)+'%', '(price − low) ÷ (high − low)'],
      ['Zone', zone, 'below 0.5 discount · above 0.5 premium'],
      ['Equilibrium', pts((hi+lo)/2), 'the 0.5 level'],
      ['Correct half for a '+v.dir+'?', good?'yes':'NO', 'R32']], w};
  }},

 fromhere:{
  t:'Risk from here', rules:[45],
  why:'R45: <b>"free trade" is a lie.</b> Moving to breakeven after price ran 19 of a 20-point target means risking 19 to make 1. Risk is recalculated from the <b>current price</b>, never from entry.',
  f:[['px','Current price','number',21300],['stop','Stop (where it is now)','number',21567.50],
     ['tgt','Target','number',20727.00]],
  run:v=>{
    const p=n(v.px),s=n(v.stop),t=n(v.tgt);
    if([p,s,t].some(x=>x===null)) return null;
    const risk=Math.abs(p-s), rew=Math.abs(t-p);
    if(!risk) return null;
    const rr=rew/risk;
    const w = rr>=1 ? [] : [`<b>${rr.toFixed(2)} : 1 from here.</b> R45's rule of thumb is to maintain at least 1:1 from where price actually is — below that you are risking more than the move still on offer.`];
    return {rows:[['Still at risk', pts(risk)+' pts', '|current − stop|'],
      ['Still on offer', pts(rew)+' pts', '|target − current|'],
      ['Ratio from here', rr.toFixed(2)+' : 1', 'remaining reward ÷ remaining risk'],
      ['At least 1:1 from here?', rr>=1?'yes':'NO', 'R45']], w};
  }},

 stoprange:{
  t:'Is the stop too wide?', rules:[34,33],
  why:'A stop that eats a quarter of the range is a stop that will be hit by ordinary movement inside it. This is the check that flagged the 30 May trade at <b>27%</b>.',
  f:[['hi','Range high','number',21562.25],['lo','Range low','number',20727.00],
     ['entry','Entry','number',21341.75],['stop','Stop','number',21567.50]],
  run:v=>{
    const hi=n(v.hi),lo=n(v.lo),e=n(v.entry),s=n(v.stop);
    if([hi,lo,e,s].some(x=>x===null)||hi===lo) return null;
    const dist=Math.abs(e-s), pct=dist/Math.abs(hi-lo)*100;
    const w = pct>25 ? [`<b>${pct.toFixed(1)}% of the range.</b> Over the declared 25% flag. R34's answer is the same idea on a correlated triad member with a tighter equivalent gap — not automatic, but this is where you consider it.`] : [];
    return {rows:[['Range', pts(Math.abs(hi-lo))+' pts', 'high − low'],
      ['Stop distance', pts(dist)+' pts', '|entry − stop|'],
      ['Stop as share of range', pct.toFixed(1)+'%', 'stop ÷ range'],
      ['Under the 25% flag?', pct<=25?'yes':'NO', 'R34']], w};
  }},

 breakers:{
  t:'Circuit breakers and drawdown', rules:[40,41,42,49],
  why:'R42 contains a computable test most traders never run: <b>if ten straight losses would draw you down more than 20%, your per-trade risk is too high.</b> Losing streaks are not hypothetical.',
  f:[['pct','Risk per trade %','number',2],['daily','Daily stop in R','number',2]],
  run:v=>{
    const p=n(v.pct), d=n(v.daily);
    if([p,d].some(x=>x===null)) return null;
    const ten=(1-Math.pow(1-p/100,10))*100, ten10R=p*10;
    const w=[];
    if(ten>20) w.push(`Ten straight losses at ${p}% compounds to <b>−${ten.toFixed(1)}%</b>. R42: that is above 20%, so per-trade risk is too high. Size <b>down</b> — never up — in a drawdown.`);
    if(d<2||d>3) w.push(`R40 puts the daily stop at <b>2–3R</b>. ${d}R is outside it.`);
    return {rows:[['Losses that end the day', Math.floor(d)+' at 1R each', `${d}R daily stop (R40)`],
      ['Ten straight losses', '−'+ten.toFixed(1)+'%', 'compounded, not 10 × risk%'],
      ['Full-stop drawdown (R41)', '10R = −'+ten10R.toFixed(0)+'%', `10 × ${p}% — stop completely and investigate`],
      ['Also absolute', 'two-loss daily max · 10-minute rule', 'R49']], w};
  }}
};

/* which step reaches for which tool */
const STEP_TOOLS = {PRE:['breakers'], M5:['zone'], M11:['stoprange','rr'],
                    D0:['zone','rr'], SIZE:['size','breakers','rr'], MAN:['fromhere'], EXIT:['fromhere']};

const TS='aura-tools-v1';
let tv={}; try{ tv=JSON.parse(localStorage.getItem(TS)||'{}')||{}; }catch(e){}
const saveTools=()=>{ try{ localStorage.setItem(TS,JSON.stringify(tv)); }catch(e){} };

function toolHTML(key){
  const T=TOOLS[key]; const v=tv[key]||{};
  const fields=T.f.map(([k,label,type,def])=>{
    const val=(v[k]!==undefined&&v[k]!=='')?v[k]:def;
    if(type==='select') return `<label class="tf"><span>${label}</span>
      <select data-t="${key}" data-k="${k}">${def.map(o=>
        `<option${String(val)===o?' selected':''}>${o}</option>`).join('')}</select></label>`;
    return `<label class="tf"><span>${label}</span>
      <input type="number" step="any" data-t="${key}" data-k="${k}" value="${val}"></label>`;
  }).join('');
  return `<div class="tool" data-tool="${key}">
    <div class="toolhd"><h4>${T.t}</h4>${chips(T.rules)}</div>
    <p class="toolwhy">${T.why}</p>
    <div class="tfs">${fields}</div>
    <div class="tout" data-out="${key}"></div></div>`;
}

function runTool(key){
  const T=TOOLS[key], el=document.querySelector(`[data-out="${key}"]`);
  if(!el) return;
  const v={}; T.f.forEach(([k,,type,def])=>{
    const node=document.querySelector(`[data-t="${key}"][data-k="${k}"]`);
    v[k]= node ? node.value : (type==='select'?def[0]:def);
  });
  tv[key]=v; saveTools();
  const r=T.run(v);
  if(!r){ el.innerHTML='<p class="toolempty">Fill every field to compute.</p>'; return; }
  el.innerHTML='<table class="ttab">'+r.rows.map(([k,val,how])=>
    `<tr><td>${k}</td><td class="tv">${val}</td><td class="thow">${how}</td></tr>`).join('')+'</table>'
    + r.w.map(x=>`<p class="toolwarn">${x}</p>`).join('');
}

function mountTools(container, keys){
  if(!container) return;
  container.innerHTML = keys.map(toolHTML).join('');
  keys.forEach(runTool);
}
document.addEventListener('input', e=>{
  const t=e.target.closest('[data-t]'); if(t) runTool(t.dataset.t);
});
document.addEventListener('change', e=>{
  const t=e.target.closest('[data-t]'); if(t) runTool(t.dataset.t);
});

/* the standalone section: every tool, always available */
mountTools(document.getElementById('allTools'), Object.keys(TOOLS));
