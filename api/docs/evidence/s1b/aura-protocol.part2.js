
/* ── §01 the eight phases — from concepts/mastery/aura/checklist.md ────────*/
const PHASES = [
 {n:0,t:"Pre-market readiness",gate:false,rules:[47,48,54],items:[
  {x:"Slept ~7h, consistent wake time; morning light and movement done; last caffeine before noon NY.",r:[47]},
  {x:"Phone out of the room; Discord, X and Telegram closed on the trading machine.",r:[47]},
  {x:"Circuit breakers written and visible — 2-loss daily max, 2–3R daily stop, the 10-minute rule.",r:[40,49]},
  {x:"I can answer all three: what am I looking for, where, and what would make me stand aside?",r:[48]},
  {x:"Prior session reviewed and today's plan written before price moves.",r:[26,48]}]},

 {n:1,t:"HTF framing — the top-down cascade",gate:true,rules:[27,28,29],items:[
  {x:"HTF ranges marked by the expansive-move method; discount / EQ / premium, no quadrants.",r:[4,5]},
  {x:"Range extremes anchored on SMT-qualified swing points, not just any high or low.",r:[3,8]},
  {x:"Walked the if-then cascade and noted the current cycle chain.",r:[27]},
  {x:"Draw on liquidity noted — refined to the liquidity within a gap, not the gap's boundary.",r:[12,35]},
  {x:"Written both what would confirm the bias and what would invalidate it.",r:[29],gate:true}]},

 {n:2,t:"Confirmation — Sequential SMT",gate:true,rules:[18,19,20],items:[
  {x:"Bias supported by Sequential SMT nested across ≥2 adjacent cycles on the triad.",r:[17,18]},
  {x:"Confirmed by at least one of: cross-cycle nesting, gap-SMT-fill, or candle-level SMT.",r:[20]},
  {x:"Cross-cycle gap-pairing checked.",r:[21]},
  {x:"If the adjacent cycle is missing, a valid Sequential Skip identified instead.",r:[24,25]},
  {x:"I accept this is probabilistic — I am not treating the signal as certain.",r:[19],gate:true}]},

 {n:3,t:"Entry",gate:true,rules:[30,31,32,33,34],items:[
  {x:"On the 5-minute: a confirmed inverse FVG in the bias direction (plain FVG is the fallback).",r:[30]},
  {x:"Preferably a session-cycle Sequential SMT within discount (long) or premium (short) of the LTF range.",r:[30]},
  {x:"On a skip or news-open setup, waited for the 9:30 NY open rather than chasing a pre-9:30 gap.",r:[31]},
  {x:"Premium/discount position checked, and a realistic R:R ceiling set from it.",r:[32]},
  {x:"Stop placed at the invalidation level — the qualifying SMT's high or low.",r:[33]},
  {x:"Stop distance acceptable, or switched to an alternate triad asset with a tighter equivalent gap.",r:[34]},
  {x:"Risk sized at 1–2% of capital, computed in R. Negative visualisation done — the loss is pre-accepted.",r:[39,43,52]},
  {x:"Pre-trade check: does this fit my plan, did I define it in advance, am I trading the market and not my P&L?",r:[50],gate:true}]},

 {n:4,t:"In-trade management",gate:false,rules:[35,45],items:[
  {x:"Expecting price not to run cleanly to target — new ranges and SMT will form on the way.",r:[35]},
  {x:"Risk recalculated from current price, not entry. Holding ≥1:1 from here.",r:[45]},
  {x:"Trailing as structure develops. A move to breakeven is not 'free'.",r:[45]},
  {x:"If the expected trigger never appeared, treated it as invalidation and zoomed out.",r:[29]}]},

 {n:5,t:"Exit",gate:false,rules:[35,36],items:[
  {x:"Exited at plan — HTF-range equilibrium, or held for liquidity in the range's discount or extreme.",r:[36]},
  {x:"Target was the extreme of the timeframe played; multi-level TP only with the Aura Asset.",r:[35,36]},
  {x:"Outcome recorded in R, not dollars.",r:[43]}]},

 {n:6,t:"Circuit breakers — checkable at any moment",gate:true,rules:[40,41,49],items:[
  {x:"Two losses today → stop for the session. No exceptions.",r:[40],gate:true},
  {x:"Daily stop of 2–3R hit → the day is over.",r:[40],gate:true},
  {x:"After any loss: 10 minutes with charts closed, then zoom out to HTF before considering re-entry.",r:[49]},
  {x:"Feeling the urge to get it back? That is the revenge spiral — intervene before the next trade.",r:[50]},
  {x:"Down 10R overall → full stop and investigation before trading again.",r:[41],gate:true}]},

 {n:7,t:"Post-market review",gate:false,rules:[53],items:[
  {x:"Daily 5-minute check: did I follow my plan, what happened if not, one thing to do better.",r:[49]},
  {x:"Journalled the trades and every missed or cancelled setup, with screenshot and emotional state.",r:[53]},
  {x:"Weekly review run on the three questions: more from winners, less on losers, more ideas.",r:[53]},
  {x:"Never miss twice — if I skipped journalling yesterday, I did it today.",r:[53]}]}
];

const LS = 'aura-protocol-v1';
let state = {};
try{ state = JSON.parse(localStorage.getItem(LS)||'{}') || {}; }catch(e){ state = {}; }
function save(){ try{ localStorage.setItem(LS, JSON.stringify(state)); }catch(e){} }

const phasesEl = document.getElementById('phases');
phasesEl.innerHTML = PHASES.map(p=>{
  const items = p.items.map((it,i)=>{
    const id = 'p'+p.n+'i'+i;
    return '<li><input type="checkbox" id="'+id+'" data-k="'+id+'"'+(state[id]?' checked':'')+'>'+
           '<label for="'+id+'">'+md(it.x)+' '+chips(it.r)+
           (it.gate?'<span class="gatetag">hard gate</span>':'')+'</label></li>';
  }).join('');
  return '<div class="ph'+(p.gate?' gate':'')+'" data-p="'+p.n+'">'+
    '<button class="phb" type="button" aria-expanded="false">'+
      '<span class="phi">'+p.n+'</span>'+
      '<span class="pht">'+p.t+'</span>'+
      '<span class="phm" data-m="'+p.n+'">0/'+p.items.length+'</span>'+
      '<span class="meter"><i data-f="'+p.n+'"></i></span>'+
      '<span class="chev"></span>'+
    '</button>'+
    '<div class="phbody"><ul class="items">'+items+'</ul></div></div>';
}).join('');

function refresh(){
  let done=0, tot=0;
  PHASES.forEach(p=>{
    const d = p.items.filter((_,i)=>state['p'+p.n+'i'+i]).length;
    done+=d; tot+=p.items.length;
    document.querySelector('[data-m="'+p.n+'"]').textContent = d+'/'+p.items.length;
    document.querySelector('[data-f="'+p.n+'"]').style.width = (d/p.items.length*100)+'%';
  });
  document.getElementById('tally').textContent = done+' of '+tot+' ticked · kept in this browser only';
}
phasesEl.addEventListener('click', e=>{
  const b = e.target.closest('.phb');
  if(b){ const ph=b.parentElement; const open=ph.classList.toggle('open');
         b.setAttribute('aria-expanded', open?'true':'false'); }
});
phasesEl.addEventListener('change', e=>{
  const c = e.target.closest('input[data-k]'); if(!c) return;
  state[c.dataset.k] = c.checked; save(); refresh();
});
document.getElementById('resetTicks').addEventListener('click', ()=>{
  state = {}; save();
  phasesEl.querySelectorAll('input[data-k]').forEach(c=>c.checked=false);
  refresh();
});
refresh();

/* ── §02 the decision tree ────────────────────────────────────────────────
   Gates and their order are taken verbatim from aura_setup_engine.py's declared
   HARD_GATES list. Soft branches come from its SOFT_BRANCHES list. Neither is
   re-decided here — if the engine changes, this is what has to change with it. */
const ASIDE = (r, why) => ({aside:true, r:r, why:why});
const NODES = {
 start:{q:"Is the HTF swing anchoring your range SMT-qualified across the triad?", r:[3],
   o:[{l:"Yes — the triad confirms it", g:"r6"},
      {l:"No — it is an unqualified swing", w:"provisional by definition", g:ASIDE(3,
        "An unqualified swing is weak and more likely to be swept. It is the load-bearing filter for everything downstream, so a range anchored on one is a range built on sand.")}]},

 r6:{q:"Is that range still live — has any candle CLOSED beyond a boundary?", r:[6],
   o:[{l:"Still live", g:"r7"},
      {l:"A candle closed through it", w:"a wick through is not a break", g:ASIDE(6,
        "The range died at that close. Trading it now is trading a corpse — this was 13 of 21 stand-asides the first time the rules were run over real bars, the single most common reason to do nothing.")}]},

 r7:{q:"Is the SMT driving that range still the current one?", r:[7],
   o:[{l:"Yes, nothing has superseded it", g:"r18"},
      {l:"A later same-cycle or opposing SMT has formed", g:ASIDE(7,
        "A new Sequential SMT plus an expansive move anchors a NEW range. Reframe from that swing point before you look for an entry — you are not standing aside for the day, you are standing aside from a stale frame.")}]},

 r18:{q:"Does the SMT nest across at least two adjacent cycles?", r:[18],
   o:[{l:"Yes — it nests", g:"r30"},
      {l:"No — the adjacent cycle is missing", g:"skip"}]},

 skip:{q:"Is there a valid Sequential Skip instead?", r:[24,25],
   o:[{l:"Yes — a cycle further down confirms it", w:"down-cycle skip", g:"r30", tag:"skip-down"},
      {l:"Yes — same setup on another triad member", w:"cross-asset skip", g:"r30", tag:"skip-cross"},
      {l:"Neither", g:ASIDE(18,
        "Without nesting or a valid skip there is no Sequential SMT, and without one there is no confirmed level. This is the confirmation gate doing its job.")}]},

 r30:{q:"Is there a 5-minute inverse FVG in the bias direction?", r:[30],
   o:[{l:"Yes — a confirmed iFVG", g:"r31", tag:"ifvg"},
      {l:"Only a plain FVG", w:"the stated fallback", g:"r31", tag:"fvg"},
      {l:"Neither", g:ASIDE(30,
        "No entry PD array means no entry. Waiting for one is not missing the trade — the setup has not arrived yet.")}]},

 r31:{q:"Is this a skip or news-open setup before 09:30 New York?", r:[31], soft:true,
   o:[{l:"Not applicable — already past 09:30", g:"r29"},
      {l:"Yes, and I am waiting for the open", w:"the stated preference", g:"r29", tag:"post930"},
      {l:"Yes, and I am taking the pre-9:30 gap", w:"soft rule — a preference, not a gate",
       soft:true, g:"r29", tag:"pre930"}]},

 r29:{q:"Can you define what would invalidate this — is there a stop level?", r:[29],
   o:[{l:"Yes, invalidation is defined", g:"r33"},
      {l:"No", g:ASIDE(29,
        "The framework supplies the next question to ask; it is not a licence to enter without one. If you cannot say what would prove you wrong, you cannot size the risk either.")}]},

 r33:{q:"Is the stop distance acceptable on this asset?", r:[33,34],
   o:[{l:"Yes", g:"r35"},
      {l:"No — too wide here", w:"take it on a correlated triad member", g:"r35", tag:"altasset"}]},

 r35:{q:"Does the target lie beyond entry, in the bias direction?", r:[35],
   o:[{l:"Yes", g:"r32"},
      {l:"No — price has already passed it", g:ASIDE(35,
        "A target behind you is not a target. This gate exists because an absolute-value bug once hid exactly this case and produced confident 0.0R trades.")}]},

 r32:{q:"Where in the range are you entering?", r:[32], soft:true,
   o:[{l:"In discount (long) / premium (short)", w:"the preferred half", g:"ENTRY", tag:"good-zone"},
      {l:"Against it", w:"soft — lower your R:R ceiling", soft:true, g:"ENTRY", tag:"bad-zone"}]}
};

const LEAF = {
 "skip-down":{t:"Sequential Skip — down-cycle", r:[24],
   d:"The adjacent cycle never confirmed, but a cycle further down confirmed the HTF signal directly."},
 "skip-cross":{t:"Sequential Skip — cross-asset", r:[25],
   d:"The bias is set but this asset offered no clean entry, so the same idea is taken on another triad member in the bias direction."},
 "altasset":{t:"Alternate-asset entry, for stop size", r:[34],
   d:"Same idea, different leg — chosen because the primary asset's stop was uncomfortably wide, not because the read changed."},
 "pre930":{t:"Pre-9:30 entry", r:[31], soft:true,
   d:"Taken against the stated preference. R31 is soft and aimed particularly at traders still building consistency — it is a preference you are choosing to override, not a rule you are breaking."},
 "std":{t:"Standard nested-SMT entry", r:[18,30],
   d:"The SMT nested across adjacent cycles and the 5-minute PD array was there. This is the model's base case."}
};

let path = [];
function nodeOf(k){ return NODES[k]; }
function renderTree(){
  const trail = document.getElementById('trail');
  let html = '', cur = 'start', i = 0, tags = [], ended = null;

  for(const choice of path){
    const n = nodeOf(cur); if(!n) break;
    const o = n.o[choice];
    if(o.tag) tags.push(o.tag);
    html += '<div class="step'+((n.soft||o.soft)?' softstep':'')+'">'+
      '<span class="dot">'+(++i)+'</span><div>'+
      '<p class="qz">'+n.q+' '+chips(n.r)+'</p>'+
      '<p class="ans">→ <b>'+o.l+'</b>'+(o.w?' — '+o.w:'')+'</p></div></div>';
    if(typeof o.g === 'object'){ ended = o.g; cur = null; break; }
    cur = o.g;
    if(cur === 'ENTRY'){ cur = null; break; }
  }

  if(ended){
    html += '<div class="step leaf aside"><span class="dot">■</span><div>'+
      '<div class="leafcard standaside"><span class="leafkind">Outcome · this is a result</span>'+
      '<h4>Stand aside '+chip(ended.r)+'</h4><p>'+ended.why+'</p>'+
      '<p style="margin-top:10px">'+md(RULES['51'].t)+'</p></div></div></div>';
  } else if(cur === null && path.length){
    let kind = tags.find(t=>LEAF[t]) || 'std';
    const L = LEAF[kind];
    const mods = tags.filter(t=>LEAF[t] && t!==kind).map(t=>LEAF[t].t);
    const zone = tags.includes('bad-zone') ? ' Entering against the preferred half of the range — R32 says lower the R:R ceiling accordingly.' : '';
    const arr = tags.includes('fvg') ? ' Entry is on a plain FVG, the stated fallback rather than the preferred iFVG.' : '';
    html += '<div class="step leaf"><span class="dot">■</span><div>'+
      '<div class="leafcard"><span class="leafkind">Outcome · entry</span>'+
      '<h4>'+L.t+' '+chips(L.r)+'</h4><p>'+L.d+arr+zone+'</p>'+
      (mods.length?'<p style="margin-top:9px"><b>Also on this path:</b> '+mods.join(' · ')+'</p>':'')+
      '</div></div></div>';
  } else if(cur){
    const n = nodeOf(cur);
    html += '<div class="step'+(n.soft?' softstep':'')+'"><span class="dot">'+(i+1)+'</span><div>'+
      '<p class="qz">'+n.q+' '+chips(n.r)+
        (n.soft?' <span class="gatetag">soft</span>':' <span class="gatetag">hard gate</span>')+'</p>'+
      '<div class="opts">'+n.o.map((o,ix)=>
        '<button class="opt'+(o.soft?' softopt':'')+'" data-c="'+ix+'" type="button">'+o.l+
        (o.w?'<span class="why">'+o.w+'</span>':'')+'</button>').join('')+'</div>'+
      '</div></div>';
  }
  trail.innerHTML = html;

  // highlight the rules now in scope — never tick them
  document.querySelectorAll('.items .rc.hl').forEach(c=>c.classList.remove('hl'));
  const live = new Set();
  let c2='start'; for(const ch of path){ const n=nodeOf(c2); if(!n) break;
    n.r.forEach(r=>live.add(String(r))); const o=n.o[ch];
    if(typeof o.g==='object'||o.g==='ENTRY') break; c2=o.g; }
  if(cur && nodeOf(cur)) nodeOf(cur).r.forEach(r=>live.add(String(r)));
  document.querySelectorAll('.items .rc').forEach(c=>{
    if(live.has(c.dataset.r)) c.classList.add('hl');
  });
}
document.getElementById('trail').addEventListener('click', e=>{
  const b = e.target.closest('.opt'); if(!b) return;
  path.push(+b.dataset.c); renderTree();
});
document.getElementById('treeReset').addEventListener('click', ()=>{ path=[]; renderTree(); });
renderTree();

/* full map — the whole tree, for study rather than execution */
document.getElementById('mapGates').innerHTML = [
 [3,"the swing must be SMT-qualified across the triad"],
 [18,"SMT must nest across ≥2 adjacent cycles, or a valid Sequential Skip (R24/R25)"],
 [6,"the framed range must still be LIVE — a candle CLOSE beyond a boundary kills it"],
 [7,"the driving SMT must still be current — a later same-cycle or opposing SMT retires it"],
 [30,"a 5m iFVG must exist in the bias direction"],
 [35,"the target must lie BEYOND entry in the bias direction"],
 [29,"invalidation must be definable — a stop level must exist"]
].map(([r,d],i)=>'<div class="gaterow"><span class="gl">'+(i+1)+'</span><span>'+chip(r)+' '+d+'</span></div>').join('')
 + '<div class="gaterow"><span class="gl">soft</span><span>'+
   [ [5,"entry in discount / premium — reported, never enforced"],
     [31,"pre-09:30 entry — reported as a branch"],
     [9,"an ambiguous range is left UNRESOLVED, never silently picked"],
     [21,"cross-cycle gap-pairing — supporting confirmation only"],
     [8,"false-sweep tiebreak — UNRESOLVED when the candidates disagree"]
   ].map(([r,d])=>chip(r)+' '+d).join('<br>')+'</span></div>';

document.getElementById('mapLeaves').innerHTML =
  Object.values(LEAF).map(L=>'<div class="gaterow"><span class="gl">entry</span><span><b>'+L.t+
    '</b> '+chips(L.r)+' — '+L.d+'</span></div>').join('') +
  '<div class="gaterow"><span class="gl">outcome</span><span><b>Stand aside</b> '+chip(51)+
  ' — reachable from six of the seven gates, and a result in its own right.</span></div>';

document.getElementById('mapToggle').addEventListener('click', e=>{
  const m = document.getElementById('fullmap');
  m.hidden = !m.hidden;
  e.target.textContent = m.hidden ? 'Show the full map' : 'Hide the full map';
  e.target.setAttribute('aria-expanded', m.hidden?'false':'true');
});

/* ── §04 the card ─────────────────────────────────────────────────────────*/
const TIERS = [
 {n:1,t:"Execution",who:"tz",label:"Tradezella fills this",
  f:["date/session","instrument","entry","exit","stop","size","R multiple","duration"],
  note:"Do not re-type any of this. It comes off the trade itself — copying it by hand only adds a place for the numbers to disagree."},
 {n:2,t:"The read",who:"you",label:"Yours",
  f:["bias (HTF cascade)","cycle chain","range high/low","zone at entry","confirm defined","invalidate defined"],
  note:"The cascade you actually walked. Written before the trade, or it is a reconstruction."},
 {n:3,t:"The signal",who:"you",label:"Yours",
  f:["SMT cycles nested","skip? none / down-cycle / cross-asset","entry PD array (iFVG/FVG)","liquidity inside the gap","target basis"],
  note:"Which of the entry types on this page you actually took — the decision tree's leaf, recorded."},
 {n:4,t:"The psychological layer",who:"you",label:"Yours alone",
  f:["emotion before","emotion during","emotion after","plan followed? Y/N","rule broken + why","urge to re-enter?","grade A+/A/B/C"],
  note:"dOoMeR puts the value here, and no tool can fill it in for you. A card without this tier records what happened but not why you did it."},
 {n:5,t:"Management style",who:"you",label:"Yours",
  f:["MANAGED / SET-AND-LEFT","trailed?","risk-from-here ≥1:1?","trigger failed → zoomed out?"],
  note:"The MANAGED / SET-AND-LEFT tag is what later powers the comparison between actively managing a trade and walking away from it."}
];
document.getElementById('cardTiers').innerHTML = TIERS.map(t=>
 '<div class="tier"><div class="tierhd"><span class="tiern">Tier '+t.n+'</span>'+
 '<span class="tiert">'+t.t+'</span><span class="who '+t.who+'">'+t.label+'</span></div>'+
 '<div class="fields">'+t.f.map(f=>'<span class="fld">'+f+'</span>').join('')+'</div>'+
 '<p class="tiernote">'+t.note+'</p></div>').join('');

document.getElementById('copyCard').addEventListener('click', async ()=>{
  const txt = TIERS.map(t=>'--- Tier '+t.n+' · '+t.t+' ('+t.label+') ---\n'+
      t.f.map(f=>f+': ').join('\n')).join('\n\n');
  try{ await navigator.clipboard.writeText(txt);
       document.getElementById('copyMsg').textContent = 'Copied — paste it into your journal.'; }
  catch(e){ document.getElementById('copyMsg').textContent = 'Clipboard blocked here — select the fields above instead.'; }
  setTimeout(()=>{document.getElementById('copyMsg').textContent='';}, 4000);
});

/* ── reveal — with a non-rAF fallback so a background tab is never blank ───*/
document.querySelectorAll('section, .honesty, figure').forEach(el=>el.classList.add('rv'));
function reveal(el){ el.classList.add('in'); }
if(STILL){
  document.querySelectorAll('.rv').forEach(reveal);
}else{
  const io = new IntersectionObserver((es,o)=>{
    es.forEach(e=>{ if(e.isIntersecting){ reveal(e.target); o.unobserve(e.target); } });
  },{threshold:.12, rootMargin:'0px 0px -6% 0px'});
  document.querySelectorAll('.rv').forEach(el=>io.observe(el));
  const sweep = ()=>document.querySelectorAll('.rv:not(.in)').forEach(el=>{
    if(el.getBoundingClientRect().top < innerHeight) reveal(el);
  });
  addEventListener('scroll', ()=>{ clearTimeout(window._sw);
    window._sw=setTimeout(sweep,90); }, {passive:true});
  setTimeout(()=>document.querySelectorAll('.rv').forEach(reveal), 2600);
}
