import fs from 'node:fs';
const PORT=9333, URL0='http://127.0.0.1:8901/aura-protocol.html';
const t=(await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(x=>x.type==='page');
const ws=new WebSocket(t.webSocketDebuggerUrl); let id=0; const pend=new Map(); const logs=[];
const send=(m,p={})=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p}));});
ws.onmessage=e=>{const m=JSON.parse(e.data);
  if(m.method==='Runtime.exceptionThrown') logs.push('EXCEPTION: '+(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text));
  if(m.method==='Runtime.consoleAPICalled'&&['error','warning'].includes(m.params.type))
    logs.push(m.params.type.toUpperCase()+': '+m.params.args.map(a=>a.value??a.description).join(' '));
  if(m.id&&pend.has(m.id)){pend.get(m.id)(m.result);pend.delete(m.id);}};
await new Promise(r=>ws.onopen=r);
await send('Page.enable'); await send('Runtime.enable'); await send('Log.enable');
const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true})).result?.value;

async function shot(name,w,extra={}){
  await send('Emulation.setDeviceMetricsOverride',{width:w,height:1200,deviceScaleFactor:1,mobile:false,...extra});
  await send('Page.navigate',{url:URL0}); await new Promise(r=>setTimeout(r,2200));
  await ev('document.querySelectorAll(".rv").forEach(e=>e.classList.add("in"))');
  const h=await ev('document.documentElement.scrollHeight');
  await send('Emulation.setDeviceMetricsOverride',{width:w,height:Math.min(h,16000),deviceScaleFactor:1,mobile:false,...extra});
  await new Promise(r=>setTimeout(r,700));
  const d=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
  fs.writeFileSync(`shots/${name}.png`,Buffer.from(d.data,'base64'));
  const sw=await ev('document.documentElement.scrollWidth');
  console.log(`${name}: viewport ${w} · scrollWidth ${sw} · height ${h} ${sw>w+1?'  ⚠ HORIZONTAL OVERFLOW':'· no overflow'}`);
}
await shot('v-1280',1280);
await shot('v-400',400);

// interaction: walk the tree to a STAND ASIDE leaf, then to an entry leaf
await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1200,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:URL0}); await new Promise(r=>setTimeout(r,2000));
console.log('\n— decision tree —');
console.log('nodes at start   :', await ev('document.querySelectorAll("#trail .step").length'));
await ev('document.querySelector("#trail .opt[data-c=\'1\']").click()');   // R3 → No
console.log('after "No" at R3 :', await ev('document.querySelector("#trail .leafcard.standaside h4")?.textContent.trim()'));
await ev('document.getElementById("treeReset").click()');
for(let i=0;i<9;i++){ const ok=await ev('(()=>{const b=document.querySelector("#trail .opt[data-c=\'0\']"); if(b){b.click();return 1} return 0})()'); if(!ok) break; }
console.log('all-yes path ends:', await ev('document.querySelector("#trail .leafcard h4")?.textContent.trim()'));
console.log('steps on path    :', await ev('document.querySelectorAll("#trail .step").length'));
console.log('rules highlighted:', await ev('document.querySelectorAll(".items .rc.hl").length'), '(highlighted, not ticked)');
console.log('boxes auto-ticked:', await ev('document.querySelectorAll(".items input:checked").length'), '(must be 0)');

// checklist persistence
console.log('\n— checklist —');
await ev('document.querySelector("#phases .phb").click(); document.querySelector("#phases input").click()');
console.log('tally after 1 tick:', await ev('document.getElementById("tally").textContent'));
console.log('localStorage key  :', await ev('Object.keys(JSON.parse(localStorage.getItem("aura-protocol-v1")||"{}")).length'), 'entry');
await send('Page.navigate',{url:URL0}); await new Promise(r=>setTimeout(r,1800));
console.log('after reload      :', await ev('document.getElementById("tally").textContent'));
await ev('document.getElementById("resetTicks").click()');
console.log('after clear       :', await ev('document.getElementById("tally").textContent'));

// rule popover
console.log('\n— rule popover —');
await ev('document.querySelector(".items .rc").dispatchEvent(new PointerEvent("pointerover",{bubbles:true}))');
console.log('popover text      :', (await ev('document.querySelector(".pop")?.textContent||""')).slice(0,90).replace(/\s+/g,' '));

console.log('\n— console —');
console.log(logs.length? logs.join('\n') : 'no errors, no warnings');
ws.close(); process.exit(0);
