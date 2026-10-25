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
let A,P,TH={},SN={stocks:{}},FH={};
try{[A,P,TH]=await Promise.all([fetch("data/assets.json?"+Date.now()).then(r=>r.json()),fetch("data/prices.json?"+Date.now()).then(r=>r.json()),fetch("data/themes.json?"+Date.now()).then(r=>r.json()).catch(()=>({}))]);delete TH._help;[SN,FH]=await Promise.all([fetch("data/snapshot.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}})),fetch("data/fv_history.json?"+Date.now()).then(r=>r.json()).catch(()=>({}))])}
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
let sortK="ticker",dir=1,filt="",theme="All",pf="all";
const inTheme=r=>theme==="All"||(theme==="Other"?!Object.values(TH).some(l=>l.includes(r.ticker)):(TH[theme]||[]).includes(r.ticker));
const names=["All",...Object.keys(TH).filter(k=>rows.some(r=>TH[k].includes(r.ticker))),...(rows.some(r=>!Object.values(TH).some(l=>l.includes(r.ticker)))?["Other"]:[])];
$("#themechips").innerHTML='<span class="lbl">Group</span>'+names.map(n=>`<button class="chip${n==="All"?" on":""}" data-th="${n}">${n}</button>`).join("");
const PF={all:["All",()=>true],below:["Below fair value",r=>r.diff<=0],int:["Interesting or better",r=>r.status<=1]};
$("#pricechips").innerHTML='<span class="lbl">Price</span>'+Object.entries(PF).map(([k,v])=>`<button class="chip${k==="all"?" on":""}" data-pf="${k}">${v[0]} <span class="cnt">${rows.filter(v[1]).length}</span></button>`).join("");
document.querySelectorAll("#pricechips .chip").forEach(c=>c.onclick=()=>{pf=c.dataset.pf;document.querySelectorAll("#pricechips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
document.querySelectorAll("#themechips .chip").forEach(c=>c.onclick=()=>{theme=c.dataset.th;document.querySelectorAll("#themechips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
function render(){const f=rows.filter(r=>(r.ticker+r.name).toLowerCase().includes(filt)&&inTheme(r)&&PF[pf][1](r));
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
  const addb=r.wacc&&r.rev?(r.wacc.after_tax_interest||0)/r.rev:0;
  const desc=r.type==="stock"?`growth ${(v.g1*100).toFixed(0)}% → ${(v.g10*100).toFixed(1)}%, FCF margin ${(v.m*100).toFixed(1)}%${addb>=0.0005?` (+${(addb*100).toFixed(1)}% interest add-back = ${((v.m+addb)*100).toFixed(1)}% before interest)`:""}`:r.type==="etf"?`EPS ${v.eps.toFixed(1)}, growth ${(v.g1*100).toFixed(0)}% → ${(v.g10*100).toFixed(1)}%, cash conversion ${(v.conv*100).toFixed(0)}%`:`${v.why}`;
  return `<tr><td style="text-align:left"><b>${k[0].toUpperCase()+k.slice(1)}</b></td><td>${usd(r[k])}</td><td>${r.type==="commodity"?"":(pr*100)+"%"}</td><td style="text-align:left;white-space:normal">${desc}</td></tr>`}).join("");
 let mcH="";if(r.mc){const M=r.mc,$f=x=>"$"+(x>=1000?x.toFixed(0):x.toFixed(2)),W=500;
  const T=M.tornado,tl=Math.min(...T.rows.map(o=>Math.min(o.low,o.high)),T.base),th=Math.max(...T.rows.map(o=>Math.max(o.low,o.high)),T.base),TX=x=>235+(x-tl)/(th-tl)*190;
  const torn=`<svg viewBox="0 0 ${W} ${T.rows.length*30+24}" class="mcsvg" role="img" aria-label="Sensitivity of base-case value"><line x1="${TX(T.base)}" x2="${TX(T.base)}" y1="4" y2="${T.rows.length*30+6}" class="mcfv"/>`+
   T.rows.map((o,i)=>{const a=Math.min(o.low,o.high),b=Math.max(o.low,o.high),y=10+i*30,pin=v=>Math.abs(v)<1?(v*100).toFixed(1)+"%":v;
    return `<text x="0" y="${y+13}" class="mct mcl">${o.label.replace(" (+1 / -1 pt)","").replace(" (2% / 3%)","")}${o.choice?" *":""}</text><rect class="mctb" x="${TX(a)}" y="${y+2}" width="${Math.max(2,TX(b)-TX(a))}" height="16" rx="3"><title>${o.label}: ${pin(o.low_in)} → ${$f(o.low)}, ${pin(o.high_in)} → ${$f(o.high)}</title></rect><text x="${TX(a)-4}" y="${y+14}" text-anchor="end" class="mct">${$f(a)}</text><text x="${TX(b)+4}" y="${y+14}" class="mct">${$f(b)}</text>`}).join("")+
   `<text x="${TX(T.base)}" y="${T.rows.length*30+20}" text-anchor="middle" class="mct">base case ${$f(T.base)}</text></svg>`;
  mcH=`<h3>Range of outcomes (Monte Carlo)</h3><div id="mcbox"></div>
  <h3>What moves the value most</h3><p class="muted">Base case with one input moved to its bear and bull value, the others unchanged. * The required return is a choice, shown for comparison.</p>${torn}`}
 let fc="";if(r.forecast){const B=x=>"$"+x.toFixed(1)+"B",pc=x=>(x*100).toFixed(1)+"%",F=r.forecast,w=r.wacc||{},fi=r.fcf_inputs||{};
  const tab=k=>{const d=F[k];return `<div class="fct" data-k="${k}" style="${k==="base"?"":"display:none"}"><div class="scroll"><table class="s"><tr><th style="text-align:left">Year</th><th>Growth</th><th>Revenue</th><th>Cash margin</th><th>Cash flow</th><th>Worth today</th></tr>`+
   d.rows.map(x=>`<tr><td style="text-align:left">${x.t}</td><td>${pc(x.g)}</td><td>${B(x.rev)}</td><td>${pc(x.m)}</td><td>${B(x.fcf)}</td><td title="× ${x.df.toFixed(3)} discount">${B(x.pv)}</td></tr>`).join("")+
   `<tr><td style="text-align:left" colspan="5">10 years of cash flow, in today's money</td><td><b>${B(d.pv_fcf)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">+ value after year 10 (grows 2.5% a year forever: ${B(d.tv)} in year-10 money)</td><td><b>${B(d.pv_tv)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">= value of the business</td><td><b>${B(d.ev)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">${r.net_cash>=0?"+ net cash":"− net debt"}</td><td>${B(Math.abs(r.net_cash))}</td></tr>
   <tr><td style="text-align:left" colspan="5">= value for shareholders ÷ ${r.shares.toFixed(3)}B shares</td><td><b>$${d.per_share.toFixed(2)}</b></td></tr></table></div></div>`};
  fc=`<h3>How the value is built, year by year</h3>
  <p class="muted">Method: free cash flow <b>before interest</b>, discounted at the ${pc(r.required_return)} required return, then net debt subtracted. Starting cash margin ${pc(r.start_margin)} = (FCF $${(+fi.fcf).toFixed(2)}B − stock pay $${(+fi.sbc).toFixed(2)}B + after-tax interest $${(w.after_tax_interest||0).toFixed(2)}B) ÷ revenue $${r.rev.toFixed(2)}B. Growth fades in a straight line from year 1 to year 10; the margin moves to the scenario target over 5 years.${w.wacc?` For reference, WACC would be ${pc(w.wacc)} (${pc(w.equity_weight)} equity at ${pc(w.cost_equity)}, ${pc(w.debt_weight)} debt at ${pc(w.cost_debt)} before ${pc(w.tax)} tax); it isn't used for discounting so that debt never raises the value.`:""}</p>
  <div class="chips fctabs">${["bear","base","bull"].map(k=>`<button class="chip${k==="base"?" on":""}" data-k="${k}">${k[0].toUpperCase()+k.slice(1)} · $${F[k].per_share.toFixed(2)}</button>`).join("")}</div>${["bear","base","bull"].map(tab).join("")}`}
 let rt="";if(r.rate_table){const px=(P.prices[r.ticker]||{}).price;
  rt=`<h3>Fair value at different required returns</h3><p class="muted">${r.required_return_reason?`<b>Why ${(r.required_return*100).toFixed(1)}%:</b> ${r.required_return_reason}`:""}</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Required return</th><th>Fair value</th><th>Buy below</th><th>Price vs fair value</th><th>Base case</th></tr>`+
  r.rate_table.map(x=>{const on=Math.abs(x.r-r.required_return)<1e-9,d=px?px/x.fv-1:null;return`<tr><td style="text-align:left" class="${on?"hl":""}">${(x.r*100).toFixed(1)}%${on?" ⭐ used":""}</td><td class="${on?"hl":""}">$${x.fv.toFixed(2)}</td><td>$${(x.fv*(1-r.mos)).toFixed(2)}</td><td class="${d==null?"":d>0?"down":"up"}">${d==null?"–":(d>0?"+":"")+(d*100).toFixed(0)+"%"}</td><td>$${x.base.toFixed(2)}</td></tr>`}).join("")+
  `</table></div><p class="muted">Same Bear/Base/Bull weights (30/50/20), only the required return changes. A higher hurdle means future cash is worth less today.</p>`}
 let sens="";if(r.sensitivity){sens=`<h3>Sensitivity (base case value per share)</h3><div class="scroll"><table class="s"><tr><th>Required return ↓ / terminal growth →</th>${r.sensitivity.g.map(g=>`<th>${(g*100).toFixed(1)}%</th>`).join("")}</tr>`+
  r.sensitivity.grid.map((row,i)=>`<tr><th>${(r.sensitivity.r[i]*100).toFixed(1)}%</th>${row.map((v,j)=>`<td class="${i==2&&j==2?"hl":""}">${v.toFixed(0)}</td>`).join("")}</tr>`).join("")+"</table></div>"}
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 ${snapHTML(r)}
 <h3>Scenarios</h3><table class="s"><tr><th style="text-align:left">Case</th><th>Value</th><th>Weight</th><th style="text-align:left">Assumptions</th></tr>${sc}</table>
 ${r.reverse_g1!=null?`<h3>What the price implies</h3><p>${r.reverse_g1<0?`At today's price and a ${(r.required_return*100).toFixed(1)}% required return, the market is pricing in year-1 sales <b>shrinking about ${Math.abs(r.reverse_g1*100).toFixed(0)}%</b>, then recovering to the base long-run rate. That is a pessimistic view.`:`To justify today's price at a ${(r.required_return*100).toFixed(1)}% required return, year-1 growth would need to be about <b>${(r.reverse_g1*100).toFixed(0)}%</b> fading to the base long-run rate.`} Terminal value is ${(r.tv_share*100).toFixed(0)}% of the base DCF.</p>`:""}
 ${mcH}${fc}${rt}${sens}<h3>Notes</h3><p>${r.notes}</p><p class="muted">Valued ${r.valued_on}. Estimates only, not investment advice. Full step-by-step workbook is in the repo (docs/).</p>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close;bindSnap();if(r.mc)drawMC(r,{bear:A.probabilities.bear,base:A.probabilities.base,bull:A.probabilities.bull});
 document.querySelectorAll(".fctabs .chip").forEach(b=>b.onclick=()=>{document.querySelectorAll(".fctabs .chip").forEach(x=>x.classList.toggle("on",x===b));document.querySelectorAll(".fct").forEach(t=>t.style.display=t.dataset.k===b.dataset.k?"":"none")})}

// ---------- Monte Carlo section: mixes the three regime distributions with weights w (30/50/20 by default) ----------
const KS=["bear","base","bull"],KN={bear:"Bear",base:"Base",bull:"Bull"};
const cdfQ=(q,x)=>{const n=q.length-1;if(x<=q[0])return 0;if(x>=q[n])return 1;let i=0;while(q[i+1]<x)i++;const d=q[i+1]-q[i];return (i+(d>0?(x-q[i])/d:0))/n};
function mix(Q,w){const tot=KS.reduce((s,k)=>s+w[k],0)||1;const F=x=>KS.reduce((s,k)=>s+w[k]/tot*cdfQ(Q[k],x),0);
 const lo0=Math.min(...KS.map(k=>Q[k][0])),hi0=Math.max(...KS.map(k=>Q[k][Q[k].length-1]));
 const inv=p=>{let a=lo0,b=hi0;for(let i=0;i<60;i++){const m=(a+b)/2;if(F(m)<p)a=m;else b=m}return (a+b)/2};return {F,inv,tot}}
function irrAt(I,m,key){const g=I.price_multiples,L=Math.log(m);let j=0;while(j<g.length-2&&Math.log(g[j+1])<L)j++;
 const t=Math.min(1,Math.max(0,(L-Math.log(g[j]))/(Math.log(g[j+1])-Math.log(g[j]))));const out={};
 KS.forEach(k=>{const a=I[key][k][j],b=I[key][k][j+1];out[k]=a.map((x,i)=>x+(b[i]-x)*t)});return {Q:out,inside:m>=g[0]&&m<=g[g.length-1]}}
function drawMC(r,w){const M=r.mc,box=$("#mcbox");if(!box)return;const px=(P.prices[r.ticker]||{}).price,$f=x=>"$"+(x>=1000?x.toFixed(0):x.toFixed(2));
 const P0=A.probabilities,isDef=KS.every(k=>Math.abs(w[k]-P0[k])<1e-9);
 const Q={};KS.forEach(k=>Q[k]=M.regimes[k].quantiles);const X=mix(Q,w),tot=X.tot,wn=k=>w[k]/tot;
 const fv=KS.reduce((s,k)=>s+wn(k)*r[k],0),med=X.inv(.5),p10=X.inv(.1),pc=p=>X.inv(p);
 const pf=x=>x==null?"–":(x*100).toFixed(0)+"%",rel=x=>px?((x/px-1)>0?"+":"")+((x/px-1)*100).toFixed(0)+"% vs price":"";
 const pAbove=px?1-X.F(px):null,pMos=px?1-X.F(px/(1-r.mos)):null,pHalf=px?X.F(px*.5):null;
 // stacked histogram, 1st-99th percentile of the mixed distribution
 const lo=pc(.01),hi=pc(.99),nb=28,bw=(hi-lo)/nb,bins=KS.map(()=>new Array(nb).fill(0));
 KS.forEach((k,ki)=>{const q=Q[k],n=q.length-1,mass=wn(k)*100/n;for(let i=0;i<n;i++){const a=q[i],b=q[i+1],d=b-a;
  for(let j=0;j<nb;j++){const x0=lo+j*bw,x1=x0+bw;if(d>0){const ov=Math.max(0,Math.min(b,x1)-Math.max(a,x0));bins[ki][j]+=mass*ov/d}else if(a>=x0&&a<x1)bins[ki][j]+=mass}}});
 const W=500,H=170,pl=8,pr=8,pt=34,pb=26,XS=x=>pl+(x-lo)/(hi-lo)*(W-pl-pr),tots=bins[0].map((_,j)=>bins[0][j]+bins[1][j]+bins[2][j]),mx=Math.max(...tots)||1,Y=v=>v/mx*(H-pt-pb);
 const bars=tots.map((tt,j)=>{const x=XS(lo+j*bw)+1,wd=Math.max(1,XS(lo+(j+1)*bw)-XS(lo+j*bw)-2);let y=H-pb,out="";
  KS.forEach((k,ki)=>{const h=Y(bins[ki][j]);if(h>0.05){y-=h;out+=`<rect class="mc-${k}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${wd.toFixed(1)}" height="${h.toFixed(1)}"/>`}});
  return `<g class="mcg"><title>${$f(lo+j*bw)}–${$f(lo+(j+1)*bw)}: ${tt.toFixed(1)}% of runs gave a value in this range (Bear ${bins[0][j].toFixed(1)}%, Base ${bins[1][j].toFixed(1)}%, Bull ${bins[2][j].toFixed(1)}%)</title>${out}</g>`}).join("");
 const mark=(x,lab,cls,row)=>x<lo||x>hi?"":`<line x1="${XS(x)}" x2="${XS(x)}" y1="${row?pt-6:pt-22}" y2="${H-pb}" class="${cls}"/><text x="${Math.min(Math.max(XS(x),60),W-60)}" y="${row?pt-9:pt-25}" text-anchor="middle" class="mct">${lab}</text>`;
 const svg=`<svg viewBox="0 0 ${W} ${H}" class="mcsvg" role="img" aria-label="Distribution of simulated value per share by case"><line x1="${pl}" x2="${W-pr}" y1="${H-pb}" y2="${H-pb}" class="mcax"/>${bars}${mark(fv,(isDef?"Fair value ":"What-if fair value ")+$f(fv),"mcfv",0)}${px?mark(px,"Price "+$f(px),"mcpx",1):""}
  <text x="${pl}" y="${H-8}" class="mct">${$f(lo)}</text><text x="${W-pr}" y="${H-8}" text-anchor="end" class="mct">${$f(hi)}</text><text x="${W/2}" y="${H-8}" text-anchor="middle" class="mct">value per share (1st–99th percentile of runs)</text></svg>`;
 // implied yearly return at the live price
 const I=M.irr,m0=px&&I?px/I.fair_value:null,ir=m0?irrAt(I,m0,"regimes"):null,hr=m0&&I.hold10?irrAt(I,m0,"hold10"):null;
 const RX=ir?mix(ir.Q,w):null,HX=hr?mix(hr.Q,w):null,rq=p=>RX?RX.inv(p):null,hq=p=>HX?HX.inv(p):null,rp=x=>x==null?"–":(x*100).toFixed(1)+"%";
 const rr=r.required_return,rrs=(rr*100).toFixed(1)+"%",pBeat=HX?1-HX.F(rr):RX?1-RX.F(rr):null,pLoss=HX?HX.F(0):null;
 const avg=KS.every(k=>M.regimes[k].mean!=null)?KS.reduce((s,k)=>s+wn(k)*M.regimes[k].mean,0):null;
 // per-case table
 const rows=KS.map(k=>{const q=Q[k],F1=x=>cdfQ(q,x),iq=hr?hr.Q[k]:ir?ir.Q[k]:null;return `<tr><td style="text-align:left"><span class="sw mc-${k}"></span><b>${KN[k]}</b></td><td>${(wn(k)*100).toFixed(0)}%</td><td>${$f(q[50])}</td><td>${$f(q[10])} – ${$f(q[90])}</td><td>${px?pf(1-F1(px)):"–"}</td><td>${iq?rp(iq[10]):"–"}</td></tr>`}).join("");
 const right=fv>=med,P5=[.1,.25,.5,.75,.9];
 box.innerHTML=`<p class="muted">${M.n.toLocaleString()} runs: Bear / Base / Bull in proportion to the weights, each with growth, long-run growth and margin varied together (correlated) and terminal growth around 2.5%. The ${rrs} required return is fixed: it's your choice, not an uncertainty. <b>Values</b> are what the business is worth <b>today</b> at ${rrs}; <b>returns</b> are what you'd earn a year buying at today's price.</p>
 <div class="grid3"><div class="mini">Today's price<b>${px?$f(px):"–"}</b><span class="muted">live</span></div>
 <div class="mini">Median value today<b>${$f(med)}</b><span class="muted">${rel(med)} · the middle run</span></div>
 <div class="mini">Average value today<b>${avg==null?"–":$f(avg)}</b><span class="muted">${avg==null?"":rel(avg)+" · mean of all runs"}</span></div>
 <div class="mini">Downside (10th percentile)<b>${$f(p10)}</b><span class="muted">${rel(p10)}</span></div>
 <div class="mini">Chance value is above price<b class="up">${pf(pAbove)}</b><span class="muted">model-implied</span></div>
 <div class="mini">Chance value is below price<b class="down">${pf(pAbove==null?null:1-pAbove)}</b><span class="muted">below half the price: ${pf(pHalf)}</span></div>
 <div class="mini">Chance of a ${(r.mos*100).toFixed(0)}% margin of safety<b>${pf(pMos)}</b><span class="muted">value ≥ ${px?$f(px/(1-r.mos)):"–"}</span></div>
 <div class="mini">10-year return, median<b>${rp(hq(.5))}</b><span class="muted">a year · beats ${rrs}: ${pf(pBeat)}</span></div>
 <div class="mini">Chance of a loss over 10 years<b class="${pLoss>.1?"down":""}">${pf(pLoss)}</b><span class="muted">yearly return below 0%</span></div></div>
 <div class="wts" title="What-if weights: view only. The official fair value and the main table keep ${KS.map(k=>(P0[k]*100).toFixed(0)).join("/")}.">
  <span class="wl">Odds</span>
  <label class="wk wk-bear"><span class="sw mc-bear"></span>Bear<input type="range" min="0" max="100" step="5" value="${Math.round(wn("bear")*100)}" data-k="bear" aria-label="Bear weight"><b>${Math.round(wn("bear")*100)}%</b></label>
  <span class="wk wk-base"><span class="sw mc-base"></span>Base <b>${Math.round(wn("base")*100)}%</b></span>
  <label class="wk wk-bull"><span class="sw mc-bull"></span>Bull<input type="range" min="0" max="100" step="5" value="${Math.round(wn("bull")*100)}" data-k="bull" aria-label="Bull weight"><b>${Math.round(wn("bull")*100)}%</b></label>
  ${isDef?"":`<button class="wreset" id="wreset" title="Back to the model's ${KS.map(k=>(P0[k]*100).toFixed(0)).join("/")}" aria-label="Reset weights">↺</button>`}</div>
 ${svg}<div class="mcleg">${KS.map(k=>`<span><span class="sw mc-${k}"></span>${KN[k]} ${(wn(k)*100).toFixed(0)}%</span>`).join("")}<span><span class="ln fv"></span>${isDef?"Fair value":"What-if fair value"}</span><span><span class="ln px"></span>Price</span></div>
 <p class="muted"><b>${isDef?"Fair value":"What-if fair value"} ${$f(fv)}, average ${avg==null?"–":$f(avg)}, median ${$f(med)}:</b> fair value weights the three scenario values; the average is the mean of all runs (close to fair value); the median is the middle run. ${Math.abs(fv/med-1)<0.02?"Average and median are close, so outcomes are fairly balanced.":right?"The average sits above the median because a minority of strong (mostly Bull) runs stretch far to the right.":"The average sits below the median because weak (mostly Bear) runs stretch far to the left."} The 10th percentile is a severe but not worst-case simulated value, not a price forecast.</p>
 <div class="scroll"><table class="s" style="margin-top:8px"><tr><th style="text-align:left">Percentile</th><th>10th</th><th>25th</th><th>Median</th><th>75th</th><th>90th</th></tr><tr><td style="text-align:left">Value today, per share</td>${P5.map(p=>`<td>${$f(pc(p))}</td>`).join("")}</tr>
 ${HX?`<tr><td style="text-align:left">Yearly return, 10-year hold</td>${P5.map(p=>`<td>${rp(hq(p))}</td>`).join("")}</tr>`:""}
 ${RX?`<tr><td style="text-align:left">Yearly return, hold for good</td>${P5.map(p=>`<td>${rp(rq(p))}</td>`).join("")}</tr>`:""}</table></div>
 <h3>Where the outcomes come from</h3><p class="muted">The same runs split by case. If the right tail is mostly Bull, the upside depends on the optimistic story coming true.</p>
 <div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th><th>Weight</th><th>Median value today</th><th>10th – 90th</th><th>Above price</th><th>Median 10-yr return</th></tr>${rows}</table></div>
 ${HX||RX?`<h3>Yearly return if you buy at today's price</h3>
 <div class="scroll"><table class="s"><tr><th style="text-align:left">Version</th><th>Median</th><th>10th – 90th</th><th style="text-align:left;white-space:normal">What it assumes</th></tr>
 ${HX?`<tr><td style="text-align:left"><b>10-year hold</b></td><td><b>${rp(hq(.5))}</b></td><td>${rp(hq(.1))} – ${rp(hq(.9))}</td><td style="text-align:left;white-space:normal">You buy at ${$f(px)}, receive 10 years of the business's free cash flow, then sell at the end of year 10 at the price that gives the next buyer ${rrs} (the gap closes in year 10). Can be negative: chance of a loss ${pf(pLoss)}.</td></tr>`:""}
 ${RX?`<tr><td style="text-align:left"><b>Hold for good</b></td><td>${rp(rq(.5))}</td><td>${rp(rq(.1))} – ${rp(rq(.9))}</td><td style="text-align:left;white-space:normal">You never sell: 10 years of cash flow, then cash growing at terminal growth forever. Can't go below about 2.5%, so a low number means "poor return", not "safe".</td></tr>`:""}</table></div>
 <p class="muted"><b>Why the median return can be positive while the median value is below the price:</b> the value is worth-it-at-${rrs} today, not a future price. Paying more than that still earns a positive return, just less than ${rrs}. (A bond paying $10 a year forever is worth $100 at 10%; buy it for $125 and you still earn 8%.)</p>
 <p class="muted"><b>Why "beats ${rrs}" equals "value above price" (${pf(pBeat)} both):</b> in each run, the value falls as the discount rate rises. The return is the rate where value = price, so value at ${rrs} ≥ price exactly when the return ≥ ${rrs}. That holds for both versions here; it would not if the exit were priced differently (say, at a fixed P/E). Free cash flow is counted as yours whether it's paid as dividends, buybacks or kept in the business.${(ir&&!ir.inside)?" Today's price is outside the range stored for this stock, so these figures are clipped.":""}</p>`:""}

 <p class="muted">These probabilities are model-implied: only as good as the assumption ranges. A Sobol (quasi-Monte Carlo) check with ${M.sobol.n.toLocaleString()} points gives a median of ${$f(M.sobol.p50)} vs ${$f(M.p50)} at the model weights (${((M.sobol.p50/M.p50-1)*100).toFixed(1)}% difference), so the estimate is numerically stable. Stable is not the same as right: it can't test whether the assumption ranges themselves are realistic.</p>`;
 box.querySelectorAll(".wts input").forEach(inp=>{const k=inp.dataset.k,o=k==="bear"?"bull":"bear",ov=Math.round(wn(o)*100)/100;
  const cl=()=>Math.min(+inp.value/100,1-ov);
  inp.oninput=()=>{const v=cl();inp.nextElementSibling.textContent=Math.round(v*100)+"%";box.querySelector(".wk-base b").textContent=Math.round((1-v-ov)*100)+"%"};
  inp.onchange=()=>{const v=cl(),nw={};nw[k]=v;nw[o]=ov;nw.base=Math.max(0,1-v-ov);drawMC(r,nw)}});
 const rb=box.querySelector("#wreset");if(rb)rb.onclick=()=>drawMC(r,{bear:P0.bear,base:P0.base,bull:P0.bull})}
// ---------- Snapshot: flags, five quality cards, valuation strip, what to watch, fair value history ----------
const GC={Strong:"g-s",OK:"g-o",Weak:"g-w",Reinvests:"g-n","n/a":"g-n"};
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function spark2(tr){if(!tr||!tr.points||tr.points.length<2)return "";const v=tr.points.map(p=>p[1]),ref=tr.ref,all=ref!=null?[...v,ref]:v,mn=Math.min(...all),mx=Math.max(...all),w=116,h=30,
 X=i=>3+i/(v.length-1)*(w-6),Y=x=>h-4-(x-mn)/((mx-mn)||1)*(h-8);
 return `<svg class="spk" viewBox="0 0 ${w} ${h}" aria-label="${esc(tr.label)}"><title>${esc(tr.label)}: ${tr.points.map(p=>p[0]+" "+p[1]+(tr.unit||"")).join(", ")}${ref!=null?" (cost of capital "+ref+"%)":""}</title>${ref!=null?`<line x1="2" x2="${w-2}" y1="${Y(ref)}" y2="${Y(ref)}" class="spkref"/>`:""}<polyline points="${v.map((x,i)=>X(i).toFixed(1)+","+Y(x).toFixed(1)).join(" ")}" class="spkl"/><circle cx="${X(v.length-1)}" cy="${Y(v[v.length-1])}" r="2.6" class="spkd"/></svg>`}
const pbar=(p,name)=>p==null?"":`<span class="pbar" title="${p}th percentile in ${esc(name||"sector")} (higher = better)"><i style="left:${Math.min(97,Math.max(3,p))}%"></i></span><span class="pct">${p}th</span>`;
function snapHTML(r){const S=(SN.stocks||{})[r.ticker],px=r.price,$f=x=>"$"+(x>=1000?x.toLocaleString("en-US",{maximumFractionDigits:0}):x.toFixed(2));
 // flags (static from the build + live price-based)
 const fl=[...(S?S.flags:[])];
 if(r.diff>0.5)fl.unshift({t:`Price ${(r.diff*100).toFixed(0)}% above fair value`,d:"Even the bull case may not justify today's price; see the valuation strip."});
 if(px<=r.buy_below)fl.unshift({t:"Below buy-below price",d:`Price is under ${$f(r.buy_below)}, the fair value less the ${(r.mos*100).toFixed(0)}% margin of safety.`});
 const flags=fl.length?`<div class="flags">${fl.map(f=>`<details class="flag"><summary>${esc(f.t)}</summary><div>${esc(f.d)}</div></details>`).join("")}</div>`:"";
 // quality cards
 let q="";if(S){const sn=S.valuation.sector_pct.name;
  q=`<div class="snaphd"><b>Business quality</b><span class="muted">Is it a good company? (price not included)</span></div><div class="cards">`+
  S.cards.map((c,i)=>`<button class="qc" data-i="${i}" aria-expanded="false"><span class="qt">${c.title}</span><span class="gr ${GC[c.grade]||"g-n"}"><i></i>${c.grade}</span>
   <span class="qq">${esc(c.question)}</span><span class="qh">${c.headline.map(esc).join(" · ")||"–"}</span>${spark2(c.trend)}</button>`).join("")+`</div><div id="qdet" class="qdet" hidden></div>`;
  window.__snapCards=S.cards.map(c=>`<div class="qdh"><b>${c.title}</b> <span class="gr ${GC[c.grade]||"g-n"}"><i></i>${c.grade}</span> <span class="muted">${esc(c.question)}${c.note?" "+esc(c.note):""}</span></div>
   <div class="scroll"><table class="s qtab"><tr><th style="text-align:left">Metric</th><th>Value</th><th>Grade</th><th style="text-align:left" title="Percentile among ${esc(sn)} companies (or the industry, where the note says so)">vs peers</th></tr>`+
   c.metrics.map(m=>`<tr class="${m.graded?"":"info"}"><td style="text-align:left;white-space:normal">${esc(m.label)}${m.note?`<div class="muted mnote">${esc(m.note)}</div>`:""}</td><td>${esc(m.value)}</td>
    <td>${m.graded?`<span class="gd ${["g-w","g-o","g-s"][m.score]}" title="${["Weak","OK","Strong"][m.score]}"></span>`:`<span class="muted" title="Shown for context, not graded here">info</span>`}</td><td style="text-align:left">${pbar(m.pct,m.grp||sn)}</td></tr>`).join("")+
   `</table></div>${c.trend&&c.trend.points&&c.trend.points.length?`<p class="muted">${esc(c.trend.label)}: ${c.trend.points.map(p=>p[0]+" "+p[1]+(c.trend.unit||"")).join(" · ")}</p>`:""}`)}
 // valuation strip
 const lo=Math.min(r.bear,px,r.buy_below)*0.92,hi=Math.max(r.bull,px)*1.06,X=v=>((v-lo)/(hi-lo)*100).toFixed(2)+"%";
 let pA=null,h10=null;if(r.mc&&r.mc.regimes){const Q={};KS.forEach(k=>Q[k]=r.mc.regimes[k].quantiles);const w={bear:A.probabilities.bear,base:A.probabilities.base,bull:A.probabilities.bull};pA=1-mix(Q,w).F(px);
  if(r.mc.irr&&r.mc.irr.hold10){const hr=irrAt(r.mc.irr,px/r.mc.irr.fair_value,"hold10");h10=mix(hr.Q,w).inv(.5)}}
 const V=S&&S.valuation,L=V&&V.live,live={pe:L&&L.trailing_eps>0?px/L.trailing_eps:V&&V.now.pe,ev_ebitda:L&&L.ebitda>0&&L.shares?(px*L.shares+(L.net_debt||0))/L.ebitda:V&&V.now.ev_ebitda,fcf_yield:L&&L.fcf_ttm&&L.shares?L.fcf_ttm/(px*L.shares)*100:V&&V.now.fcf_yield};
 const mrow=(k,lab,low,unit)=>{const h=V.history[k]||[],now=live[k];if(now==null||!isFinite(now))return "";const vals=h.map(x=>x[1]);const mn=Math.min(...vals,now),mx=Math.max(...vals,now),pos=x=>((x-mn)/((mx-mn)||1)*100).toFixed(1)+"%";
  const hmn=Math.min(...vals),hmx=Math.max(...vals),where=!vals.length?"":now>hmx?"above its range":now<hmn?"below its range":now>hmn+(hmx-hmn)*2/3?"top of its range":now<hmn+(hmx-hmn)/3?"bottom of its range":"middle of its range";
  const cheap=!vals.length?null:low?(now<hmn+(hmx-hmn)/3):(now>hmn+(hmx-hmn)*2/3);const dear=!vals.length?null:low?(now>hmn+(hmx-hmn)*2/3):(now<hmn+(hmx-hmn)/3);
  return `<tr><td style="text-align:left">${lab}</td><td><b>${now.toFixed(1)}${unit}</b></td><td style="text-align:left">${vals.length?`<span class="vr" title="${h.map(x=>x[0]+": "+x[1]+unit).join(", ")}"><span class="vrb" style="left:${pos(hmn)};width:calc(${pos(hmx)} - ${pos(hmn)})"></span><i class="${cheap?"up":dear?"down":""}" style="left:${pos(now)}"></i></span> <span class="muted">${hmn.toFixed(1)}–${hmx.toFixed(1)}${unit} · ${where}</span>`:"–"}</td><td style="text-align:left">${pbar(V.sector_pct[k],V.sector_pct.name)}</td></tr>`};
 const vt=V?`<div class="scroll"><table class="s vtab"><tr><th style="text-align:left">Multiple</th><th>Now</th><th style="text-align:left">vs its own last ${Math.max(...["pe","ev_ebitda","fcf_yield"].map(k=>(V.history[k]||[]).length))} years</th><th style="text-align:left" title="Percentile in the sector; further right = cheaper">vs sector</th></tr>
  ${mrow("pe","P/E",true,"")}${mrow("ev_ebitda","EV / EBITDA",true,"")}${mrow("fcf_yield","FCF yield",false,"%")}</table></div>`:"";
 const val=`<div class="snaphd"><b>Valuation</b><span class="muted">Is it a good price?</span><span class="badge ${BANDS[r.status][1]}" style="margin-left:auto">${BANDS[r.status][0]}</span></div>
 <div class="vstrip"><div class="vbar"><span class="vband" style="left:${X(r.bear)};width:calc(${X(r.bull)} - ${X(r.bear)})"></span><span class="vbb" style="left:${X(r.buy_below)}" title="Buy below ${$f(r.buy_below)}"></span><span class="vfv" style="left:${X(r.fair_value)}"></span><span class="vpx ${r.diff>0?"bad":"good"}" style="left:${X(px)}" title="Price ${$f(px)}"></span></div>
  <div class="vlab"><span style="left:${X(r.bear)}">Bear ${$f(r.bear)}</span><span style="left:${X(r.fair_value)}"><b>FV ${$f(r.fair_value)}</b></span><span style="left:${X(r.bull)}">Bull ${$f(r.bull)}</span></div></div>
 <p class="vline">Price <b>${$f(px)}</b> is <b class="${r.diff>0?"down":"up"}">${Math.abs(r.diff*100).toFixed(0)}% ${r.diff>0?"above":"below"}</b> fair value · buy below ${$f(r.buy_below)} (${(r.mos*100).toFixed(0)}% margin of safety)</p>
 <div class="vstats"><div><span>Chance value > price</span><b>${pA==null?"–":(pA*100).toFixed(0)+"%"}</b></div><div><span>10-yr return (median)</span><b>${h10==null?"–":(h10*100).toFixed(1)+"%"}</b></div>
  <div><span>Growth priced in (year 1)</span><b>${r.reverse_g1==null?"–":(r.reverse_g1>0?"+":"")+(r.reverse_g1*100).toFixed(0)+"%"}</b></div><div><span>No-growth value (EPV)</span><b>${r.epv?$f(r.epv):"–"}</b></div></div>${vt}`;
 // what to watch: the two biggest drivers (not the required return)
 let watch="";if(r.mc&&r.mc.tornado&&r.scenarios&&r.scenarios.base){const b=r.scenarios.base,addb=r.wacc&&r.rev?(r.wacc.after_tax_interest||0)/r.rev:0,pc=x=>(x*100).toFixed(1).replace(".0","")+"%";
  const KEY=l=>l.startsWith("Year-1")?"g1":l.startsWith("Target")?"m":l.startsWith("Long-run")?"g10":l.startsWith("Terminal")?"gt":null;
  const items=r.mc.tornado.rows.filter(o=>!o.choice).slice(0,2).map(o=>{const k=KEY(o.label),base=k==="g1"?b.g1:k==="g10"?b.g10:k==="m"?b.m+addb:0.025;
   const check=k==="g1"?`Each quarter: is revenue growing near ${pc(base)} a year?${r.reverse_g1!=null?` Today's price needs about ${pc(r.reverse_g1)}.`:""}`:k==="m"?`Each quarter: free cash flow minus stock pay${addb>0.0005?" (plus after-tax interest)":""}, as a share of revenue, vs ${pc(base)}.`:k==="g10"?"Yearly: is the market still growing and is the company holding its share?":"Mostly the economy and inflation; little to check quarter to quarter.";
   return `<li><b>${o.label.replace(" (2% / 3%)","")}</b>: base ${pc(base)}. Bear ${pc(o.low_in)} → ${$f(o.low)}, bull ${pc(o.high_in)} → ${$f(o.high)}. <span class="muted">${check}</span></li>`});
  watch=`<div class="snaphd"><b>What to watch</b><span class="muted">The inputs that move the value most</span></div><ul class="watch">${items.join("")}</ul>`}
 // fair value history vs price
 let fh="";const H=(FH[r.ticker]||[]).filter(x=>x&&x.fv!=null),pr=S&&S.prices&&S.prices.length>3?S.prices:null;
 if(pr&&H.length){const pts=[...pr.map(p=>[p[0],p[1]]),["now",px]],last=H[H.length-1],W=500,Hh=150,pl=8,prr=78,pt=10,pb=22;
  const vals=[...pts.map(p=>p[1]),last.bear,last.bull,...H.map(x=>x.fv)],mn=Math.min(...vals)*0.95,mx=Math.max(...vals)*1.04,XX=i=>pl+i/(pts.length-1)*(W-pl-prr),YY=v=>pt+(1-(v-mn)/(mx-mn))*(Hh-pt-pb);
  const idx=d=>{const m=d.slice(0,7);let i=pts.findIndex(p=>p[0]>=m);return i<0?pts.length-1:i};
  const steps=H.map((h,i)=>{const x0=XX(idx(h.date)),x1=i+1<H.length?XX(idx(H[i+1].date)):XX(pts.length-1);return `<line x1="${x0}" x2="${x1}" y1="${YY(h.fv)}" y2="${YY(h.fv)}" class="fhfv"/><circle cx="${x0}" cy="${YY(h.fv)}" r="3" class="fhpt"><title>${h.date}: fair value ${$f(h.fv)} (bear ${$f(h.bear)}, bull ${$f(h.bull)})</title></circle>`}).join("");
  const x0=XX(idx(last.date)),x1=XX(pts.length-1);
  fh=`<div class="snaphd"><b>Fair value over time</b><span class="muted">Price (monthly) vs each recorded valuation</span></div>
  <svg viewBox="0 0 ${W} ${Hh}" class="mcsvg" role="img" aria-label="Price and fair value over time">
   <rect x="${x0}" y="${YY(last.bull)}" width="${Math.max(2,x1-x0)}" height="${YY(last.bear)-YY(last.bull)}" class="fhband"><title>Bear ${$f(last.bear)} to bull ${$f(last.bull)}</title></rect>
   <line x1="${pl}" x2="${W-prr}" y1="${YY(last.fv)}" y2="${YY(last.fv)}" class="fhguide"/>
   <polyline points="${pts.map((p,i)=>XX(i).toFixed(1)+","+YY(p[1]).toFixed(1)).join(" ")}" class="fhpx"/>${steps}
   <circle cx="${XX(pts.length-1)}" cy="${YY(px)}" r="4" class="fhnow"><title>Price now ${$f(px)}</title></circle>
   <text x="${W-prr+6}" y="${YY(px)+4}" class="mct fhtx">Price ${$f(px)}</text><text x="${W-prr+6}" y="${YY(last.fv)+4}" class="mct fhtx">FV ${$f(last.fv)}</text>
   <text x="${pl}" y="${Hh-6}" class="mct">${pts[0][0]}</text><text x="${W-prr}" y="${Hh-6}" text-anchor="end" class="mct">now</text></svg>
  <p class="muted">Line: monthly price. Dashes and dots: fair value at each refresh (${H.length} recorded so far; recording started ${H[0].date}, earlier values used another method). Shaded: bear–bull range of the latest valuation. A fair value that keeps rising with the price supports the thesis; one that falls while the price holds up is a warning.</p>`}
 else if(H.length){fh=`<div class="snaphd"><b>Fair value over time</b></div><p class="muted">${H.map(h=>`${h.date}: ${$f(h.fv)}`).join(" · ")}</p>`}
 return flags+q+val+watch+fh}
function bindSnap(){const det=$("#qdet");if(!det)return;document.querySelectorAll(".qc").forEach(b=>b.onclick=()=>{const open=b.getAttribute("aria-expanded")==="true";
 document.querySelectorAll(".qc").forEach(x=>{x.setAttribute("aria-expanded","false");x.classList.remove("on")});
 if(open){det.hidden=true;return}b.setAttribute("aria-expanded","true");b.classList.add("on");det.innerHTML=window.__snapCards[+b.dataset.i];det.hidden=false})}
function close(){$("#drawer").classList.remove("on");$("#scrim").classList.remove("on")}
if(location.hash.length>1&&rows.some(r=>r.ticker===location.hash.slice(1).toUpperCase()))open(location.hash.slice(1).toUpperCase());
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
})();
