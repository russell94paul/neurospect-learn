const t=(await (await fetch('http://127.0.0.1:9337/json/list')).json()).find(x=>x.type==='page');
const ws=new WebSocket(t.webSocketDebuggerUrl); let id=0; const pend=new Map(); const errs=[];
const send=(m,p={})=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p}));});
ws.onmessage=e=>{const m=JSON.parse(e.data);
 if(m.method==='Runtime.exceptionThrown') errs.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);
 if(m.id&&pend.has(m.id)){pend.get(m.id)(m.result);pend.delete(m.id);}};
await new Promise(r=>ws.onopen=r);
await send('Page.enable'); await send('Runtime.enable');
const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true})).result?.value;
await send('Emulation.setDeviceMetricsOverride',{width:1240,height:1000,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:'http://127.0.0.1:8901/aura-protocol.html'}); await new Promise(r=>setTimeout(r,2400));

console.log('tools rendered   :', await ev('document.querySelectorAll("#allTools .tool").length'), '(expect 6)');
console.log('all compute      :', await ev('document.querySelectorAll("#allTools .ttab").length'), 'tables');

console.log('\n— cross-check against numbers the tracker published independently —');
const row = async (tool,i) => ev(`[...document.querySelectorAll('[data-out="${tool}"] .ttab tr')][${i}]?.innerText.replace(/\s+/g,' ')`);
console.log('R:R          ', await row('rr',2),   '   tracker says: 2.7R PLANNED');
console.log('break-even   ', await row('rr',3));
console.log('zone         ', await row('zone',0), '   tracker says: PREMIUM, 0.74 of range');
console.log('stop/range   ', await row('stoprange',2), '   tracker says: 27% of the range, over the 25% flag');
console.log('sizer 1R     ', await row('size',0));
console.log('sizer stop   ', await row('size',1), '   tracker says: risk 225.75 pts');
console.log('breakers 10L ', await row('breakers',1));

console.log('\n— warnings fire when they should —');
console.log('stop>25% warn:', await ev(`!!document.querySelector('[data-out="stoprange"] .toolwarn')`));
console.log('1-contract    :', await ev(`document.querySelector('[data-out="size"] .toolwarn')?.innerText.slice(0,80)`));
const setv = async (tool,k,val)=>ev(`(()=>{const n=document.querySelector('[data-t="${tool}"][data-k="${k}"]');n.value='${val}';n.dispatchEvent(new Event('input',{bubbles:true}));return 1})()`);
await setv('breakers','pct','2.5');
console.log('2.5% risk warn:', await ev(`document.querySelector('[data-out="breakers"] .toolwarn')?.innerText.slice(0,95)`));
await setv('breakers','pct','2');
console.log('2.0% risk warn:', await ev(`document.querySelector('[data-out="breakers"] .toolwarn')?.innerText.slice(0,60) || 'none (correct: 18.3% < 20%)'`));
await setv('zone','dir','long');
console.log('wrong-half warn:', await ev(`document.querySelector('[data-out="zone"] .toolwarn')?.innerText.slice(0,70)`));

console.log('\n— tools appear inside the guided run —');
await ev(`run.i=STEPS.findIndex(s=>s.id==='SIZE'); renderRun();`);
console.log('at SIZE step  :', await ev('document.querySelectorAll("#stepToolBox .tool").length'), 'tools');
await ev(`run.i=STEPS.findIndex(s=>s.id==='M3'); renderRun();`);
console.log('at M3 step    :', await ev('document.querySelectorAll("#stepToolBox .tool").length'), '(expect 0 — no tool for M3)');
console.log('\nscrollWidth   :', await ev('document.documentElement.scrollWidth'), '(viewport 1240)');
console.log('errors        :', errs.length? errs.join('\n') : 'none');
ws.close(); process.exit(0);
