(async function(){
const $=s=>document.querySelector(s);
const usd=n=>n==null?"–":"$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const pct=(n,d=1)=>n==null?"–":(n>0?"+":"")+(n*100).toFixed(d)+"%";
const BANDS=[["Attractive","b-attr","Price at or below the buy-below level (fair value less margin of safety)"],
["Potentially interesting","b-int","Between buy-below and fair value less half the margin of safety"],
["Little margin","b-lit","Below fair value, but with a thin cushion"],["Above estimated value","b-abv","Price is higher than the estimated fair value"]];
function status(a){const p=a.price,fv=a.fair_value;
 if(p<=a.buy_below)return 0;if(p<=fv*(1-a.mos/2))return 1;if(p<=fv)return 2;return 3}
// theme
const root=document.documentElement;try{const t=localStorage.getItem("theme");if(t)root.dataset.theme=t}catch(e){}
$("#theme").onclick=()=>{const dark=getComputedStyle(root).getPropertyValue("--bg").trim()==="#0b1020";const n=dark?"light":"dark";root.dataset.theme=n;try{localStorage.setItem("theme",n)}catch(e){}};
$("#bands").innerHTML=BANDS.map(b=>`<div><span class="badge ${b[1]}">${b[0]}</span><p class="muted">${b[2]}</p></div>`).join("");
let A,P,TH={};
try{[A,P,TH]=await Promise.all([fetch("data/assets.json?"+Date.now()).then(r=>r.json()),fetch("data/prices.json?"+Date.now()).then(r=>r.json()),fetch("data/themes.json?"+Date.now()).then(r=>r.json()).catch(()=>({}))]);delete TH._help}
catch(e){$("main").innerHTML='<div class="err">Could not load data files. Open this page through GitHub Pages (or a local server such as <code>python -m http.server</code>), not by double-clicking the file.</div>';return}
let rows=A.assets.map(a=>{const p=P.prices[a.ticker]||{};const price=p.price;
 const r={...a,price,prev:p.prev_close,history:p.history||[]};
 if(price!=null){r.diff=price/a.fair_value-1;r.status=status(r);r.day=p.prev_close?price/p.prev_close-1:null}return r}).filter(r=>r.price!=null);
$("#stamp").textContent="Prices: "+(P.source||"")+" · updated "+new Date(P.updated).toLocaleString();
$("#sub").textContent=A.model+" · valuations as of "+A.assets.map(a=>a.valued_on).sort().pop();
// KPIs
const n=rows.length,under=rows.filter(r=>r.diff<=0).length,att=rows.filter(r=>r.status<=1).length;
const avg=rows.reduce((s,r)=>s+r.diff,0)/n;const best=[...rows].sort((a,b)=>a.diff-b.diff)[0];
$("#kpis").innerHTML=[["Assets tracked",n,"in data/assets.json"],["Below fair value",`${under} / ${n}`,"price ≤ estimated value"],["Interesting or better",att,"inside the margin-of-safety bands"],
 ["Average price vs FV",pct(avg),"simple average"],["Biggest discount to FV",best.ticker,pct(best.diff)+" vs fair value"]].map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("");
function range(r){const lo=Math.min(r.bear,r.price)*0.9,hi=Math.max(r.bull,r.price)*1.05,x=v=>(v-lo)/(hi-lo)*160+5;
 return `<svg class="rng" viewBox="0 0 170 30"><rect x="5" y="12" width="160" height="6" rx="3" fill="var(--line)"/><rect x="${x(r.bear)}" y="12" width="${x(r.bull)-x(r.bear)}" height="6" rx="3" fill="var(--acc)" opacity=".28"/>
 <rect x="${x(r.fair_value)-1.5}" y="7" width="3" height="16" rx="1.5" fill="var(--acc)"/><circle cx="${x(r.price)}" cy="15" r="5.5" fill="${r.diff<=0?"var(--good)":"var(--bad)"}" stroke="var(--card)" stroke-width="2"/></svg>`}
function spark(h){if(h.length<3)return '<span class="muted">n/a</span>';const mn=Math.min(...h),mx=Math.max(...h),w=90,ht=28;
 const pts=h.map((v,i)=>`${(i/(h.length-1)*w).toFixed(1)},${(ht-2-(v-mn)/(mx-mn||1)*(ht-4)).toFixed(1)}`).join(" ");
 return `<svg width="${w}" height="${ht}"><polyline points="${pts}" fill="none" stroke="${h[h.length-1]>=h[0]?"var(--good)":"var(--bad)"}" stroke-width="1.6"/></svg>`}
let sortK="ticker",dir=1,filt="",theme="All";
const inTheme=r=>theme==="All"||(theme==="Other"?!Object.values(TH).some(l=>l.includes(r.ticker)):(TH[theme]||[]).includes(r.ticker));
const names=["All",...Object.keys(TH).filter(k=>rows.some(r=>TH[k].includes(r.ticker))),...(rows.some(r=>!Object.values(TH).some(l=>l.includes(r.ticker)))?["Other"]:[])];
$("#themechips").innerHTML='<span class="lbl">Group</span>'+names.map(n=>`<button class="chip${n==="All"?" on":""}" data-th="${n}">${n}</button>`).join("");
document.querySelectorAll("#themechips .chip").forEach(c=>c.onclick=()=>{theme=c.dataset.th;document.querySelectorAll("#themechips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
function render(){const f=rows.filter(r=>(r.ticker+r.name).toLowerCase().includes(filt)&&inTheme(r));
 f.sort((a,b)=>{const x=a[sortK],y=b[sortK];return (typeof x==="string"?x.localeCompare(y):(x??1e9)-(y??1e9))*dir});
 $("#tbl tbody").innerHTML=f.map(r=>`<tr data-t="${r.ticker}"><td><div class="tk">${r.ticker}</div><div class="nm">${r.name}</div></td>
 <td class="r num">${usd(r.price)}<div class="nm ${r.day>0?"neg":"pos"}" style="color:var(--mut)">${r.day==null?"":pct(r.day,2)+" today"}</div></td>
 <td class="r num"><b>${usd(r.fair_value)}</b></td><td class="r num">${usd(r.buy_below)}</td>
 <td class="r num ${r.diff>0?"pos":"neg"}"><b>${pct(r.diff)}</b></td><td>${range(r)}<div class="nm">${usd(r.bear).slice(0,-3)} · ${usd(r.base).slice(0,-3)} · ${usd(r.bull).slice(0,-3)}</div></td>
 <td><span class="badge ${BANDS[r.status][1]}">${BANDS[r.status][0]}</span></td><td class="r num">${r.implied_return==null?"–":(r.implied_return*100).toFixed(1)+"%"}</td><td>${spark(r.history)}</td></tr>`).join("")||'<tr><td colspan="9" class="err">No match</td></tr>';
 document.querySelectorAll("tbody tr[data-t]").forEach(tr=>tr.onclick=()=>open(tr.dataset.t))}
document.querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{const k=th.dataset.k;dir=sortK===k?-dir:1;sortK=k;render()});
$("#q").oninput=e=>{filt=e.target.value.toLowerCase();render()};render();
function open(t){const r=rows.find(x=>x.ticker===t);const s=r.scenarios||{};
 const sc=["bear","base","bull"].map(k=>{const v=s[k]||{};const pr=A.probabilities[k];
  const desc=r.type==="stock"?`growth ${(v.g1*100).toFixed(0)}% → ${(v.g10*100).toFixed(1)}%, FCF margin ${(v.m*100).toFixed(1)}%`:r.type==="etf"?`EPS ${v.eps.toFixed(1)}, growth ${(v.g1*100).toFixed(0)}% → ${(v.g10*100).toFixed(1)}%, cash conversion ${(v.conv*100).toFixed(0)}%`:`${v.why}`;
  return `<tr><td style="text-align:left"><b>${k[0].toUpperCase()+k.slice(1)}</b></td><td>${usd(r[k])}</td><td>${r.type==="commodity"?"":(pr*100)+"%"}</td><td style="text-align:left;white-space:normal">${desc}</td></tr>`}).join("");
 let sens="";if(r.sensitivity){sens=`<h3>Sensitivity (base case value per share)</h3><table class="s"><tr><th>Required return ↓ / terminal growth →</th>${r.sensitivity.g.map(g=>`<th>${(g*100).toFixed(1)}%</th>`).join("")}</tr>`+
  r.sensitivity.grid.map((row,i)=>`<tr><th>${(r.sensitivity.r[i]*100).toFixed(1)}%</th>${row.map((v,j)=>`<td class="${i==2&&j==2?"hl":""}">${v.toFixed(0)}</td>`).join("")}</tr>`).join("")+"</table>"}
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 <p><span class="badge ${BANDS[r.status][1]}">${BANDS[r.status][0]}</span></p>
 <div class="grid2"><div class="mini">Price<b>${usd(r.price)}</b></div><div class="mini">Fair value<b>${usd(r.fair_value)}</b></div>
 <div class="mini">Buy below (${(r.mos*100).toFixed(0)}% MoS)<b>${usd(r.buy_below)}</b></div><div class="mini">Price vs fair value<b>${pct(r.diff)}</b></div>
 <div class="mini">No-growth value (EPV)<b>${usd(r.epv)}</b></div><div class="mini">Implied annual return at this price<b>${r.implied_return==null?"–":(r.implied_return*100).toFixed(1)+"%"}</b></div></div>
 <h3>Scenarios</h3><table class="s"><tr><th style="text-align:left">Case</th><th>Value</th><th>Weight</th><th style="text-align:left">Assumptions</th></tr>${sc}</table>
 ${r.reverse_g1!=null?`<h3>What the price implies</h3><p>${r.reverse_g1<0?`At today's price and a ${(r.required_return*100).toFixed(1)}% required return, the market is pricing in year-1 sales <b>shrinking about ${Math.abs(r.reverse_g1*100).toFixed(0)}%</b>, then recovering to the base long-run rate. That is a pessimistic view.`:`To justify today's price at a ${(r.required_return*100).toFixed(1)}% required return, year-1 growth would need to be about <b>${(r.reverse_g1*100).toFixed(0)}%</b> fading to the base long-run rate.`} Terminal value is ${(r.tv_share*100).toFixed(0)}% of the base DCF.</p>`:""}
 ${sens}<h3>Notes</h3><p>${r.notes}</p><p class="muted">Valued ${r.valued_on}. Estimates only, not investment advice. Full step-by-step workbook is in the repo (docs/).</p>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close}
function close(){$("#drawer").classList.remove("on");$("#scrim").classList.remove("on")}
if(location.hash.length>1&&rows.some(r=>r.ticker===location.hash.slice(1).toUpperCase()))open(location.hash.slice(1).toUpperCase());
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
})();
