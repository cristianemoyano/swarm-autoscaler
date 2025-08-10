const rowsEl = document.getElementById('rows');
const svcEl = document.getElementById('svc');
const limitEl = document.getElementById('limit');
const prevBtn = document.getElementById('prev');
const nextBtn = document.getElementById('next');
const pageInfo = document.getElementById('pageInfo');
let currentPage = 1;
let totalPages = 1;
const statusEl = document.getElementById('status');
const chartEl = document.getElementById('chart');
const sortEl = document.getElementById('sort');
const sinceEl = document.getElementById('since');
const untilEl = document.getElementById('until');
const refreshBtn = document.getElementById('refresh');
const clearBtn = document.getElementById('clear');

function setLoadingState(isLoading){
  const ctrls = [svcEl, limitEl, sortEl, sinceEl, untilEl, refreshBtn, clearBtn];
  ctrls.forEach(el => { if(el) el.disabled = isLoading; });
  if(isLoading) statusEl.textContent = 'loading...';
}

function fmtTs(ts){
  const d = new Date(ts*1000);
  return d.toLocaleString();
}

function renderTable(events){
  const sort = document.getElementById('sort').value;
  const list = sort === 'oldest' ? events.slice().reverse() : events.slice();
  rowsEl.innerHTML = list.map(e=>{
    const cls = e.delta>0? 'up' : (e.delta<0? 'down' : '');
    return `<tr>
      <td>${fmtTs(e.ts)}</td>
      <td>${e.service}</td>
      <td>${e.metric || ''}</td>
      <td>${e.old}</td>
      <td>${e.new}</td>
      <td class="${cls}">${e.delta}</td>
      <td class="${cls}">${e.direction}</td>
      <td>${e.reason || ''}</td>
      <td>${e.dryRun ? 'yes' : ''}</td>
    </tr>`;
  }).join('');
}

function renderChart(events){
  const W = chartEl.width = chartEl.clientWidth || 800;
  const H = chartEl.height = 220;
  const ctx = chartEl.getContext('2d');
  ctx.clearRect(0,0,W,H);

  const data = events.slice(-200).reverse(); // chronological
  if(!data.length) return;

  // Group by service and use current replicas (new) as value
  const series = new Map();
  let tMin = Infinity, tMax = -Infinity; let yMin = Infinity, yMax = -Infinity;
  for(const e of data){
    const svc = e.service;
    if(!series.has(svc)) series.set(svc, []);
    const ts = e.ts, y = Number(e.new);
    series.get(svc).push({ts, y});
    if(ts < tMin) tMin = ts; if(ts > tMax) tMax = ts;
    if(y < yMin) yMin = y; if(y > yMax) yMax = y;
  }
  if(!isFinite(tMin) || tMin === tMax) { tMin = tMax - 1; }
  if(!isFinite(yMin) || yMin === yMax) { yMin = yMin-1; yMax = yMax+1; }

  // chart padding
  const PL = 48, PR = 12, PT = 12, PB = 28;
  const PW = W - PL - PR, PH = H - PT - PB;

  // axes
  ctx.strokeStyle = '#ccc'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(PL, PT); ctx.lineTo(PL, PT+PH); ctx.stroke(); // y
  ctx.beginPath(); ctx.moveTo(PL, PT+PH); ctx.lineTo(PL+PW, PT+PH); ctx.stroke(); // x

  // y ticks (min/mid/max)
  const yMid = (yMin + yMax)/2;
  const yTicks = [yMax, yMid, yMin];
  ctx.fillStyle = '#666'; ctx.font = '12px system-ui, sans-serif'; ctx.textAlign = 'right';
  function yToPx(v){ return PT + PH - ((v - yMin)/(yMax - yMin))*PH; }
  for(const v of yTicks){
    const y = yToPx(v);
    ctx.strokeStyle = '#eee'; ctx.beginPath(); ctx.moveTo(PL, y); ctx.lineTo(PL+PW, y); ctx.stroke();
    ctx.fillText(String(Math.round(v)), PL-6, y+1);
  }

  // x labels (first/last time)
  const fmt = ts=> new Date(ts*1000).toLocaleTimeString();
  ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = '#666';
  ctx.fillText(fmt(tMin), PL, PT+PH+6);
  ctx.fillText(fmt(tMax), PL+PW, PT+PH+6);

  // Color palette
  const palette = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf'];
  const svcNames = Array.from(series.keys()).sort();
  const colorOf = s => palette[svcNames.indexOf(s) % palette.length];

  // Plot each service line and collect pixel points for hover
  const seriesPts = [];
  for(const svc of svcNames){
    const pts = series.get(svc).sort((a,b)=>a.ts-b.ts);
    ctx.strokeStyle = colorOf(svc); ctx.lineWidth = 1.8;
    ctx.beginPath();
    const pix = pts.map((p,i)=>{
      const x = PL + ((p.ts - tMin)/(tMax - tMin))*PW;
      const y = yToPx(p.y);
      if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
      return {x,y, ts:p.ts, val:p.y, svc};
    });
    ctx.stroke();
    seriesPts.push({svc, color: colorOf(svc), pts: pix});
  }

  // Legend
  const lh = 16; const boxW = 10; const pad = 6;
  let lx = PL+4, ly = PT+4;
  ctx.font = '12px system-ui, sans-serif'; ctx.textAlign='left'; ctx.textBaseline='middle';
  for(const svc of svcNames){
    ctx.fillStyle = colorOf(svc);
    ctx.fillRect(lx, ly, boxW, boxW);
    ctx.fillStyle = '#333';
    ctx.fillText(svc, lx+boxW+6, ly+boxW/2);
    lx += Math.min(180, ctx.measureText(svc).width + boxW + 28);
    if(lx > PL+PW-160){ lx = PL+4; ly += lh+4; }
  }

  // Save state for hover rendering
  window._chartState = { W,H, PL,PT,PW,PH, tMin,tMax, yMin,yMax, seriesPts };
}

async function populateServices(){
  setLoadingState(true);
  try{
    const res = await fetch('/api/events/services');
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const opts = ['<option value="">(all)</option>'].concat((data.services||[]).map(s=>`<option value="${s}">${s}</option>`));
    svcEl.innerHTML = opts.join('');
  }catch(e){
    console.error('Failed to load services', e);
    statusEl.textContent = 'error loading services';
  } finally {
    setLoadingState(false);
  }
}

async function load(){
  setLoadingState(true);
  try{
    const svc = svcEl.value;
    const limit = parseInt(limitEl.value||'100',10);
    const url = new URL(window.location.origin + '/api/events');
    url.searchParams.set('page_size', String(limit));
    url.searchParams.set('page', String(Math.max(1,currentPage)));
    if(svc) url.searchParams.set('service', svc);
    // datetime-local -> unix seconds
    const toSec = (el)=>{ if(!el || !el.value) return null; const ms = Date.parse(el.value); return isNaN(ms)? null : Math.floor(ms/1000); };
    const s = toSec(sinceEl), u = toSec(untilEl);
    if(s!=null) url.searchParams.set('since', String(s));
    if(u!=null) url.searchParams.set('until', String(u));
    const t0 = performance.now();
    const res = await fetch(url);
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const dt = (performance.now()-t0).toFixed(0);
    statusEl.textContent = `events=${data.events.length}/${data.total}`;
    currentPage = data.page || 1;
    totalPages = Math.max(1, Math.ceil((data.total||0) / (data.page_size||limit)));
    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
    renderTable(data.events);
    window._lastEvents = data.events;
    renderChart(window._lastEvents);
  }catch(e){
    console.error('Failed to load events', e);
    statusEl.textContent = 'error loading events';
  } finally {
    setLoadingState(false);
  }
}

refreshBtn.onclick = load;
clearBtn.onclick = async () => {
  try{
    const svc = svcEl.value.trim();
    const url = new URL(window.location.origin + '/api/events/clear');
    if(svc) url.searchParams.set('service', svc);
    const res = await fetch(url, { method: 'POST' });
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    await load();
  }catch(e){
    console.error('Failed to clear events', e);
    statusEl.textContent = 'error clearing events';
  }
};
// Auto-reload on input changes
[svcEl, sortEl].forEach(el => el.addEventListener('change', load));
[limitEl, sinceEl, untilEl].forEach(el => el.addEventListener('change', load));
setInterval(load, 5000);
populateServices().then(load).catch(()=>load());

prevBtn.addEventListener('click', ()=>{ if(currentPage>1){ currentPage--; load(); }});
nextBtn.addEventListener('click', ()=>{ if(currentPage<totalPages){ currentPage++; load(); }});

// Hover interaction: crosshair + tooltip for nearest point
function redrawWithOverlay(hit){
  if(!window._lastEvents) return;
  renderChart(window._lastEvents);
  if(!hit) return;
  const {x,y, svc, ts, val, color} = hit;
  const ctx = chartEl.getContext('2d');
  // crosshair
  ctx.strokeStyle = '#bbb'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
  ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, chartEl.height); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(chartEl.width, y); ctx.stroke();
  ctx.setLineDash([]);
  // point
  ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2); ctx.fill();
  // tooltip
  const text = `${svc}  |  replicas=${val}  |  ${new Date(ts*1000).toLocaleString()}`;
  ctx.font = '12px system-ui, sans-serif';
  const tw = ctx.measureText(text).width + 16, th = 22;
  let tx = x + 10, ty = y - th - 8;
  if(tx + tw > chartEl.width) tx = x - tw - 10;
  if(ty < 4) ty = y + 12;
  ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.strokeStyle = '#ccc';
  ctx.fillRect(tx, ty, tw, th); ctx.strokeRect(tx, ty, tw, th);
  ctx.fillStyle = '#333'; ctx.textBaseline='middle'; ctx.textAlign='left';
  ctx.fillText(text, tx+8, ty+th/2);
}

function nearestPoint(mx, my){
  const st = window._chartState; if(!st) return null;
  let best=null, bestD=Infinity;
  for(const s of st.seriesPts){
    for(const p of s.pts){
      const dx = p.x - mx, dy = p.y - my; const d = Math.hypot(dx, dy);
      if(d < bestD){ bestD = d; best = {...p, color:s.color}; }
    }
  }
  return bestD <= 20 ? best : null; // 20px snap radius
}

chartEl.addEventListener('mousemove', (e)=>{
  const r = chartEl.getBoundingClientRect();
  const mx = e.clientX - r.left; const my = e.clientY - r.top;
  redrawWithOverlay(nearestPoint(mx,my));
});
chartEl.addEventListener('mouseleave', ()=>{ redrawWithOverlay(null); });


