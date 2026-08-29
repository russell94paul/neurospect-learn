const PORT=9333, URL0='http://127.0.0.1:8901/aura-protocol.html';
const t=(await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(x=>x.type==='page');
const ws=new WebSocket(t.webSocketDebuggerUrl); let id=0; const pend=new Map(); const errs=[];
const send=(m,p={})=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p}));});
ws.onmessage=e=>{const m=JSON.parse(e.data);
 if(m.method==='Runtime.exceptionThrown') errs.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);
 if(m.method==='Runtime.consoleAPICalled'&&['error','warning'].includes(m.params.type))
   errs.push(m.params.type+': '+m.params.args.map(a=>a.value??a.description).join(' '));
 if(m.id&&pend.has(m.id)){pend.get(m.id)(m.result);pend.delete(m.id);}};
await new Promise(r=>ws.onopen=r);
await send('Page.enable'); await send('Runtime.enable');
const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true})).result?.value;
await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:URL0}); await new Promise(r=>setTimeout(r,2400));

console.log('steps in rail   :', await ev('document.querySelectorAll("#rail .rstep").length'));
console.log('phase headings  :', await ev('[...document.querySelectorAll(".railph")].map(e=>e.textContent).join(" · ")'));
console.log('tagged layers   : htf', await ev('document.querySelector(".chart[data-v=htf] svg").querySelectorAll(".mstep").length'),
            '· ltf', await ev('document.querySelector(".chart[data-v=ltf] svg").querySelectorAll(".mstep").length'));

console.log('\n— walking every step —');
let bad=[];
for(let k=0;k<19;k++){
  const row = await ev(`(()=>{
    const c=document.getElementById('stepCard');
    const id=c.querySelector('.sid').textContent;
    const art=c.querySelector('.artpill').textContent;
    const view=document.querySelector('.chart.on').dataset.v;
    const shown=[...document.querySelectorAll('.chart.on .mstep.shown')].map(g=>g.dataset.mi).join(',');
    const prim=!!c.querySelector('.sprim');
    const says=!!c.querySelector('.ssays');
    const gap=!!c.querySelector('.sgap');
    const rules=c.querySelectorAll('.srules .rc').length;
    return JSON.stringify({id,art,view,shown,prim,says,gap,rules});
  })()`);
  const r = JSON.parse(row);
  console.log(` ${String(k+1).padStart(2)} ${r.id.padEnd(5)} ${r.art.padEnd(26)} ${r.view}  shapes[${r.shown||'—'}]  rules:${r.rules}`);
  if(!r.prim) bad.push(r.id+': no primitive');
  if(!r.says) bad.push(r.id+': no session note');
  if(r.art!=='Drawn on the chart' && r.shown && r.shown.split(',').some(x=>0)) {}
  if((r.art==='Not recorded'||r.art==='Unresolved in the rulebook') && !r.gap) bad.push(r.id+': missing why-nothing-appears');
  if(k<18) await ev('document.getElementById("runMark").click()');
}
console.log('\nstructural problems:', bad.length? bad.join(' | ') : 'none');
console.log('marked after walk :', await ev('document.getElementById("runProg").textContent'));
console.log('rail done dots    :', await ev('document.querySelectorAll("#rail .rstep.done").length'));

// persistence
await send('Page.navigate',{url:URL0}); await new Promise(r=>setTimeout(r,1800));
console.log('after reload      :', await ev('document.getElementById("runProg").textContent'));
// view override
await ev('document.querySelector(".vbtn[data-view=htf]").click()');
console.log('view override     :', await ev('document.querySelector(".chart.on").dataset.v'));
await ev('document.getElementById("runReset").click()');
console.log('after reset       :', await ev('document.getElementById("runProg").textContent'),
            '· view', await ev('document.querySelector(".chart.on").dataset.v'),
            '· shapes', await ev('document.querySelectorAll(".chart.on .mstep.shown").length'));
console.log('\nerrors:', errs.length? errs.join('\n') : 'none');
ws.close(); process.exit(0);
