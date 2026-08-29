const PORT=9333, URL0='http://127.0.0.1:8901/aura-protocol.html';
const t=(await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(x=>x.type==='page');
const ws=new WebSocket(t.webSocketDebuggerUrl); let id=0; const pend=new Map();
const send=(m,p={})=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:p}));});
ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m.result);pend.delete(m.id);}};
await new Promise(r=>ws.onopen=r);
await send('Page.enable'); await send('Runtime.enable');
const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true})).result?.value;
await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1200,deviceScaleFactor:1,mobile:false});
async function path(label, seq){
  await send('Page.navigate',{url:URL0}); await new Promise(r=>setTimeout(r,1500));
  for(const i of seq){
    const ok = await ev(`(()=>{const os=[...document.querySelectorAll("#trail .opt")];
      if(!os.length)return 0; os[Math.min(${i},os.length-1)].click(); return 1})()`);
    if(!ok) break;
  }
  // finish with first option until terminal
  for(let k=0;k<14;k++){ const ok=await ev(`(()=>{const os=[...document.querySelectorAll("#trail .opt")];
      if(!os.length)return 0; os[0].click(); return 1})()`); if(!ok) break; }
  console.log(label.padEnd(34), '→', await ev('document.querySelector("#trail .leafcard h4")?.textContent.trim()'));
  const also = await ev('[...document.querySelectorAll("#trail .leafcard p")].map(p=>p.textContent).join(" | ").slice(0,150)');
  console.log('   ', (also||'').replace(/\s+/g,' ').slice(0,140), '\n');
}
await path('skip: down-cycle (R24)',      [0,0,0,1,0]);
await path('skip: cross-asset (R25)',     [0,0,0,1,1]);
await path('alt-asset for stop size R34', [0,0,0,0,0,0,0,1]);
await path('pre-9:30, soft override R31', [0,0,0,0,0,2]);
await path('plain FVG fallback',          [0,0,0,0,1]);
await path('entering against the zone',   [0,0,0,0,0,0,0,0,0,1]);
ws.close(); process.exit(0);
