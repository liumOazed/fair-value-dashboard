const MOATN={wide:"wide moat",narrow:"narrow moat",none:"no moat",short:"short advantage"};
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
let A,P,TH={},SN={stocks:{}},FH={},KP={stocks:{}},KD={stocks:{}},DR0=null,RH={stocks:{}},MS={stocks:{}};
try{[A,P,TH]=await Promise.all([fetch("data/assets.json?"+Date.now()).then(r=>r.json()),fetch("data/prices.json?"+Date.now()).then(r=>r.json()),fetch("data/themes.json?"+Date.now()).then(r=>r.json()).catch(()=>({}))]);delete TH._help;[SN,FH,KP,KD]=await Promise.all([fetch("data/snapshot.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}})),fetch("data/fv_history.json?"+Date.now()).then(r=>r.json()).catch(()=>({})),fetch("data/kpis.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}})),fetch("data/kpi_defs.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}}))]);DR0=await fetch("data/drops.json?"+Date.now()).then(r=>r.ok?r.json():null).catch(()=>null);RH=await fetch("data/returns.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}}));MS=await fetch("data/moat_scorecard.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}}))}
catch(e){$("main").innerHTML='<div class="err">Could not load data files. Open this page through GitHub Pages (or a local server such as <code>python -m http.server</code>), not by double-clicking the file.</div>';return}
let rows=A.assets.map(a=>{const p=P.prices[a.ticker]||{};const price=p.price;
 const r={...a,price,prev:p.prev_close,history:p.history||[]};
 if(price!=null){r.diff=price/a.fair_value-1;r.status=status(r);r.day=p.prev_close?price/p.prev_close-1:null}return r}).filter(r=>r.price!=null);
{const M=P.market||{},ny={timeZone:"America/New_York"},at=new Date(M.as_of||P.updated);
 $("#stamp").textContent=M.state==="open"?"● Market open · latest prices as of "+at.toLocaleTimeString("en-US",{...ny,hour:"numeric",minute:"2-digit"})+" New York time (Yahoo, ~15 min delay)"
  :M.state==="closed"?"Market closed · closing prices of "+at.toLocaleDateString("en-US",{...ny,weekday:"short",month:"short",day:"numeric"})
  :"Prices: "+(P.source||"")+" · updated "+new Date(P.updated).toLocaleString();
 if(M.state==="open")$("#stamp").style.color="var(--good,#1a7f37)"}
$("#sub").textContent=A.model+" · valuations as of "+A.assets.map(a=>a.valued_on).sort().pop();
// KPIs
function kpis(){const n=rows.length,under=rows.filter(r=>r.diff<=0).length,att=rows.filter(r=>r.status<=1).length;
const bb=rows.filter(r=>r.price<=r.buy_below).length,ds=rows.map(r=>r.diff).sort((a,b)=>a-b),med=n%2?ds[(n-1)/2]:(ds[n/2-1]+ds[n/2])/2;const best=[...rows].sort((a,b)=>a.diff-b.diff)[0];
$("#kpis").innerHTML=[["Assets tracked",n,"in data/assets.json"],["Below fair value",`${under} / ${n}`,"price ≤ estimated value"],["Interesting or better",att,"inside the margin-of-safety bands"],
 ["Below buy-below price",`${bb} of ${n}`,"median price vs FV "+pct(med)],["Biggest discount to FV",best.ticker,pct(best.diff)+" vs fair value"]].map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("");}
kpis();
function range(r){const lo=Math.min(r.bear,r.price)*0.9,hi=Math.max(r.bull,r.price)*1.05,x=v=>(v-lo)/(hi-lo)*160+5;
 return `<svg class="rng" viewBox="0 0 170 30"><rect x="5" y="12" width="160" height="6" rx="3" fill="var(--line)"/><rect x="${x(r.bear)}" y="12" width="${x(r.bull)-x(r.bear)}" height="6" rx="3" fill="var(--acc)" opacity=".28"/>
 <rect x="${x(r.fair_value)-1.5}" y="7" width="3" height="16" rx="1.5" fill="var(--acc)"/><circle cx="${x(r.price)}" cy="15" r="5.5" fill="${r.diff<=0?"var(--good)":"var(--bad)"}" stroke="var(--card)" stroke-width="2"/></svg>`}
function spark(h){if(h.length<3)return '<span class="muted">n/a</span>';const mn=Math.min(...h),mx=Math.max(...h),w=90,ht=28;
 const pts=h.map((v,i)=>`${(i/(h.length-1)*w).toFixed(1)},${(ht-2-(v-mn)/(mx-mn||1)*(ht-4)).toFixed(1)}`).join(" ");
 return `<svg width="${w}" height="${ht}"><polyline points="${pts}" fill="none" stroke="${h[h.length-1]>=h[0]?"var(--good)":"var(--bad)"}" stroke-width="1.6"/></svg>`}
let sortK="ticker",dir=1,filt="",theme="All",pf="all",hf="all";
const inTheme=r=>theme==="All"||(theme==="Other"?!Object.values(TH).some(l=>l.includes(r.ticker)):(TH[theme]||[]).includes(r.ticker));
const names=["All",...Object.keys(TH).filter(k=>rows.some(r=>TH[k].includes(r.ticker))),...(rows.some(r=>!Object.values(TH).some(l=>l.includes(r.ticker)))?["Other"]:[])];
$("#themechips").innerHTML='<span class="lbl">Group</span>'+names.map(n=>`<button class="chip${n==="All"?" on":""}" data-th="${n}">${n}</button>`).join("");
const PF={all:["All",()=>true],below:["Below fair value",r=>r.diff<=0],int:["Interesting or better",r=>r.status<=1]};
$("#pricechips").innerHTML='<span class="lbl">Price</span>'+Object.entries(PF).map(([k,v])=>`<button class="chip${k==="all"?" on":""}" data-pf="${k}">${v[0]} <span class="cnt">${rows.filter(v[1]).length}</span></button>`).join("");
document.querySelectorAll("#pricechips .chip").forEach(c=>c.onclick=()=>{pf=c.dataset.pf;document.querySelectorAll("#pricechips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
const HF={all:["All",()=>true],clean:["Passes all 5 checks",r=>!!((SN.stocks||{})[r.ticker]||{}).all_checks]};
$("#healthchips").innerHTML='<span class="lbl">Health</span>'+Object.entries(HF).map(([k,v])=>`<button class="chip${k==="all"?" on":""}" data-hf="${k}"${k==="clean"?' title="Answers yes to all five Growth Screen checks: revenue growing, profits healthy, cash flow strong, debt manageable, financial position improving. Updated monthly."':""}>${v[0]} <span class="cnt">${rows.filter(v[1]).length}</span></button>`).join("");
document.querySelectorAll("#healthchips .chip").forEach(c=>c.onclick=()=>{hf=c.dataset.hf;document.querySelectorAll("#healthchips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
document.querySelectorAll("#themechips .chip").forEach(c=>c.onclick=()=>{theme=c.dataset.th;document.querySelectorAll("#themechips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
function render(){const f=rows.filter(r=>(r.ticker+r.name).toLowerCase().includes(filt)&&inTheme(r)&&PF[pf][1](r)&&HF[hf][1](r));
 f.sort((a,b)=>{const x=a[sortK],y=b[sortK];return (typeof x==="string"?x.localeCompare(y):(x??1e9)-(y??1e9))*dir});
 $("#tbl tbody").innerHTML=f.map(r=>`<tr data-t="${r.ticker}"><td><div class="tk">${r.ticker}</div><div class="nm">${r.name}</div></td>
 <td class="r num">${usd(r.price)}<div class="nm ${r.day>0?"neg":"pos"}" style="color:var(--mut)">${r.day==null?"":pct(r.day,2)+" today"}</div></td>
 <td class="r num"><b>${usd(r.fair_value)}</b></td><td class="r num">${usd(r.buy_below)}</td>
 <td class="r num ${r.diff>0?"pos":"neg"}"><b>${pct(r.diff)}</b></td><td>${range(r)}<div class="nm">${usd(r.bear).slice(0,-3)} · ${usd(r.base).slice(0,-3)} · ${usd(r.bull).slice(0,-3)}</div></td>
 <td><span class="badge ${BANDS[r.status][1]}">${BANDS[r.status][0]}</span></td><td class="r num">${r.implied_return==null?"–":(r.implied_return*100).toFixed(1)+"%"}</td><td class="r num">${r.size==null?"–":r.size>0?`<b>${(r.size*100).toFixed(1)}%</b>`:'<span class="muted">0%</span>'}</td><td>${spark(r.history)}</td></tr>`).join("")||'<tr><td colspan="10" class="err">No match</td></tr>';
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
   `<tr><td style="text-align:left" colspan="5">${d.rows.length} years of cash flow, in today's money</td><td><b>${B(d.pv_fcf)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">+ value after year ${d.rows.length} (grows 2.5% a year forever${d.tv_factor!=null&&Math.abs(d.tv_factor-1)>0.0005?`, cash flow × ${d.tv_factor.toFixed(3)} for the return on new investment`:""}: ${B(d.tv)} in year-${d.rows.length} money)</td><td><b>${B(d.pv_tv)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">= value of the business</td><td><b>${B(d.ev)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">${r.net_cash>=0?"+ net cash":"− net debt"}</td><td>${B(Math.abs(r.net_cash))}</td></tr>
   <tr><td style="text-align:left" colspan="5">= value for shareholders ÷ ${r.shares.toFixed(3)}B shares</td><td><b>$${d.per_share.toFixed(2)}</b></td></tr></table></div></div>`};
  fc=`<h3>How the value is built, year by year</h3>
  <p class="muted">Method: free cash flow <b>before interest</b>, discounted at the ${pc(r.required_return)} required return, then net debt subtracted. Starting cash margin ${pc(r.start_margin)} = (FCF $${(+fi.fcf).toFixed(2)}B − stock pay $${(+fi.sbc).toFixed(2)}B + after-tax interest $${(w.after_tax_interest||0).toFixed(2)}B) ÷ revenue $${r.rev.toFixed(2)}B. Growth fades in a straight line from year 1 to year 10${(r.cap_years||10)>10?`, then from the year-10 rate to 2.5% by year ${r.cap_years} (${MOATN[r.moat]||r.moat}: the advantage period)`:""}; the margin moves to the scenario target over 5 years.${r.moat_note?` ${r.moat_note}`:""}${w.wacc?` For reference, WACC would be ${pc(w.wacc)} (${pc(w.equity_weight)} equity at ${pc(w.cost_equity)}, ${pc(w.debt_weight)} debt at ${pc(w.cost_debt)} before ${pc(w.tax)} tax); it isn't used for discounting so that debt never raises the value.`:""}</p>
  <div class="chips fctabs">${["bear","base","bull"].map(k=>`<button class="chip${k==="base"?" on":""}" data-k="${k}">${k[0].toUpperCase()+k.slice(1)} · $${F[k].per_share.toFixed(2)}</button>`).join("")}</div>${["bear","base","bull"].map(tab).join("")}`}
 let rt="";if(r.rate_table){const px=(P.prices[r.ticker]||{}).price;
  rt=`<h3>Fair value at different required returns</h3><p class="muted">${r.required_return_reason?`<b>Why ${(r.required_return*100).toFixed(1)}%:</b> ${r.required_return_reason}`:""}</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Required return</th><th>Fair value</th><th>Buy below</th><th>Price vs fair value</th><th>Base case</th></tr>`+
  r.rate_table.map(x=>{const on=Math.abs(x.r-r.required_return)<1e-9,d=px?px/x.fv-1:null;return`<tr><td style="text-align:left" class="${on?"hl":""}">${(x.r*100).toFixed(1)}%${on?" ⭐ used":""}</td><td class="${on?"hl":""}">$${x.fv.toFixed(2)}</td><td>$${(x.fv*(1-r.mos)).toFixed(2)}</td><td class="${d==null?"":d>0?"down":"up"}">${d==null?"–":(d>0?"+":"")+(d*100).toFixed(0)+"%"}</td><td>$${x.base.toFixed(2)}</td></tr>`}).join("")+
  `</table></div><p class="muted">Same Bear/Base/Bull weights (30/50/20), only the required return changes. A higher hurdle means future cash is worth less today.</p>`}
 // ---------- advantage period the price implies + is growth paid for? (diagnostics only; fair value unchanged)
 let capH="";if(r.type==="stock"&&(r.implied_cap!==undefined||r.growth_check)){const pc=x=>(x*100).toFixed(0)+"%",rr=(r.required_return*100).toFixed(1)+"%",c=r.implied_cap;
  const capTxt=c==null?`Not meaningful here: base-case growth is at or below the 2.5% long-run rate, so a longer advantage period would not add value.`:
   c<=1?`Today's price needs <b>1 year or less</b> of above-average growth: the price is low even before counting any lasting edge.`:
   c>80?`Today's price needs <b>more than 80 years</b> of above-average growth at our base growth and margin. Duration alone cannot explain it: the market expects higher margins or growth than our base case, or accepts a lower return.`:
   `Today's price needs about <b>${c} years</b> of above-average growth, fading to 2.5%, at our base growth and margin. Our valuation uses ${r.cap_years||10} (${MOATN[r.moat]||"default"}${r.moat_reason?`: ${r.moat_reason.replace(/\.$/,"")}`:""}).`;
  const NOTE={free:"Assumes cash flow at or above after-tax operating profit while growing, so little net reinvestment. Normal for asset-light software and networks; aggressive otherwise.",
   below_hurdle:`Growth earns less than the ${rr} required return, so it adds no value.`,high:"Growth looks close to free (over 50%): check growth and margin together.",shrinking:"Sales shrink, so there is no growth to pay for."};
  const G=r.growth_check,gm=r.nopat_margin;
  const rows=G?["bear","base","bull"].filter(k=>G[k]).map(k=>{const g=G[k],f=g.forecast,t=g.terminal,fx=x=>x==null?"–":x>1?"over 100%":pc(x);
   return `<tr><td style="text-align:left">${k[0].toUpperCase()+k.slice(1)}</td><td class="${g.flag==="below_hurdle"?"down":""}">${fx(f)}</td><td>${fx(t)}</td><td style="text-align:left" class="muted">${g.flag?NOTE[g.flag]:"Plausible."}</td></tr>`}).join(""):"";
  capH=`<h3>How long the edge must last</h3><p>${capTxt}</p>`+(rows?`<p class="muted">Return on new investment each case implies, using after-tax operating margin ${gm!=null?pc(gm):"–"} (latest year, held flat) and reinvestment = operating profit − cash flow. Compare with the ${rr} required return: growth only adds value above it.</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th><th>Forecast years</th><th>After the forecast</th><th style="text-align:left">Reading</th></tr>${rows}</table></div>`:
   (G===null||gm==null?`<p class="muted">Return on new investment not shown: no operating profit figure for this company.</p>`:""))}
 // ---------- growth engines (segments): each segment's own year-1 growth, all fading to the scenario's year-10 rate
 let segH="";if(r.segments&&r.segments.names){const S=r.segments,pc=x=>(x*100).toFixed(1).replace(".0","")+"%";
  segH=`<h3>Growth engines</h3><p class="muted">Revenue is split into the company's reported segments (${S.period}; <a href="${S.source}" target="_blank" rel="noopener">source</a>). Each segment's year-1 growth follows its reported growth relative to the company's (${pc(S.reported)}), capped at twice the company rate, and still adds up to the scenario's year-1 growth. All segments fade to the same year-10 rate, so faster segments gain share and lift growth in years 2-9. One company-wide margin.</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Segment</th><th>Share now</th><th>Bear yr 1</th><th>Base yr 1</th><th>Bull yr 1</th></tr>`+
   S.names.map((n,i)=>`<tr><td style="text-align:left">${n}</td><td>${pc(S.share[i])}</td>${["bear","base","bull"].map(k=>`<td class="${k==="base"?"hl":""}">${pc(S.g1[k][i])}</td>`).join("")}</tr>`).join("")+`</table></div>`}
 let sens="";if(r.sensitivity){sens=`<h3>Sensitivity (base case value per share)</h3><div class="scroll"><table class="s"><tr><th>Required return ↓ / terminal growth →</th>${r.sensitivity.g.map(g=>`<th>${(g*100).toFixed(1)}%</th>`).join("")}</tr>`+
  r.sensitivity.grid.map((row,i)=>`<tr><th>${(r.sensitivity.r[i]*100).toFixed(1)}%</th>${row.map((v,j)=>`<td class="${i==2&&j==2?"hl":""}">${v.toFixed(0)}</td>`).join("")}</tr>`).join("")+"</table></div>"}
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 ${snapHTML(r)}
 <h3>Scenarios</h3><table class="s"><tr><th style="text-align:left">Case</th><th>Value</th><th>Weight</th><th style="text-align:left">Assumptions</th></tr>${sc}</table>
 ${r.reverse_g1!=null?`<h3>What the price implies</h3><p>${r.reverse_g1<0?`At today's price and a ${(r.required_return*100).toFixed(1)}% required return, the market is pricing in year-1 sales <b>shrinking about ${Math.abs(r.reverse_g1*100).toFixed(0)}%</b>, then recovering to the base long-run rate. That is a pessimistic view.`:`To justify today's price at a ${(r.required_return*100).toFixed(1)}% required return, year-1 growth would need to be about <b>${(r.reverse_g1*100).toFixed(0)}%</b> fading to the base long-run rate.`} Terminal value is ${(r.tv_share*100).toFixed(0)}% of the base DCF.</p>`:""}
 ${sizeHTML(r)}${capH}${moatHTML(r)}${retHTML(r)}${segH}${mcH}${fc}${rt}${sens}<h3>Notes</h3><p>${r.notes}</p><p class="muted">Valued ${r.valued_on}. Estimates only, not investment advice. Full step-by-step workbook is in the repo (docs/).</p>`;
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
 const DR=driversData(r.ticker);DR.rows.forEach(x=>{if(x.worse3)fl.push({t:`${x.d.label}: worse 3 quarters running`,d:`Each of the last three quarters moved in the wrong direction (${x.pts.slice(-4).map(p=>p.label+" "+fmtK(x.d,p.value)).join(" → ")}). Check whether the story is changing.`})});
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
 return flags+q+driversHTML(DR)+val+watch+fh}
// ---------- Business drivers (Phase B): company-specific KPIs from quarterly releases, judged against the company's own history
const fmtK=(d,v)=>v==null?"–":d.unit==="text"?String(v):d.unit==="pct"?(+v).toFixed(1).replace(/\.0$/,"")+"%":d.unit==="usd_b"?"$"+(+v).toFixed(v>=100?0:1)+"B":d.unit==="usd"?"$"+(+v).toFixed(2):d.unit==="x"?(+v).toFixed(2)+"×":Math.abs(v)>=1e9?(v/1e9).toFixed(2).replace(/\.?0+$/,"")+"B":Math.abs(v)>=1e6?(v/1e6).toFixed(1)+"M":Math.abs(v)>=1e3?(v/1e3).toFixed(1)+"k":String(v);
function driversData(t){const defs=((KD.stocks||{})[t]||{}).kpis||[],data=(KP.stocks||{})[t]||{};
 const rows=defs.map(d=>{const pts=(data[d.id]||[]).slice().sort((a,b)=>a.period<b.period?-1:1),last=pts[pts.length-1];if(!last)return {d,pts};
  const ly=new Date(last.period);ly.setFullYear(ly.getFullYear()-1);const ya=pts.find(p=>Math.abs(new Date(p.period)-ly)<25*864e5);
  const num=d.unit!=="text";let chg=null,chgTxt="–",base=ya,basis="vs 1y";
  if(num&&!ya&&pts.length>=2){base=pts[pts.length-2];basis="vs prev qtr"}
  if(num&&base){chg=d.unit==="pct"||d.unit==="x"?last.value-base.value:(base.value?last.value/base.value-1:null);
   chgTxt=chg==null?"–":d.unit==="pct"?(chg>0?"+":"")+chg.toFixed(1).replace(/\.0$/,"")+" pts":d.unit==="x"?(chg>0?"+":"")+chg.toFixed(2)+"×":(chg>0?"+":"")+(chg*100).toFixed(0)+"%"}
  const tol=d.unit==="pct"?1:d.unit==="x"?0.05:0.02;let tr=null;
  if(chg!=null){tr=Math.abs(chg)<=tol||d.better==="none"?0:((chg>0)===(d.better==="up")?1:-1)}
  let worse3=false;if(num&&d.better!=="none"&&pts.length>=4){const L=pts.slice(-4).map(p=>p.value);worse3=[1,2,3].every(i=>d.better==="up"?L[i]<L[i-1]:L[i]>L[i-1])}
  return {d,pts,last,chg,chgTxt,basis,tr,worse3}});
 return {rows,latest:rows.filter(x=>x.last).map(x=>x.last).sort((a,b)=>a.period<b.period?1:-1)[0]}}
function sparkK(pts){const v=pts.slice(-8).map(p=>+p.value).filter(x=>isFinite(x));if(v.length<2)return "";const w=90,h=22,mn=Math.min(...v),mx=Math.max(...v),X=i=>2+i/(v.length-1)*(w-4),Y=x=>h-3-(x-mn)/((mx-mn)||1)*(h-6);
 return `<svg class="kspk" viewBox="0 0 ${w} ${h}"><polyline points="${v.map((x,i)=>X(i).toFixed(1)+","+Y(x).toFixed(1)).join(" ")}" class="spkl"/><circle cx="${X(v.length-1)}" cy="${Y(v[v.length-1])}" r="2.4" class="spkd"/></svg>`}
function driversHTML(DR){if(!DR.rows.length)return "";const have=DR.rows.filter(x=>x.last);
 const sc=have.filter(x=>x.tr!=null&&x.d.better!=="none"),up=sc.filter(x=>x.tr>0).length;
 const TR={1:'<span class="up">▲ improving</span>',0:'<span class="muted">● steady</span>',"-1":'<span class="down">▼ worse</span>'};
 const body=DR.rows.map(x=>{const d=x.d;if(!x.last)return `<tr class="info"><td style="text-align:left">${esc(d.label)}</td><td colspan="4" style="text-align:left" class="muted">awaiting data</td></tr>`;
  const tip=`${x.last.label} (${x.last.period}): “${x.last.quote}”`;
  return `<tr><td style="text-align:left;white-space:normal">${esc(d.label)}</td><td title="${esc(tip)}"><b>${esc(fmtK(d,x.last.value))}</b> <a href="${esc(x.last.source)}" target="_blank" rel="noopener" class="src" title="${esc(tip)}">↗</a><div class="muted mnote">${esc(x.last.label)}</div></td>
   <td>${d.unit==="text"?"–":esc(x.chgTxt)}${x.basis!=="vs 1y"&&x.chg!=null?'<div class="muted mnote">vs prev qtr</div>':""}</td><td>${d.unit==="text"?"":sparkK(x.pts)}</td><td>${x.tr==null?'<span class="muted">–</span>':TR[x.tr]}${x.worse3?' <span class="down" title="Worse 3 quarters running">⚠</span>':""}</td></tr>`}).join("");
 return `<div class="snaphd"><b>Business drivers</b><span class="muted">What moves this business · from its quarterly releases${DR.latest?" · latest "+esc(DR.latest.label):""}</span>${sc.length?`<span class="badge" style="margin-left:auto">${up} of ${sc.length} improving</span>`:""}</div>
 ${have.length?"":`<p class="muted">Company KPIs are being collected from the releases; this table fills in over the next days.</p>`}
 <div class="scroll"><table class="s ktab"><tr><th style="text-align:left">KPI</th><th>Latest</th><th title="Change vs the same quarter a year earlier (points for percentages)">vs 1y</th><th>Last 8 qtrs</th><th>Trend</th></tr>${body}</table></div>
 <p class="muted">Judged against the company's own history, not other companies. Hover a value (or open ↗) for the exact quote and filing.</p>`}
function bindSnap(){const det=$("#qdet");if(!det)return;document.querySelectorAll(".qc").forEach(b=>b.onclick=()=>{const open=b.getAttribute("aria-expanded")==="true";
 document.querySelectorAll(".qc").forEach(x=>{x.setAttribute("aria-expanded","false");x.classList.remove("on")});
 if(open){det.hidden=true;return}b.setAttribute("aria-expanded","true");b.classList.add("on");det.innerHTML=window.__snapCards[+b.dataset.i];det.hidden=false})}
function close(){$("#drawer").classList.remove("on");$("#scrim").classList.remove("on")}
// ---------- Price drops: the four-step check ----------
function dropUI(){const D=DR0;if(!D||!(D.open||[]).length&&!(D.log||[]).length)return;
 const al=D.open.filter(e=>e.kind==="alert"),sl=D.open.filter(e=>e.kind!=="alert"),em=al.some(e=>e.emergency);
 const b=document.createElement("button");b.id="dropbtn";b.className="dropbtn"+(em?" em":al.length?" al":"");
 b.innerHTML=al.length?`⚠ ${al.length} price drop${al.length>1?"s":""}${sl.length?` <span class="muted">· ${sl.length} long slides</span>`:""}`:`${sl.length} long slide${sl.length>1?"s":""}`;
 b.title="Stocks that fell sharply: why, is the business still healthy, and is it cheap enough?";
 const head=document.querySelector(".card-head");head.insertBefore(b,$("#stamp"));
 const w=document.createElement("div");w.id="dropwin";w.className="dwin";w.setAttribute("role","dialog");w.setAttribute("aria-label","Price drops");
 w.innerHTML=`<div class="dwin-in"><div class="dwh"><div><h2>Price drops · the four-step check</h2><p class="muted">1 Price fell → 2 Why? → 3 Is the business still healthy? → 4 Is the price low enough for this business? A drop is only an opportunity if the reason is temporary and the business is intact.</p></div><button class="x" id="dwx" aria-label="Close">✕</button></div>
  <div class="dtabs"><button class="on" data-v="al">Sharp drops <span class="cnt">${al.length}</span></button><button data-v="sl">Long slides <span class="cnt">${sl.length}</span></button><button data-v="log">Past drops <span class="cnt">${(D.log||[]).length}</span></button></div>
  <div id="dwbody"></div><p class="muted dfoot">${esc(D.rules||"")} Prices, triggers and evidence update every 30 minutes on GitHub; the “why” verdict is Claude's reading of the news and results (twice a week; the next morning for emergencies). A checklist for research, not advice.</p></div>`;
 document.body.appendChild(w);
 const show=v=>{w.querySelectorAll(".dtabs button").forEach(x=>x.classList.toggle("on",x.dataset.v===v));
  $("#dwbody").innerHTML=v==="log"?dropLog(D.log||[]):(v==="al"?al:sl).map(dropCard).join("")||`<p class="muted" style="padding:16px">None right now.</p>`;
  $("#dwbody").querySelectorAll("[data-open]").forEach(x=>x.onclick=()=>{hideW();open(x.dataset.open)})};
 const hideW=()=>{w.classList.remove("on");$("#scrim").classList.remove("on")};
 b.onclick=()=>{show(al.length?"al":"sl");w.classList.add("on");$("#scrim").classList.add("on")};
 w.querySelectorAll(".dtabs button").forEach(x=>x.onclick=()=>show(x.dataset.v));$("#dwx").onclick=hideW;
 $("#scrim").addEventListener("click",hideW);document.addEventListener("keydown",e=>e.key==="Escape"&&hideW())}
const dot=c=>`<span class="ddot d-${c}"></span>`;
const lvl=v=>v==null?"na":v>=1.45?"g":v>=0.75?"a":"r";
function smet(t,label){const S=(SN.stocks||{})[t];if(!S)return null;for(const c of S.cards||[])for(const m of c.metrics||[])if(m.label.startsWith(label))return m;return null}
function sgrade(t,keys){const ms=keys.map(k=>smet(t,k)).filter(Boolean),sc=ms.filter(m=>m.graded&&m.score!=null).map(m=>m.score);
 return {lv:lvl(sc.length?sc.reduce((a,b)=>a+b,0)/sc.length:null),ms}}
function health(t){const DRV=driversData(t).rows.filter(x=>x.last),worse=DRV.filter(x=>x.worse3||x.tr===-1).length,w3=DRV.filter(x=>x.worse3).length;
 const v=(ms,n=2)=>ms.map(m=>`${m.label.replace(" (YoY)","").replace(" (3 years combined)","")}: <b>${esc(m.value)}</b>`).join(" · ");
 const R=sgrade(t,["Revenue growth, latest quarter","Revenue growth, 3-year CAGR"]),C=sgrade(t,["FCF margin trend","Operating margin trend","FCF / net income"]);
 const B=sgrade(t,["Net debt / EBITDA","Interest coverage"]),M=sgrade(t,["ROIC vs cost of capital","ROIC above cost of capital","Gross margin trend"]);
 let mlv=M.lv;if(w3>=2&&mlv==="g")mlv="a";else if(w3>=2&&mlv==="a")mlv="r";
 return [["Revenue still growing?",R.lv,v(R.ms)],["Profits and cash flow healthy?",C.lv,v(C.ms)],["Debt manageable?",B.lv,v(B.ms)],
  ["Competitive edge intact? (proxies)",mlv,v(M.ms)+(DRV.length?` · business drivers: <b>${DRV.length-worse} of ${DRV.length}</b> not worsening${w3?`, ${w3} worse 3 quarters running`:""}`:"")]]}
function dropCard(e){const r=rows.find(x=>x.ticker===e.ticker);if(!r)return "";const m=e.moves||{},q=e.spy||e.qqq||{},sm=e.sector_moves||{},E=e.evidence||{},V=e.verdict,P0=e.provisional||{};
 const mv=[["today","day"],["5 days","week"],["from 52-wk high","high"]].filter(([,k])=>m[k]!=null);
 const chips=mv.map(([l,k])=>`<span class="mchip${m[k]<=-0.07?" bad":""}" title="S&P 500 (SPY) ${pct(q[k])}${e.sector?` · ${esc(e.sector)} (${esc(e.sector_etf)}, equal-weight) ${pct(sm[k])}`:""}"><b>${pct(m[k])}</b> ${l}<span class="muted"> · S&amp;P ${pct(q[k])}${sm[k]!=null?` · sector ${pct(sm[k])}`:""}</span></span>`).join("");
 // step 2
 const lean=V?V.label:P0.lean||"unclear",LB={temporary:["Looks temporary","g"],lasting:["Looks lasting","r"],unclear:["Unclear","a"]};
 const est=(E.estimates||{})["+1y"],rv=(E.estimates||{}).revisions_30d,pr=(E.peers||{}),pm=pr.median;
 const k=e.triggers.includes("day")?"day":e.triggers.includes("week")?"week":"high";
 const DRV=driversData(e.ticker).rows.filter(x=>x.last),wd=DRV.filter(x=>x.worse3).map(x=>x.d.label);
 const ev=[["Market",`S&amp;P 500 (SPY) ${pct(q[k])} over the same period`],
  ["Sector",e.sector?`${esc(e.sector)} ${pct(sm[k])} (${esc(e.sector_etf)}, equal-weight S&amp;P 500 sector fund)`:"n/a"],
  ["Industry peers",pm?`median ${pct(pm[k])} (${esc(pr.basis)}, ${pr.n} stocks)`:`not enough peers (${esc(pr.basis||"–")})`],
  ["Earnings",E.earnings_on?`reported ${E.earnings_on}: the drop followed the results`:`no report in the week before${E.last_report?" (last: "+E.last_report+")":""}`],
  ["Analyst forecasts",est?`next-year EPS ${pct(est.chg)} in 30 days${rv?` (${rv.up} raised, ${rv.down} cut)`:""}`:"n/a"],
  ["Business drivers",DRV.length?(wd.length?`worse 3 quarters running: ${wd.map(esc).join(", ")}`:"none worse 3 quarters running"):"not collected yet"]];
 const news=(E.news||[]).slice(0,5).map(n=>`<li><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a> <span class="muted">${esc(n.publisher||"")} · ${esc(n.date)}</span></li>`).join("");
 const s2=V?`<b>${LB[lean][0]}</b> · ${esc(V.cause)}<div class="dsum">${esc(V.summary)}</div><div class="muted mnote">Claude's read, ${esc(V.date)}, ${esc(V.confidence)} confidence${V.model_changed?" · fair value updated for it":""}</div>`
  :`<b>${LB[lean][0]}</b> <span class="muted">(first read from the data)</span> · ${esc(P0.cause||"")}<div class="muted mnote">Claude's reading of the news and results: ${e.emergency?"tomorrow morning (emergency drop)":"next review (Tue / Fri)"}</div>`;
 // step 3
 const H=health(e.ticker),reds=H.filter(h=>h[1]==="r").length,l3=reds?"r":H.some(h=>h[1]==="a")?"a":H.every(h=>h[1]==="na")?"na":"g";
 // step 4
 const below=r.price<=r.fair_value,l4=r.price<=r.buy_below?"g":below?"a":"r";
 const base=(r.scenarios||{}).base||{},stale=lean==="lasting"&&!(V&&V.model_changed);
 const s4=`Price ${usd(r.price)} vs fair value <b>${usd(r.fair_value)}</b> (${pct(r.diff)}) and buy-below ${usd(r.buy_below)}.`+
  (r.implied_return!=null?` Expected return at this price <b>${(r.implied_return*100).toFixed(1)}%</b> a year vs ${(r.required_return*100).toFixed(1)}% required.`:"")+
  (r.reverse_g1!=null&&base.g1!=null?` Today's price assumes about <b>${(r.reverse_g1*100).toFixed(0)}%</b> growth next year; our base case has ${(base.g1*100).toFixed(0)}%.`:"")+
  (stale?` <span class="down">The fair value (from ${esc(r.valued_on)}) does not yet reflect this setback, so it is probably too high.</span>`:"");
 // overall
 const ov=lean==="lasting"||reds>=2?["Value-trap risk","r"]:lean==="temporary"&&reds===0&&below?["Worth a look","g"]:["Wait for clarity","a"];
 const step=(n,lv,q,a,more)=>`<div class="dstep"><div class="dnum d-${lv}">${n}</div><div class="dbody"><div class="dq">${q}</div><div class="da">${a}</div>${more?`<details><summary>Evidence</summary>${more}</details>`:""}</div></div>`;
 return `<article class="dcard${e.emergency?" em":""}"><div class="dtop"><div><button class="dtk" data-open="${e.ticker}">${e.ticker}</button> <span class="muted">${esc(r.name)}</span>${e.emergency?' <span class="emtag">Emergency drop</span>':""}
  <div class="mchips">${chips}</div></div><div class="dverdict d-${ov[1]}">${ov[0]}${V?"":'<span class="mnote">provisional</span>'}</div></div>
  ${step(1,"x","Price fell",(()=>{const L={day:"today",week:"in 5 trading days",high:"below its 52-week high"},v=m[k],qq=q[k];
   const since=r.price/e.price_at_open-1;
   return `${k==="high"?`${pct(v,0).replace("-","")} ${L[k]}`:`Down ${pct(v).replace("-","")} ${L[k]}`}, ${Math.abs((v-(qq||0))*100).toFixed(0)} points worse than the S&amp;P 500${sm[k]!=null?` and ${Math.abs((v-sm[k])*100).toFixed(0)} points ${v<=sm[k]?"worse":"better"} than its sector (${esc(e.sector)})`:""}.`+
    ` Flagged ${esc(e.opened)} at ${usd(e.price_at_open)}${Math.abs(since)>=0.005?`; ${pct(since)} since`:""}.`})())}
  ${step(2,LB[lean][1],"Why did it fall?",s2,`<ul class="dev">${ev.map(x=>`<li><span class="muted">${x[0]}</span> ${x[1]}</li>`).join("")}</ul>${news?`<div class="muted mnote">Headlines (past week)</div><ul class="dnews">${news}</ul>`:""}`)}
  ${step(3,l3,"Is the business still healthy?",H.map(h=>`<div class="hrow">${dot(h[1])}<span>${h[0]}</span></div>`).join(""),H.map(h=>`<div class="hrow">${dot(h[1])}<span>${h[2]||"no data"}</span></div>`).join(""))}
  ${step(4,l4,"Is the price low enough for this business?",s4)}</article>`}
function dropLog(L){if(!L.length)return `<p class="muted" style="padding:16px">Closed drops (30 days after the last trigger) land here with the stock's return vs the S&amp;P 500 and vs its sector 30 and 90 days later, so the four-step check can be judged over time.</p>`;
 const f=(o,k)=>o&&o[k]!=null?`<span class="${o[k]>=0?"up":"down"}">${pct(o[k])}</span>`:"–";
 return `<div class="scroll"><table class="s"><tr><th style="text-align:left">Stock</th><th>Dropped</th><th>Verdict</th><th>30 days vs S&amp;P · sector</th><th>90 days vs S&amp;P · sector</th></tr>${L.map(e=>`<tr><td style="text-align:left"><button class="dtk" data-open="${e.ticker}">${e.ticker}</button></td><td>${esc(e.opened)}</td><td>${e.verdict?esc(e.verdict.label):"–"}</td><td>${f(e.outcome.d30,"vs_spy")} · ${f(e.outcome.d30,"vs_sector")}</td><td>${f(e.outcome.d90,"vs_spy")} · ${f(e.outcome.d90,"vs_sector")}</td></tr>`).join("")}</table></div>`}
// ---------- My settings: personal hurdle (question 7) and position sizing (question 6). Kept in this browser only.
const MY0={h:null,max:0.10,eq:0.35};let MY={...MY0};try{MY={...MY0,...JSON.parse(localStorage.getItem("my")||"{}")}}catch(e){}
rows.forEach(r=>{r.fv0=r.fair_value;r.bb0=r.buy_below});
const pc1=x=>(x*100).toFixed(1).replace(".0","")+"%";
function hurdleOf(r){return MY.h==null?r.required_return:MY.h}
function applyHurdle(){rows.forEach(r=>{let fv=r.fv0;
  if(MY.h!=null&&r.rate_table){const x=r.rate_table.find(x=>Math.abs(x.r-MY.h)<1e-9);if(x)fv=x.fv}
  r.fair_value=fv;r.buy_below=MY.h!=null&&r.rate_table?fv*(1-r.mos):r.bb0;r.diff=r.price/fv-1;r.status=status(r)})}
// Yearly return from buying at today's price and holding (Monte Carlo, Bear/Base/Bull 30/50/20): median, p10, p90
function retDist(r){const M=r.mc;if(!M||!M.irr||r.price==null)return null;const I=M.irr,m=r.price/I.fair_value,ir=irrAt(I,m,"regimes"),X=mix(ir.Q,A.probabilities);
  return {med:X.inv(.5),p10:X.inv(.1),p90:X.inv(.9),inside:ir.inside,F:X.F}}
// Size = max position x edge x confidence. Edge = median yearly return above your hurdle, full at +5 points (FULL_EDGE).
// Confidence = chance the return beats your hurdle, 0 at 50% rising to 1 at 90%. Zero when the price is above fair value
// at your hurdle; if all sizes add up to more than your stock share, all scale down in proportion.
const FULL_EDGE=0.05;
function sizeAll(){const raw={};rows.forEach(r=>{r.sz=null;r.size=null;if(r.type!=="stock"&&r.type!=="etf")return;const d=retDist(r);if(!d)return;
  const h=hurdleOf(r),ex=d.med-h,pb=1-d.F(h),edge=Math.min(1,Math.max(0,ex/FULL_EDGE)),conf=Math.min(1,Math.max(0,(pb-0.5)/0.4)),k=r.diff<0?MY.max*edge*conf:0;
  r.sz={d,h,ex,pb,edge,conf,k};raw[r.ticker]=k});
  const tot=Object.values(raw).reduce((a,b)=>a+b,0),sc=tot>MY.eq?MY.eq/tot:1;
  rows.forEach(r=>{if(raw[r.ticker]!=null){r.size=raw[r.ticker]*sc;r.sz.scale=sc}});
  return {tot:tot*sc,n:Object.values(raw).filter(x=>x>0).length,scaled:sc<1}}
// Moat scorecard (scripts/moat_scorecard.py): question 4. Never changes the class in data/moat.json.
function moatHTML(r){const x=(MS.stocks||{})[r.ticker];if(r.type!=="stock"||!x)return "";
 const N={n:"Network effects",s:"Switching costs",i:"Brand, patents, licences",c:"Cost advantage",e:"Efficient scale"},L=["none","some","strong"];
 const dots=v=>`<span class="mdots">${[0,1].map(i=>`<i class="${i<v?"on":""}"></i>`).join("")}</span> ${L[v]}`;
 const P=x.parts||{},pp=(v,m)=>v==null?"–":`${(+v).toFixed(1).replace(".0","")} / ${m}`;
 const verdict=x.differs?`The scorecard suggests <b>${MOATN[x.suggested]}</b>, but the model uses <b>${MOATN[x.current]}</b>. That's worth a look; edit data/moat.json to change it, which moves the fair value.`:`This agrees with the model's ${MOATN[x.current]||x.current}.`;
 return `<h3>How durable is the edge?</h3><p><b>${x.total.toFixed(1)} / 10</b>: ${x.source_score.toFixed(1)} from the sources of advantage, ${x.numbers_score==null?"2.5 (neutral, the filings can't measure it)":x.numbers_score.toFixed(1)} from the filings. ${verdict}</p>
 <div class="scroll"><table class="s rq"><tr><th style="text-align:left">Source of advantage</th><th style="text-align:left">Strength</th></tr>${Object.keys(N).map(k=>`<tr><td style="text-align:left">${N[k]}</td><td style="text-align:left">${dots(x.sources[k])}</td></tr>`).join("")}
 <tr><td style="text-align:left">Main evidence</td><td style="text-align:left">${x.why}${x.src?` (<a href="${x.src}" target="_blank" rel="noopener">source</a>)`:""}</td></tr>
 <tr><td style="text-align:left">Main threat</td><td style="text-align:left">${x.risk}</td></tr></table></div>
 ${x.numbers_score!=null?`<p class="muted">From the filings: returns well above the hurdle in past years ${pp(P.persistence,2)}, no fade ${pp(P.fade,1)}, returns on new money ${pp(P.new_money,1)}, steady gross margin ${pp(P.margins,1)}${P.gm_std!=null?` (typical swing ${(P.gm_std*100).toFixed(1)} pts)`:""}.</p>`:""}
 <p class="muted">The sources are Claude's judgement as of ${MS.checked}, re-checked after each earnings report. 7.5+ suggests a wide moat, 5+ narrow.</p>`}
// Returns on capital over ~10 years of 10-Ks (scripts/returns_history.py): questions 1, 2 and 5. Diagnostics only.
function retHTML(r){const x=(RH.stocks||{})[r.ticker];if(r.type!=="stock"||!x)return "";
 const p0=v=>v==null?"–":v>1?"over 100%":(v*100).toFixed(0)+"%",hr=(x.r*100).toFixed(1)+"%";
 const head=`<h3>Returns on new money</h3>`;
 if(x.note)return head+`<p>${x.note}</p>`;
 const W=520,H=120,pl=34,pr=10,pt=10,pb=20,ys=x.roic.map(p=>p[0]),vs=x.roic.map(p=>p[1]*100),mx=Math.max(...vs,x.r*100)*1.08,mn=Math.min(0,...vs),
  X=y=>pl+(y-ys[0])/((ys[ys.length-1]-ys[0])||1)*(W-pl-pr),Y=v=>pt+(mx-v)/((mx-mn)||1)*(H-pt-pb),tk=[mn,(mn+mx)/2,mx].map(v=>Math.round(v));
 const sp=`<svg viewBox="0 0 ${W} ${H}" class="mcsvg" role="img" aria-label="Return on invested capital by year"><title>${x.roic.map(p=>p[0]+": "+(p[1]*100).toFixed(0)+"%").join(", ")}</title>`+
  tk.map(v=>`<text x="${pl-4}" y="${Y(v)+3}" text-anchor="end" class="rtx">${v}%</text>`).join("")+
  `<line x1="${pl}" x2="${W-pr}" y1="${Y(x.r*100)}" y2="${Y(x.r*100)}" class="spkref"/><text x="${W-pr}" y="${Y(x.r*100)-3}" text-anchor="end" class="rtx">hurdle ${hr}</text>`+
  `<polyline points="${x.roic.map(p=>X(p[0]).toFixed(1)+","+Y(p[1]*100).toFixed(1)).join(" ")}" class="spkl"/>`+
  x.roic.map(p=>`<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]*100).toFixed(1)}" r="2.4" class="spkd"/>`).join("")+
  [ys[0],ys[ys.length-1]].map((y,i)=>`<text x="${X(y)}" y="${H-5}" text-anchor="${i?"end":"start"}" class="rtx">${y}</text>`).join("")+`</svg>`;
 const q1={"holding up":`New money is still earning about as much as the old: <b>${p0(x.inc_recent)}</b> on the capital added in ${x.windows[1]}${x.inc_earlier!=null?` (${p0(x.inc_earlier)} in ${x.windows[0]})`:""}, against ${p0(x.roic_now)} on all capital.`,
  "diminishing":`Each new dollar is earning less: <b>${p0(x.inc_recent)}</b> on the capital added in ${x.windows[1]}${x.inc_earlier!=null?(x.inc_earlier>x.inc_recent?`, down from ${p0(x.inc_earlier)} in ${x.windows[0]}`:` (${p0(x.inc_earlier)} in ${x.windows[0]})`):""}, against ${p0(x.roic_now)} on all capital. Still above the ${hr} hurdle.`,
  "below hurdle":`New money is earning <b>${p0(x.inc_recent)}</b> (capital added in ${x.windows[1]}), below the ${hr} hurdle${x.inc_earlier!=null?`, down from ${p0(x.inc_earlier)} in ${x.windows[0]}`:""}. Growth bought this way adds no value.`,
  "unmeasured":`Can't measure it: ${x.inc_why==="invested capital barely grew or shrank"?"invested capital barely grew over the last 5 years (buybacks and dividends took the cash), so growth came from the existing business":(x.inc_why||"not enough years")}.`}[x.q1];
 const q2=x.q2==="at hurdle"?`Returns are already at or near the ${hr} hurdle (${p0(x.roic_now)}): there is little excess left to fade.`:
  x.q2==="not fading"?`No fade yet: return on capital (${p0(x.roic_now)} over the last 2 years) hasn't trended down over the last 8 years${x.roic_trend!=null?` (trend ${x.roic_trend>=0?"+":""}${(x.roic_trend*100).toFixed(1)} pts a year)`:""}. History can't say how long that lasts.`:
  `Fading: the excess over the ${hr} hurdle has halved about every <b>${x.half_life.toFixed(x.half_life<3?1:0)} years</b>. `+(x.years_left<1?`Returns (${p0(x.roic_now)}) are already within about 2 points of the hurdle.`:`At that pace returns are within 2 points of the hurdle in about <b>${x.years_left>=50?"50+":x.years_left.toFixed(0)} years</b>.`);
 const rv=x.reinvest,g=r.scenarios&&r.scenarios.base?r.scenarios.base.g1:null;
 const q5=!rv?"Not enough years with positive profit to measure.":rv.rate<=0.02?`It reinvests almost nothing: invested capital ${rv.rate<0?"shrank":"was flat"} over ${rv.years} while it earned $${rv.nopat_b.toFixed(1)}B after tax last year. Profits go to buybacks and dividends, so growth doesn't need new capital.`:
  `It put <b>${(rv.rate*100).toFixed(0)}%</b> of after-tax operating profit back into the business over ${rv.years} (about $${rv.per_year_b.toFixed(1)}B a year${rv.rate>1?", more than it earned, so partly paid for with debt, new shares or acquisitions":""}).`+(rv.growth_funded!=null?` At the latest return on new money that funds about <b>${(rv.growth_funded*100).toFixed(0)}%</b> growth a year${g!=null?`, against ${(g*100).toFixed(0)}% year-1 growth in the base case`:""}.`:x.inc_recent!=null&&x.inc_recent>1?" Returns on the extra capital are over 100%, so most growth comes from the existing assets and pricing.":"");
 const mo=r.moat?`Model setting: ${MOATN[r.moat]||r.moat}, ${r.cap_years} years of above-normal returns.`:"";
 return head+`<div class="mydet"><div>${sp}</div><p class="muted">Return on invested capital each year (10-K figures, capped at 200% on the chart; the dashed line is the ${hr} required return). Invested capital includes goodwill, so acquirers look lower than the businesses they bought.</p></div>
 <table class="s rq"><tr><th style="text-align:left;width:34%">Question</th><th style="text-align:left">Answer from the filings</th></tr>
 <tr><td style="text-align:left">Are returns on new investment diminishing?</td><td style="text-align:left">${q1}</td></tr>
 <tr><td style="text-align:left">How long can the extraordinary returns last?</td><td style="text-align:left">${q2} ${mo}</td></tr>
 <tr><td style="text-align:left">How much more can it reinvest at high returns?</td><td style="text-align:left">${q5}</td></tr></table>
 <p class="muted">History only, so it shows the direction, not the future. Nothing here changes the fair value.</p>`}
function sizeHTML(r){const z=r.sz;if(!z)return "";const d=z.d,h=z.h,eq=MY.eq;
 const why=z.k<=0?(r.diff>=0?`Price is above fair value at your ${pc1(h)} hurdle, so no new money.`:`The expected return (median ${pc1(d.med)}, ${pc1(z.pb)} chance of beating ${pc1(h)}) isn't enough above your hurdle.`)
  :`Expected return ${pc1(d.med)} a year (median; p10 ${pc1(d.p10)}, p90 ${pc1(d.p90)}) vs your ${pc1(h)} hurdle = ${pc1(z.ex)} extra → edge ${pc1(z.edge)} of full (full at +5 points). Chance of beating the hurdle ${pc1(z.pb)} → confidence ${pc1(z.conf)} (0 at 50%, full at 90%). Size = your ${pc1(MY.max)} max × ${pc1(z.edge)} × ${pc1(z.conf)} = ${pc1(z.k)}${z.scale<1?`, then ×${z.scale.toFixed(2)} so all suggested positions fit your ${pc1(eq)} in stocks`:""}.`;
 return `<h3>How much to hold</h3><p>Suggested position: <b>${pc1(r.size||0)} of your whole portfolio</b>${r.size>0?` (${pc1((r.size||0)/eq)} of the ${pc1(eq)} you keep in stocks)`:""}. ${why}</p><p class="muted">Settings: hurdle ${MY.h==null?`our judgement for this stock (${pc1(r.required_return)})`:pc1(MY.h)}, max position ${pc1(MY.max)}, stocks ${pc1(eq)} of portfolio. Change them under "My settings" above the table. A sizing guide from the model's own range, not advice: the range does not include the risk that the model itself is wrong.</p>`}
function myUI(){const S=sizeAll();
 const grp=(lab,key,opts,fmt)=>`<div class="chips"><span class="lbl">${lab}</span>${opts.map(o=>`<button class="chip${(MY[key]===o||(o!=null&&MY[key]!=null&&Math.abs(MY[key]-o)<1e-9))?" on":""}" data-my="${key}" data-v="${o}">${fmt(o)}</button>`).join("")}</div>`;
 const top=[...rows].filter(r=>r.size>0).sort((a,b)=>b.size-a.size);
 $("#mybox").innerHTML=`<details class="mydet"${MY.open?" open":""}><summary><b>My settings</b> <span class="muted">hurdle ${MY.h==null?"our judgement":pc1(MY.h)} · max ${pc1(MY.max)} a stock · ${pc1(MY.eq)} in stocks → ${S.n} stocks suggested, ${pc1(S.tot)} invested</span></summary>
  ${grp("My hurdle","h",[null,.08,.09,.10,.11,.12],o=>o==null?"Our judgement per stock":pc1(o))}
  ${grp("Max position","max",[.10,.125,.15],pc1)}
  ${grp("Stocks in portfolio","eq",[.20,.35,.60,1],o=>pc1(o)+(o===.2?" (cautious)":o===.35?" (balanced)":o===.6?" (growth)":" (all stocks)"))}
  <p class="muted"><b>My hurdle</b> is the yearly return your alternative would earn (for example QQQ or bonds plus a premium); fair value, buy-below and status are recalculated at it. "Our judgement" uses each stock's own required return and reason. <b>Suggested size</b> is a share of your <b>whole</b> portfolio: your max position × edge (expected return above your hurdle, full at +5 points a year) × confidence (chance of beating the hurdle, full at 90%), from the Monte Carlo range at today's price; zero above fair value, and scaled down if the total would exceed your stock share. The rest stays in your alternative.</p>
  ${top.length?`<p class="muted"><b>Suggested now:</b> ${top.slice(0,12).map(r=>`${r.ticker} ${pc1(r.size)}`).join(" · ")}${top.length>12?` · +${top.length-12} more`:""}. Not advice.</p>`:`<p class="muted">Nothing clears your hurdle at today's prices.</p>`}</details>`;
 const det=$("#mybox details");det.ontoggle=()=>{MY.open=det.open;save()};
 document.querySelectorAll("#mybox .chip").forEach(c=>c.onclick=()=>{const v=c.dataset.v;MY[c.dataset.my]=v==="null"?null:+v;save();refresh()})}
function save(){try{localStorage.setItem("my",JSON.stringify(MY))}catch(e){}}
function refresh(){applyHurdle();myUI();kpis();render()}
refresh();
dropUI();
if(location.hash.length>1&&rows.some(r=>r.ticker===location.hash.slice(1).toUpperCase()))open(location.hash.slice(1).toUpperCase());
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
})();
