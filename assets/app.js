const MOATN={wide:"wide moat",narrow:"narrow moat",none:"no moat",short:"short advantage"};
const INS=r=>!!r&&r.method==="excess_roe";   // underwriters: valued on book value and return on equity (model.py INSURERS)
(async function(){
const $=s=>document.querySelector(s);
const PAGE=document.body.dataset.page==="risk"?"risk":"fv";   // risk.html shares this script: same data, filters and My settings
let SZ=null;
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
if($("#bands"))$("#bands").innerHTML=BANDS.map(b=>`<div><span class="badge ${b[1]}">${b[0]}</span><p class="muted">${b[2]}</p></div>`).join("");
let A,P,TH={},SN={stocks:{}},FH={},KP={stocks:{}},KD={stocks:{}},DR0=null,RH={stocks:{}},MS={stocks:{}},DU={stocks:{}},FW={stocks:{}},DS={stocks:{}},DN={stocks:{}};
try{[A,P,TH]=await Promise.all([fetch("data/assets.json?"+Date.now()).then(r=>r.json()),fetch("data/prices.json?"+Date.now()).then(r=>r.json()),fetch("data/themes.json?"+Date.now()).then(r=>r.json()).catch(()=>({}))]);delete TH._help;[SN,FH,KP,KD]=await Promise.all([fetch("data/snapshot.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}})),fetch("data/fv_history.json?"+Date.now()).then(r=>r.json()).catch(()=>({})),fetch("data/kpis.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}})),fetch("data/kpi_defs.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}}))]);DR0=await fetch("data/drops.json?"+Date.now()).then(r=>r.ok?r.json():null).catch(()=>null);RH=await fetch("data/returns.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}}));MS=await fetch("data/moat_scorecard.json?"+Date.now()).then(r=>r.json()).catch(()=>({stocks:{}}));DU=await fetch("data/durability.json?"+Date.now()).then(r=>r.ok?r.json():{stocks:{}}).catch(()=>({stocks:{}}));FW=await fetch("data/framework.json?"+Date.now()).then(r=>r.ok?r.json():{stocks:{}}).catch(()=>({stocks:{}}));DN=await fetch("data/duration.json?"+Date.now()).then(r=>r.ok?r.json():{stocks:{}}).catch(()=>({stocks:{}}));DS=await fetch("data/debt_stress.json?"+Date.now()).then(r=>r.ok?r.json():{stocks:{}}).catch(()=>({stocks:{}}))}
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
function kpis(){if(PAGE==="risk")return riskKpis();const n=rows.length,under=rows.filter(r=>r.diff<=0).length,att=rows.filter(r=>r.status<=1).length;
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
let sortK=PAGE==="risk"?"size":"ticker",dir=PAGE==="risk"?-1:1,filt="",theme="All",pf="all",hf="all",rf="all";
const inTheme=r=>theme==="All"||(theme==="Other"?!Object.values(TH).some(l=>l.includes(r.ticker)):(TH[theme]||[]).includes(r.ticker));
const PINNED=["Cybersecurity","Insurance"];   // always shown, even before a stock in the group has a full model
const names=["All",...Object.keys(TH).filter(k=>PINNED.includes(k)||rows.some(r=>TH[k].includes(r.ticker))),...(rows.some(r=>!Object.values(TH).some(l=>l.includes(r.ticker)))?["Other"]:[])];
$("#themechips").innerHTML='<span class="lbl">Group</span>'+names.map(n=>`<button class="chip${n==="All"?" on":""}" data-th="${n}">${n}</button>`).join("");
const PF={all:["All",()=>true],below:["Below fair value",r=>r.diff<=0],int:["Interesting or better",r=>r.status<=1]};
$("#pricechips").innerHTML='<span class="lbl">Price</span>'+Object.entries(PF).map(([k,v])=>`<button class="chip${k==="all"?" on":""}" data-pf="${k}">${v[0]} <span class="cnt">${rows.filter(v[1]).length}</span></button>`).join("");
document.querySelectorAll("#pricechips .chip").forEach(c=>c.onclick=()=>{pf=c.dataset.pf;document.querySelectorAll("#pricechips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
const HF={all:["All",()=>true],clean:["Passes all 5 checks",r=>!!((SN.stocks||{})[r.ticker]||{}).all_checks]};
$("#healthchips").innerHTML='<span class="lbl">Health</span>'+Object.entries(HF).map(([k,v])=>`<button class="chip${k==="all"?" on":""}" data-hf="${k}"${k==="clean"?' title="Answers yes to all five Growth Screen checks: revenue growing, profits healthy, cash flow strong, debt manageable, financial position improving. Updated monthly."':""}>${v[0]} <span class="cnt">${rows.filter(v[1]).length}</span></button>`).join("");
document.querySelectorAll("#healthchips .chip").forEach(c=>c.onclick=()=>{hf=c.dataset.hf;document.querySelectorAll("#healthchips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
document.querySelectorAll("#themechips .chip").forEach(c=>c.onclick=()=>{theme=c.dataset.th;document.querySelectorAll("#themechips .chip").forEach(x=>x.classList.toggle("on",x===c));render()});
function render(){const f=rows.filter(r=>(r.ticker+r.name).toLowerCase().includes(filt)&&inTheme(r)&&PF[pf][1](r)&&HF[hf][1](r)&&(rf==="all"||r.rating===+rf));
 f.sort((a,b)=>{const x=a[sortK],y=b[sortK];if(x==null||y==null)return (x==null)-(y==null);return (typeof x==="string"?x.localeCompare(y):x-y)*dir});   // empty values always last
 if(PAGE==="risk")return renderRisk(f);
 $("#tbl tbody").innerHTML=f.map(r=>`<tr data-t="${r.ticker}"><td><div class="tk">${r.ticker}</div><div class="nm">${r.name}</div></td>
 <td class="r num">${usd(r.price)}<div class="nm ${r.day>0?"neg":"pos"}" style="color:var(--mut)">${r.day==null?"":pct(r.day,2)+" today"}</div></td>
 <td class="r num"><b>${usd(r.fair_value)}</b></td><td class="r num">${usd(r.buy_below)}</td>
 <td class="r num ${r.diff>0?"pos":"neg"}"><b>${pct(r.diff)}</b></td><td>${range(r)}<div class="nm">${usd(r.bear).slice(0,-3)} · ${usd(r.base).slice(0,-3)} · ${usd(r.bull).slice(0,-3)}</div></td>
 <td><span class="badge ${BANDS[r.status][1]}">${BANDS[r.status][0]}</span></td><td class="r num">${r.implied_return==null?"–":(r.implied_return*100).toFixed(1)+"%"}</td><td>${rkMini(r)}</td><td>${spark(r.history)}</td></tr>`).join("")||(theme!=="All"&&!rows.some(inTheme)?`<tr><td colspan="10" class="muted">No ${theme.toLowerCase()} stock has a full model yet. See the <a href="screener.html">Growth Screen</a> (Theme → ${theme}) for the whole group.</td></tr>`:'<tr><td colspan="10" class="err">No match</td></tr>');
 document.querySelectorAll("tbody tr[data-t]").forEach(tr=>tr.onclick=()=>open(tr.dataset.t))}
document.querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{const k=th.dataset.k;dir=sortK===k?-dir:1;sortK=k;render()});
$("#q").oninput=e=>{filt=e.target.value.toLowerCase();render()};if(PAGE==="fv")render();
function open(t){if(PAGE==="risk")return openRisk(t);const r=rows.find(x=>x.ticker===t);const s=r.scenarios||{};
 const sc=["bear","base","bull"].map(k=>{const v=s[k]||{};const pr=A.probabilities[k];
  const addb=r.wacc&&r.rev?(r.wacc.after_tax_interest||0)/r.rev:0;
  const desc=INS(r)?`book value growth ${(v.g1*100).toFixed(0)}% → ${(v.g10*100).toFixed(1)}%, long-run ROE ${(v.m*100).toFixed(1)}% (from ${(r.start_margin*100).toFixed(1)}% now)${r.insurer&&r.insurer.roe_terminal?`, then ${(r.insurer.roe_terminal[k]*100).toFixed(1)}% after year ${r.cap_years}`:""}`:r.type==="stock"?`growth ${(v.g1*100).toFixed(0)}% → ${(v.g10*100).toFixed(1)}%, FCF margin ${(v.m*100).toFixed(1)}%${addb>=0.0005?` (+${(addb*100).toFixed(1)}% interest add-back = ${((v.m+addb)*100).toFixed(1)}% before interest)`:""}`:r.type==="etf"?`EPS ${v.eps.toFixed(1)}, growth ${(v.g1*100).toFixed(0)}% → ${(v.g10*100).toFixed(1)}%, cash conversion ${(v.conv*100).toFixed(0)}%`:`${v.why}`;
  return `<tr><td style="text-align:left"><b>${k[0].toUpperCase()+k.slice(1)}</b></td><td>${usd(r[k])}</td><td>${r.type==="commodity"?"":(pr*100)+"%"}</td><td style="text-align:left;white-space:normal">${desc}</td></tr>`}).join("");
 let fc="";if(r.forecast&&INS(r))fc=insForecast(r);else if(r.forecast){const B=x=>"$"+x.toFixed(1)+"B",pc=x=>(x*100).toFixed(1)+"%",F=r.forecast,w=r.wacc||{},fi=r.fcf_inputs||{};
  const tab=k=>{const d=F[k];return `<div class="fct" data-k="${k}" style="${k==="base"?"":"display:none"}"><div class="scroll"><table class="s"><tr><th style="text-align:left">Year</th><th>Growth</th><th>Revenue</th><th>Cash margin</th><th>Cash flow</th><th>Worth today</th></tr>`+
   d.rows.map(x=>`<tr><td style="text-align:left">${x.t}</td><td>${pc(x.g)}</td><td>${B(x.rev)}</td><td>${pc(x.m)}</td><td>${B(x.fcf)}</td><td title="× ${x.df.toFixed(3)} discount">${B(x.pv)}</td></tr>`).join("")+
   `<tr><td style="text-align:left" colspan="5">${d.rows.length} years of cash flow, in today's money</td><td><b>${B(d.pv_fcf)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">+ value after year ${d.rows.length} (grows 2.5% a year forever${d.tv_factor!=null&&Math.abs(d.tv_factor-1)>0.0005?`, cash flow × ${d.tv_factor.toFixed(3)} for the return on new investment`:""}: ${B(d.tv)} in year-${d.rows.length} money)</td><td><b>${B(d.pv_tv)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">= value of the business</td><td><b>${B(d.ev)}</b></td></tr>
   <tr><td style="text-align:left" colspan="5">${r.net_cash>=0?"+ net cash":"− net debt"}</td><td>${B(Math.abs(r.net_cash))}</td></tr>
   <tr><td style="text-align:left" colspan="5">= value for shareholders ÷ ${r.shares.toFixed(3)}B shares</td><td><b>$${d.per_share.toFixed(2)}</b></td></tr></table></div></div>`};
  fc=`<h3>How the value is built, year by year</h3><details class="fcdet"><summary>Show the calculation for each year</summary>
  <p class="muted">Method: free cash flow <b>before interest</b>, discounted at the ${pc(r.required_return)} required return, then net debt subtracted. Starting cash margin ${pc(r.start_margin)} = (FCF $${(+fi.fcf).toFixed(2)}B − stock pay $${(+fi.sbc).toFixed(2)}B + after-tax interest $${(w.after_tax_interest||0).toFixed(2)}B) ÷ revenue $${r.rev.toFixed(2)}B. Growth fades in a straight line from year 1 to year 10${(r.cap_years||10)>10?`, then from the year-10 rate to 2.5% by year ${r.cap_years} (${MOATN[r.moat]||r.moat}: the advantage period)`:""}; the margin moves to the scenario target over 5 years.${r.moat_note?` ${r.moat_note}`:""}${w.wacc?` For reference, WACC would be ${pc(w.wacc)} (${pc(w.equity_weight)} equity at ${pc(w.cost_equity)}, ${pc(w.debt_weight)} debt at ${pc(w.cost_debt)} before ${pc(w.tax)} tax); it isn't used for discounting so that debt never raises the value.`:""}</p>
  <div class="chips fctabs">${["bear","base","bull"].map(k=>`<button class="chip${k==="base"?" on":""}" data-k="${k}">${k[0].toUpperCase()+k.slice(1)} · $${F[k].per_share.toFixed(2)}</button>`).join("")}</div>${["bear","base","bull"].map(tab).join("")}</details>`}
 let rt="";if(r.rate_table){const px=(P.prices[r.ticker]||{}).price;
  rt=`<h3>Fair value at different required returns</h3><p class="muted">${r.required_return_reason?`<b>Why ${(r.required_return*100).toFixed(1)}%:</b> ${r.required_return_reason}`:""}</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Required return</th><th>Fair value</th><th>Buy below</th><th>Price vs fair value</th><th>Base case</th></tr>`+
  r.rate_table.map(x=>{const on=Math.abs(x.r-r.required_return)<1e-9,d=px?px/x.fv-1:null;return`<tr><td style="text-align:left" class="${on?"hl":""}">${(x.r*100).toFixed(1)}%${on?" ⭐ used":""}</td><td class="${on?"hl":""}">$${x.fv.toFixed(2)}</td><td>$${(x.fv*(1-r.mos)).toFixed(2)}</td><td class="${d==null?"":d>0?"down":"up"}">${d==null?"–":(d>0?"+":"")+(d*100).toFixed(0)+"%"}</td><td>$${x.base.toFixed(2)}</td></tr>`}).join("")+
  `</table></div><p class="muted">Same Bear/Base/Bull weights (30/50/20), only the required return changes. A higher hurdle means future cash is worth less today.</p>`}
 // ---------- advantage period the price implies + is growth paid for? (diagnostics only; fair value unchanged)
 const piH=r.reverse_g1!=null?`<h3>What the price implies</h3><p>${r.reverse_g1<0?`At today's price and a ${(r.required_return*100).toFixed(1)}% required return, the market is pricing in year-1 sales <b>shrinking about ${Math.abs(r.reverse_g1*100).toFixed(0)}%</b>, then recovering to the base long-run rate. That is a pessimistic view.`:`To justify today's price at a ${(r.required_return*100).toFixed(1)}% required return, year-1 growth would need to be about <b>${(r.reverse_g1*100).toFixed(0)}%</b> fading to the base long-run rate.`} Terminal value is ${(r.tv_share*100).toFixed(0)}% of the base DCF.</p>`:"",piP=r.reverse_g1!=null?`<p>${r.reverse_g1<0?`At today's price and a ${(r.required_return*100).toFixed(1)}% required return, the market is pricing in year-1 sales <b>shrinking about ${Math.abs(r.reverse_g1*100).toFixed(0)}%</b>, then recovering to the base long-run rate. That is a pessimistic view.`:`To justify today's price at a ${(r.required_return*100).toFixed(1)}% required return, year-1 growth would need to be about <b>${(r.reverse_g1*100).toFixed(0)}%</b> fading to the base long-run rate.`} Terminal value is ${(r.tv_share*100).toFixed(0)}% of the base DCF.</p>`:"";
 let capH="";if(INS(r))capH=insImplied(r);else if(r.type==="stock"&&(r.implied_cap!==undefined||r.growth_check)){const pc=x=>(x*100).toFixed(0)+"%",rr=(r.required_return*100).toFixed(1)+"%",c=r.implied_cap;
  const capTxt=c==null?`Not meaningful here: base-case growth is at or below the 2.5% long-run rate, so a longer advantage period would not add value.`:
   c<=1?`Today's price needs <b>1 year or less</b> of above-average growth: the price is low even before counting any lasting edge.`:
   c>80?`Today's price needs <b>more than 80 years</b> of above-average growth at our base growth and margin. Duration alone cannot explain it: the market expects higher margins or growth than our base case, or accepts a lower return.`:
   `Today's price needs about <b>${c} years</b> of above-average growth, fading to 2.5%, at our base growth and margin. Our valuation uses ${r.cap_years||10} (${MOATN[r.moat]||"default"}${r.moat_reason?`: ${r.moat_reason.replace(/\.$/,"")}`:""}).`;
  const NOTE={free:"Assumes cash flow at or above after-tax operating profit while growing, so little net reinvestment. Normal for asset-light software and networks; aggressive otherwise.",
   below_hurdle:`Growth earns less than the ${rr} required return, so it adds no value.`,high:"Growth looks close to free (over 50%): check growth and margin together.",shrinking:"Sales shrink, so there is no growth to pay for."};
  const G=r.growth_check,gm=r.nopat_margin;
  const rows=G?["bear","base","bull"].filter(k=>G[k]).map(k=>{const g=G[k],f=g.forecast,t=g.terminal,fx=x=>x==null?"–":x>1?"over 100%":pc(x);
   return `<tr><td style="text-align:left">${k[0].toUpperCase()+k.slice(1)}</td><td class="${g.flag==="below_hurdle"?"down":""}">${fx(f)}</td><td>${fx(t)}</td><td style="text-align:left" class="muted">${g.flag?NOTE[g.flag]:"Plausible."}</td></tr>`}).join(""):"";
  capH=`<h3>How long the edge must last</h3><p>${capTxt}</p>${piP}`+(rows?`<p class="muted">Return on new investment each case implies, using after-tax operating margin ${gm!=null?pc(gm):"–"} (latest year, held flat) and reinvestment = operating profit − cash flow. Compare with the ${rr} required return: growth only adds value above it.</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th><th>Forecast years</th><th>After the forecast</th><th style="text-align:left">Reading</th></tr>${rows}</table></div>`:
   (G===null||gm==null?`<p class="muted">Return on new investment not shown: no operating profit figure for this company.</p>`:""))}
 // ---------- growth engines (segments): each segment's own year-1 growth, all fading to the scenario's year-10 rate
 let segH="";if(r.segments&&r.segments.names){const S=r.segments,pc=x=>(x*100).toFixed(1).replace(".0","")+"%";
  segH=`<h3>Growth engines</h3><p class="muted">Revenue is split into the company's reported segments (${S.period}; <a href="${S.source}" target="_blank" rel="noopener">source</a>). Each segment's year-1 growth follows its reported growth relative to the company's (${pc(S.reported)}), capped at twice the company rate, and still adds up to the scenario's year-1 growth. All segments fade to the same year-10 rate, so faster segments gain share and lift growth in years 2-9. One company-wide margin.</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Segment</th><th>Share now</th><th>Bear yr 1</th><th>Base yr 1</th><th>Bull yr 1</th></tr>`+
   S.names.map((n,i)=>`<tr><td style="text-align:left">${n}</td><td>${pc(S.share[i])}</td>${["bear","base","bull"].map(k=>`<td class="${k==="base"?"hl":""}">${pc(S.g1[k][i])}</td>`).join("")}</tr>`).join("")+`</table></div>`}
 let sens="";if(r.sensitivity){sens=`<h3>Sensitivity (base case value per share)</h3><div class="scroll"><table class="s"><tr><th>Required return ↓ / terminal growth →</th>${r.sensitivity.g.map(g=>`<th>${(g*100).toFixed(1)}%</th>`).join("")}</tr>`+
  r.sensitivity.grid.map((row,i)=>`<tr><th>${(r.sensitivity.r[i]*100).toFixed(1)}%</th>${row.map((v,j)=>`<td class="${i==2&&j==2?"hl":""}">${v.toFixed(0)}</td>`).join("")}</tr>`).join("")+"</table></div>"}
 const SN0=snapHTML(r),scH=`<h3>Scenarios</h3><table class="s"><tr><th style="text-align:left">Case</th><th>Value</th><th>Weight</th><th style="text-align:left">Assumptions</th></tr>${sc}</table>`;
 // Ex-post = looking back at reported results and history; ex-ante = looking forward with the model's forecasts
 const POST=[...SN0.post,capRetHTML(r,"post"),retHTML(r),bondHTML(r,"post")].filter(Boolean);   // risk sections live on the Risk page
 const ANTE=[...SN0.ante,capRetHTML(r,"ante"),bondHTML(r,"ante"),assumesHTML(r),capH?"":piH,capH,scH,segH,fc,rt].filter(Boolean);
 const nP=POST.length,nA=ANTE.length,sh=nP+nA?Math.round(nP/(nP+nA)*100):0;
 const grp=(id,k,t,sub,A)=>A.length?`<section class="tgrp ${k}" id="${id}"><div class="tgh"><span class="tgk">${t}</span><span class="tgs">${sub}</span><span class="tgn">${A.length} section${A.length>1?"s":""}</span></div>${A.join("")}</section>`:"";
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 ${ratingHTML(r)}${riskLinkHTML(r)}${SN0.top}
 <div class="tsplit" role="navigation" aria-label="Jump to a half of the drawer"><div class="tsbar" aria-hidden="true"><i class="post" style="width:${sh}%"></i><i class="ante" style="width:${100-sh}%"></i></div>
  <button class="tsk post" data-go="g-post"><b>Ex-post · looking back</b><span>${nP} section${nP==1?"":"s"} (${sh}%) · reported results, history, trailing figures</span></button>
  <button class="tsk ante" data-go="g-ante"><b>Ex-ante · looking forward</b><span>${nA} section${nA==1?"":"s"} (${100-sh}%) · fair value, scenarios, forecasts, expected returns</span></button></div>
 ${grp("g-post","post","Ex-post · looking back","What has actually happened: 10-K and quarterly figures, price history, past recessions",POST)}
 ${grp("g-ante","ante","Ex-ante · looking forward","What the model expects: fair value, scenarios, forecasts, NPV and expected returns",ANTE)}
 <h3>Notes</h3><p>${r.notes}</p><p class="muted">Valued ${r.valued_on}. Estimates only, not investment advice. Full step-by-step workbook is in the repo (docs/).</p>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close;document.querySelectorAll(".tsk").forEach(b=>b.onclick=()=>{const g=$("#"+b.dataset.go);if(g)g.scrollIntoView({behavior:"smooth",block:"start"})});bindSnap();bindCapRet(r);if(r.mc)drawMC(r,{bear:A.probabilities.bear,base:A.probabilities.base,bull:A.probabilities.bull});
 document.querySelectorAll(".fctabs .chip").forEach(b=>b.onclick=()=>{document.querySelectorAll(".fctabs .chip").forEach(x=>x.classList.toggle("on",x===b));document.querySelectorAll(".fct").forEach(t=>t.style.display=t.dataset.k===b.dataset.k?"":"none")})}

// ---------- Risk page (risk.html shares this script). Six checks on the stock, each scored 1 (low) to 5 (high) from data
// the dashboard already has, plus the "Risk to you" sizing above. Scores are a reading aid: nothing changes a fair value.
function rkDefs(){return [
 ["Edge lasts","Moat class and its advantage period; one step worse when the moat scorecard suggests a lower class, and one step worse when today's price needs more years of edge than ours (years shown in the cell)","g-rs-edge"],
 ["Growth paid for","Base case: does new investment earn more than the required return? Below the hurdle = growth adds no value; close to free (over 50%) or no reinvestment at all = aggressive unless asset-light","g-rs-grow"],
 ["Profits in a bad year","Durable, somewhat cyclical or cyclical, from past recessions in the filings (Are the profits durable?)","g-rs-prof"],
 ["Debts in a bad year","Pays its debts, tight or at risk in a repeat of its worst recession (Can it pay its debts in a bad year?)","g-rs-debt"],
 ["Distant cash","How much of the value is far away and how reliable it is (How far away is the value?)","g-rs-far"],
 ["Model range","90th ÷ 10th percentile value in the Monte Carlo: how wide the outcomes are (Range of outcomes)","g-rs-mc"],
 ["Price vs value","Price against fair value at your hurdle: the risk of overpaying","g-rs-px"]]}
function riskOf(r){if(r.type!=="stock")return null;const t=r.ticker,o=[],up=s=>s[0].toUpperCase()+s.slice(1),R5={1:1,3:3,5:5};
 const MR={wide:0,narrow:1,none:2},ms=(MS.stocks||{})[t],b={wide:1,narrow:2,none:4,short:3}[r.moat];
 const low=!!(ms&&ms.suggested&&MR[ms.suggested]!=null&&MR[r.moat]!=null&&MR[ms.suggested]>MR[r.moat]);
 const cy=r.cap_years||10,need=r.implied_cap,longer=need!=null&&need>cy,ny=need>80?"80+":need;
 o.push(b==null?null:{l:Math.min(5,b+(low?1:0)+(longer?1:0)),s:(r.moat==="none"?"No moat":up(r.moat))+(low?" ↓":"")+(longer?` · ${ny}y`:""),t:`${up(MOATN[r.moat]||r.moat)}, ${cy} years${low?`; scorecard suggests ${MOATN[ms.suggested]}`:""}${need==null?"":`; today's price needs ${ny} year${need===1?"":"s"}`}`});
 const G=r.growth_check&&r.growth_check.base,rq=r.required_return,gl=!G?null:G.flag==="below_hurdle"?5:G.flag==="high"||G.flag==="free"?3:G.flag==="shrinking"?3:G.forecast!=null&&G.forecast<rq+.05?2:1;
 o.push(gl==null?null:{l:gl,s:G.flag==="below_hurdle"?"Below hurdle":G.flag==="free"?"Free":G.flag==="shrinking"?"Shrinking":G.forecast!=null?(G.forecast>1?">100%":Math.round(G.forecast*100)+"%"):"–",
  t:G.flag==="free"?"Cash flow at or above operating profit while growing: little reinvestment":G.flag==="shrinking"?"Sales shrink: no growth to pay for":`New investment earns ${G.forecast>1?"over 100%":pc1(G.forecast)} vs a ${pc1(rq)} required return${G.flag==="high"?" (close to free: check)":""}`});
 const du=((DU.stocks||{})[t]||{}).stress,dl=du&&{durable:1,"somewhat cyclical":3,cyclical:5}[du.label];
 o.push(dl?{l:dl,s:{1:"Durable",3:"Somewhat",5:"Cyclical"}[dl],t:up(du.label)}:null);
 const ds=(DS.stocks||{})[t],vl=ds&&{"pays its debts":1,tight:3,"at risk":5}[ds.verdict];
 o.push(vl?{l:vl,s:{1:"Pays",3:"Tight",5:"At risk"}[vl],t:{1:"Pays its debts",3:"Tight",5:"At risk"}[vl]}:null);
 const dn=(DN.stocks||{})[t],RL=dn&&dn.reliability,rl=RL&&{"well supported":1,"some reliance on distant cash":3,"leans on distant cash":5}[RL.label],b10=dn&&dn.horizon&&dn.horizon.base?dn.horizon.base.beyond10:null;
 o.push(rl?{l:rl,s:b10==null?"–":Math.round(b10*100)+"%",t:`${up(RL.label)}${b10==null?"":`; ${Math.round(b10*100)}% of the value after year 10`}`}:null);
 const M=r.mc,f=r.fv0?r.fair_value/r.fv0:1,$k=v=>"$"+(v>=1000?v.toFixed(0):v.toFixed(v>=100?0:2));
 if(M&&M.p10>0&&M.p90){const x=M.p90/M.p10;o.push({l:x<1.6?1:x<2.2?2:x<3?3:x<4?4:5,s:x.toFixed(1)+"×",t:`${$k(M.p10*f)} to ${$k(M.p90*f)} (10th to 90th percentile)`})}else o.push(null);
 const d=r.diff;o.push(d==null?null:{l:d<=-.2?1:d<=-.05?2:d<=.05?3:d<=.25?4:5,s:(d>0?"+":"−")+Math.abs(d*100).toFixed(0)+"%",t:`${Math.abs(d*100).toFixed(0)}% ${d<0?"below":"above"} fair value`});
 return o}
// Is growth paid for, and how long must the edge last? (return on new investment each case implies; years the price needs)
function growthHTML(r){const G=r.growth_check;if(r.type!=="stock"||(!G&&r.implied_cap===undefined))return "";const rr=pc1(r.required_return),c=r.implied_cap,cy=r.cap_years||10,fx=x=>x==null?"–":x>1?"over 100%":pc1(x);
 const NOTE={free:"Cash flow at or above after-tax operating profit while growing, so little net reinvestment. Normal for asset-light software and networks; aggressive otherwise.",below_hurdle:`Growth earns less than the ${rr} required return, so it adds no value.`,high:"Close to free (over 50%): check growth and margin together.",shrinking:"Sales shrink, so there is no growth to pay for."};
 const rows=G?["bear","base","bull"].filter(k=>G[k]).map(k=>`<tr><td style="text-align:left" class="${k==="base"?"hl":""}">${k[0].toUpperCase()+k.slice(1)}</td><td class="${G[k].flag==="below_hurdle"?"down":""}">${fx(G[k].forecast)}</td><td>${fx(G[k].terminal)}</td><td style="text-align:left" class="muted">${G[k].flag?NOTE[G[k].flag]:"Plausible."}</td></tr>`).join(""):"";
 const yrs=c==null?"Base growth is at or below 2.5%, so a longer edge would not add value.":c>80?`Today's price needs <b>more than 80 years</b> of above-average growth against our ${cy}: duration alone cannot explain it.`:`Today's price needs about <b>${c} year${c===1?"":"s"}</b> of above-average growth against our ${cy} (${MOATN[r.moat]||r.moat})${c>cy?": the price assumes a longer edge than we do":""}.`;
 return `<h3>Is growth paid for, and how long must it last?</h3><p>${yrs}</p>${rows?`<p class="muted">Return on new investment each case implies (extra operating profit ÷ money reinvested), against the ${rr} required return. Growth only adds value above it.</p><div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th><th>Forecast years</th><th>After the forecast</th><th style="text-align:left">Reading</th></tr>${rows}</table></div>`:`<p class="muted">Not measured: no operating profit figure, or an insurer valued on return on equity.</p>`}`}
// Cheap under every defensible view: price at or below the fair value with the edge one moat class shorter AND the required
// return 1 point higher (duration.json: stress.lower_fv and duration.down, scaled to today's fair value at your hurdle).
function robustOf(r){const x=(DN.stocks||{})[r.ticker];if(r.type!=="stock"||!x||!x.fv||!x.duration||r.price==null)return null;
 const sh=x.stress&&x.stress.lower_fv?x.stress.lower_fv/x.fv:1,v=r.fair_value*sh*(1+x.duration.down);
 return {v,ok:r.price<=v,shorter:x.stress?x.stress.lower:null,r1:x.r+.01}}
function riskAll(){rows.forEach(r=>{const o=riskOf(r);r.rk=o;r.rb=robustOf(r);(o||[]).forEach((x,i)=>r["rk"+i]=x?x.l:null);
 r.rk_sum=o?o.reduce((a,x)=>a+(x?x.l:3),0):null;r.rk_drop=r.sz?r.sz.bd.drop:null;r.rk_loss=r.sz&&r.size>0?r.sz.loss:null})}
const rbBadge=r=>r.rb&&r.rb.ok?`<span class="rbok" title="Below ${usd(r.rb.v)}: the fair value with the edge one class shorter and a 1-point higher required return">Cheap under every view</span>`:"";
const rkCell=x=>x?`l${x.l}`:"l0";
function rkMini(r){const o=r.rk;if(!o)return '<span class="muted">–</span>';const D=rkDefs();
 return `<span class="rkmini" title="${o.map((x,i)=>`${D[i][0]}: ${x?x.t:"not scored"}`).join("\n")}">${o.map(x=>`<i class="${rkCell(x)}"></i>`).join("")}</span>`}
function riskLinkHTML(r){const o=r.rk,z=r.sz;if(!o&&!z)return "";const hi=o?o.filter(x=>x&&x.l>=4).length:0,md=o?o.filter(x=>x&&x.l===3).length:0;
 return `<a class="rklink" href="risk.html#${r.ticker}">${o?`<span class="rkmini big">${o.map(x=>`<i class="${rkCell(x)}"></i>`).join("")}</span>`:""}<span><b>Risk</b> · ${r.rb&&r.rb.ok?"cheap under every view · ":""}${o?`${hi} high, ${md} medium of ${o.length} checks`:"no stock checks for this asset"}${z?` · suggested size ${pc1(r.size||0)}`:""}</span><span class="go">Open risk →</span></a>`}
function fpHTML(r){const o=r.rk,z=r.sz,D=rkDefs(),seg=l=>`<span class="seg">${[1,2,3,4,5].map(k=>`<i class="${l&&k<=l?"l"+l:""}"></i>`).join("")}</span>`;
 const st=o?o.map((x,i)=>`<button class="fpm" data-go="${D[i][2]}" title="${D[i][1]}"><span class="fl">${D[i][0]}</span><span class="fv">${x?esc(x.t):"Not scored"}</span>${seg(x&&x.l)}</button>`).join(""):`<p class="muted">No stock checks: not an operating company.</p>`;
 const b=z&&z.bd,dl=b?(b.drop>=.5?5:b.drop>=.42?4:3):null;
 const you=z?`<button class="fpm" data-go="g-ry"><span class="fl">Bad-case drop</span><span class="fv">−${pc1(b.drop)}${b.floor?" (floor)":""}</span>${seg(dl)}</button>
  <div class="fpm"><span class="fl">Suggested size</span><span class="fv"><b>${pc1(r.size||0)}</b>${r.size>0&&z.lim?` · ${LIM[z.lim]}`:""}</span></div>
  <div class="fpm"><span class="fl">You lose in the bad case</span><span class="fv">${r.size>0?"−"+pc1(z.loss)+" of portfolio":"–"}</span></div>
  <div class="fpm"><span class="fl">Your loss budget</span><span class="fv">${pc1(MY.lb)} a stock</span></div>`:`<p class="muted">No size: no model range for this asset.</p>`;
 return `<div class="fp"><section class="rs"><h4>Risk in the stock</h4>${st}</section><section class="ry"><h4>Risk to you</h4>${you}</section></div>`}
function robustHTML(r){const b=r.rb;if(!b)return "";const cl={narrow:"narrow moat, 15 years",none:"no moat, 12 years",end10:"edge ending at year 10"}[b.shorter];
 return `<p class="rbline ${b.ok?"ok":""}">${b.ok?`<b>Cheap under every view.</b> `:`<b>Not cheap under every view.</b> `}With ${cl?`the edge one class shorter (${cl})`:"the same 10-year edge"} and a ${pc1(b.r1)} required return, fair value would be <b>${usd(b.v)}</b>; the price is ${usd(r.price)}.</p>`}
function grpHTML(id,k,t,sub,A){return A.length?`<section class="tgrp ${k}" id="${id}"><div class="tgh"><span class="tgk">${t}</span><span class="tgs">${sub}</span><span class="tgn">${A.length} section${A.length>1?"s":""}</span></div>${A.join("")}</section>`:""}
function openRisk(t){const r=rows.find(x=>x.ticker===t);if(!r)return;
 const sec=(id,h)=>h?`<div id="${id}" class="rksec">${h}</div>`:"";
 const S=[sec("g-rs-edge",moatHTML(r)),sec("g-rs-grow",growthHTML(r)),sec("g-rs-prof",durHTML(r)),sec("g-rs-debt",debtHTML(r)),sec("g-rs-far",farHTML(r)),sec("g-rs-mc",mcHTML(r))].filter(Boolean),Y=[sizeHTML(r)].filter(Boolean);
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 <p class="muted">Price ${usd(r.price)} · fair value ${usd(r.fair_value)} · <a href="index.html#${r.ticker}">Fair value and the full model →</a></p>
 ${robustHTML(r)}${fpHTML(r)}
 ${grpHTML("g-rs","rs","Risk in the stock","Could the business, its debts or the model let you down? The same for every owner",S)}
 ${grpHTML("g-ry","ry","Risk to you","How much a loss would hurt you: sizing from your settings",Y)}
 <p class="muted">Estimates only, not investment advice.</p>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close;
 document.querySelectorAll("#dr .fpm[data-go]").forEach(b=>b.onclick=()=>{const g=$("#"+b.dataset.go);if(g)g.scrollIntoView({behavior:"smooth",block:"start"})});
 if(r.mc)drawMC(r,{bear:A.probabilities.bear,base:A.probabilities.base,bull:A.probabilities.bull})}
function renderRisk(f){const D=rkDefs(),pr=v=>v==null?"–":pc1(v);
 $("#tbl tbody").innerHTML=f.map(r=>{const o=r.rk,z=r.sz;
  return `<tr data-t="${r.ticker}"><td><div class="tk">${r.ticker}</div><div class="nm">${r.name}</div>${rbBadge(r)}</td>
  ${D.map((d,i)=>{const x=o&&o[i];return `<td class="rk ${rkCell(x)}" title="${d[0]}: ${x?esc(x.t):"not scored"}">${x?x.s:"–"}</td>`}).join("")}
  <td class="r num yu">${z?"−"+pr(z.bd.drop)+(z.bd.floor?"*":""):"–"}</td><td class="r num yu">${r.size==null?"–":r.size>0?`<b>${pc1(r.size)}</b>`:'<span class="muted">0%</span>'}</td>
  <td class="yu">${z&&r.size>0&&z.lim?LIM[z.lim]:'<span class="muted">–</span>'}</td><td class="r num yu">${z&&r.size>0?"−"+pc1(z.loss):"–"}</td></tr>`}).join("")||'<tr><td colspan="12" class="err">No match</td></tr>';
 document.querySelectorAll("tbody tr[data-t]").forEach(tr=>tr.onclick=()=>open(tr.dataset.t))}
function riskKpis(){if(!SZ)return;const st=rows.filter(r=>r.rk),hi=st.filter(r=>r.rk.slice(0,-1).some(x=>x&&x.l===5)).length,T=SZ.theme;
 $("#kpis").innerHTML=[["Suggested positions",SZ.n,`${pc1(SZ.tot)} of your portfolio${SZ.scaled?`, all scaled down to fit your ${pc1(MY.eq)} stock share`:""}`],["Your bad case","−"+pc1(SZ.loss),`if every suggested stock hits its bad case at once${MY.pl!=null?` (limit ${pc1(MY.pl)}${SZ.plScaled?", sizes scaled down":""})`:""}`],
  ["Cheap under every view",`${rows.filter(r=>r.rb&&r.rb.ok).length} of ${st.length}`,"below value even with a shorter edge and a 1-point higher return"],["Biggest theme",T?esc(T[0]):"–",T?`${pc1(T[1])} of your portfolio (cap ${pc1(THEME_CAP)})`:"nothing suggested"],
  ["Business red flags",`${hi} of ${st.length}`,"stocks with a check at the highest level (price left out)"]].map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("")}

// Monte Carlo range + what moves the value most (risk page drawer)
function mcHTML(r){let mcH="";if(r.mc){const M=r.mc,$f=x=>"$"+(x>=1000?x.toFixed(0):x.toFixed(2)),W=500;
  const T=M.tornado,tl=Math.min(...T.rows.map(o=>Math.min(o.low,o.high)),T.base),th=Math.max(...T.rows.map(o=>Math.max(o.low,o.high)),T.base),TX=x=>235+(x-tl)/(th-tl)*190;
  const torn=`<svg viewBox="0 0 ${W} ${T.rows.length*30+24}" class="mcsvg" role="img" aria-label="Sensitivity of base-case value"><line x1="${TX(T.base)}" x2="${TX(T.base)}" y1="4" y2="${T.rows.length*30+6}" class="mcfv"/>`+
   T.rows.map((o,i)=>{const a=Math.min(o.low,o.high),b=Math.max(o.low,o.high),y=10+i*30,pin=v=>Math.abs(v)<1?(v*100).toFixed(1)+"%":v;
    return `<text x="0" y="${y+13}" class="mct mcl">${o.label.replace(" (+1 / -1 pt)","").replace(" (2% / 3%)","")}${o.choice?" *":""}</text><rect class="mctb" x="${TX(a)}" y="${y+2}" width="${Math.max(2,TX(b)-TX(a))}" height="16" rx="3"><title>${o.label}: ${pin(o.low_in)} → ${$f(o.low)}, ${pin(o.high_in)} → ${$f(o.high)}</title></rect><text x="${TX(a)-4}" y="${y+14}" text-anchor="end" class="mct">${$f(a)}</text><text x="${TX(b)+4}" y="${y+14}" class="mct">${$f(b)}</text>`}).join("")+
   `<text x="${TX(T.base)}" y="${T.rows.length*30+20}" text-anchor="middle" class="mct">base case ${$f(T.base)}</text></svg>`;
  mcH=`<h3>Range of outcomes (Monte Carlo)</h3><div id="mcbox"></div>
  <h3>What moves the value most</h3><p class="muted">Base case with one input moved to its bear and bull value, the others unchanged. * The required return is a choice, shown for comparison.</p>${torn}`}
 return mcH}

// ---------- Capital and returns: what $100k at today's price is worth (NPV), whether returns beat the cost of capital,
// how much the company invests and what that investment is expected to bring in. Every number follows the rate buttons.
function capRates(r){const h=hurdleOf(r),W=r.wacc_row,L=[{r:h,l:(MY.h==null?"Required ":"My hurdle ")+pc1(h)}];
 if(W&&!INS(r))L.push({r:W.r,l:"WACC "+pc1(W.r),w:1});
 r.rate_table.forEach(x=>{if(!L.some(o=>Math.abs(o.r-x.r)<5e-4))L.push({r:x.r,l:pc1(x.r)})});
 return L.filter(o=>o.w||r.rate_table.some(x=>Math.abs(x.r-o.r)<1e-9))}
function capRetHTML(r,part){if(r.type!=="stock"||!r.rate_table||r.rate_table[0].bear==null||r.price==null)return "";
 const L=capRates(r);r._capL=L;
 const T=part==="post"?["Capital and returns: track record","From the 10-Ks: has the business earned more than its capital costs, and how much has it invested? Pick the return you want (your cost of capital); it also sets the forward-looking half below:"]:["Capital and returns: what $100,000 earns","From the model: is $100,000 at today's price worth it, and what will the planned investment bring in? Same rate as the track record above:"];
 return `<h3>${T[0]}</h3><p class="muted">${T[1]}</p>
 <div class="chips caprate"><span class="lbl">Return</span>${L.map((o,i)=>`<button class="chip${i?"":" on"}" data-i="${i}"${o.w?` title="Blended cost of capital: ${pc1(r.wacc.equity_weight)} equity at ${pc1(r.wacc.cost_equity)}, ${pc1(r.wacc.debt_weight)} debt at ${pc1(r.wacc.cost_debt)} before tax"`:""}>${o.l}</button>`).join("")}</div><div class="capbody" data-part="${part}">${capBody(r,L[0],part)}</div>`}
function bindCapRet(r){document.querySelectorAll(".caprate .chip").forEach(b=>b.onclick=()=>{const i=b.dataset.i;document.querySelectorAll(".caprate .chip").forEach(x=>x.classList.toggle("on",x.dataset.i===i));document.querySelectorAll(".capbody").forEach(c=>c.innerHTML=capBody(r,r._capL[+i],c.dataset.part))})}
function capBody(r,o,part){const k=o.r,V=o.w?r.wacc_row:r.rate_table.find(x=>Math.abs(x.r-k)<1e-9),px=r.price,ins=INS(r),p=pc1(k);
 const $k=x=>(x<0?"−$":"$")+Math.abs(Math.round(x)).toLocaleString("en-US"),B=x=>x==null?"–":(x<0?"−$":"$")+Math.abs(x).toFixed(Math.abs(x)<10?2:1)+"B",p0=x=>(x*100).toFixed(0)+"%";
 // 1. NPV of $100,000
 const sh=100000/px,npv=v=>sh*v-100000,ev=npv(V.fv),band=ev>5000?["positive","up"]:ev<-5000?["negative","down"]:["about zero",""];
 const d=retDist(r),pPos=d?1-d.F(k):null;
 const row=(n,v,w)=>`<tr><td style="text-align:left">${n}${w?` <span class="muted">${w}</span>`:""}</td><td>$${v.toFixed(2)}</td><td>${$k(sh*v)}</td><td><span class="${npv(v)>0?"up":"down"}">${npv(v)>0?"+":""}${$k(npv(v))}</span></td></tr>`;
 const s1=`<h4>If you invest $100,000 today, what is it worth?</h4>
 <div class="grid3"><div class="mini">NPV at ${p}<b class="${band[1]}">${ev>0?"+":""}${$k(ev)}</b><span class="muted">${band[0]} · ${sh.toFixed(sh<10?2:0)} shares at $${px.toFixed(2)}</span></div>
 <div class="mini">Chance NPV &gt; 0<b class="${pPos!=null&&pPos>=.5?"up":"down"}">${pPos==null?"–":p0(pPos)}</b><span class="muted">Monte Carlo, bear/base/bull ${A.probabilities.bear*100}/${A.probabilities.base*100}/${A.probabilities.bull*100}</span></div>
 <div class="mini">Expected return<b class="${d&&d.med>=k?"up":"down"}">${d?pc1(d.med):"–"}</b><span class="muted">a year at this price (median) vs ${p}</span></div></div>
 <div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th><th>Value a share at ${p}</th><th>Your shares are worth</th><th>NPV</th></tr>${row("Bear",V.bear,"30%")}${row("Base",V.base,"50%")}${row("Bull",V.bull,"20%")}${row("<b>Weighted</b>",V.fv)}</table></div>
 <p class="muted">NPV = what your shares are worth when the company's future ${ins?"payouts (net income less growth in book value)":"free cash flow"} is discounted at ${p}, minus the $100,000 you pay. Positive means the price is low enough to earn more than ${p} a year if that case plays out; zero means you earn exactly ${p}; negative means less (you can still make money, just under ${p}). "About zero" is within ±$5,000.${o.w?" At WACC, cash flow before interest is discounted at the blended cost of equity and debt, so cheap debt raises the value a little; the fair value itself uses the required return.":""}</p>`;
 // 2. Return on capital vs the rate
 const x=(RH.stocks||{})[r.ticker]||{},m=ins?"ROE":"ROIC",R=x.roic||[];let s2;
 if(!R.length||x.nopat_last_b==null){s2=`<h4>Has the return beaten the cost of capital?</h4><p>${x.note||"Not enough statements to measure the return on capital."}</p>`}
 else{const last=R[R.length-1],ab=R.filter(q=>q[1]>k).length,eva=x.nopat_last_b-k*x.ic_last_b,inc=x.inc_recent;
  s2=`<h4>Has the return beaten the cost of capital?</h4>
  <div class="grid3"><div class="mini">${m} ${last[0]}<b class="${last[1]>k?"up":"down"}">${p0(last[1])}${last[1]>=2?"+":""}</b><span class="muted">vs ${p} · ${last[1]>k?"+":""}${((last[1]-k)*100).toFixed(1)} pts</span></div>
  <div class="mini">Years above ${p}<b class="${ab/R.length>=.8?"up":ab/R.length<.5?"down":""}">${ab} of ${R.length}</b><span class="muted">${R[0][0]}–${last[0]}</span></div>
  <div class="mini">Value ${eva>=0?"created":"destroyed"} in ${last[0]}<b class="${eva>=0?"up":"down"}">${B(eva)}</b><span class="muted">${ins?"net income":"after-tax operating profit"} ${B(x.nopat_last_b)} − ${p} × ${B(x.ic_last_b)} ${ins?"book value":"capital"}</span></div></div>
  <p>${inc==null?`Return on new money: ${x.inc_why||"not measurable"}.`:`New money is earning <b class="${inc>k?"up":"down"}">${inc>2?"over 200%":p0(inc)}</b> (extra profit ÷ extra capital, ${x.windows?x.windows[1]:"latest 5 years"}), ${inc>k?"above":"below"} ${p}${inc>k?": growth adds value.":": growth bought this way adds no value."}`}</p>
  <p class="muted">${m} = ${ins?"net income ÷ book value":"after-tax operating profit ÷ invested capital (equity + debt − cash, average of the year)"}, from the 10-Ks. Value created = the profit above what the capital costs at ${p} (economic profit).</p>`}
 // 3. How much is it investing?
 let s3="";const I=x.invest;if(!ins&&I&&I.length){const anyA=I.some(q=>q.acq!=null),tot=q=>(q.capex||0)+(q.rd||0)+(q.acq||0);
  s3=`<h4>How much has it invested?</h4><div class="scroll"><table class="s"><tr><th style="text-align:left">Year</th><th>Capex</th><th>Beyond depreciation</th><th>R&amp;D</th><th>Acquisitions</th><th>Total</th><th>% of sales</th><th>Op. cash flow</th></tr>`+
  I.map(q=>`<tr><td style="text-align:left">${q.y}</td><td>${B(q.capex)}</td><td>${q.capex!=null&&q.dep!=null?B(Math.max(0,q.capex-q.dep)):"–"}</td><td>${B(q.rd)}</td><td>${q.acq==null?"–":B(q.acq)}</td><td><b>${B(tot(q))}</b></td><td>${q.rev?pc1(tot(q)/q.rev):"–"}</td><td>${B(q.ocf)}</td></tr>`).join("")+`</table></div>
  <p class="muted">Capex beyond depreciation roughly splits keeping today's business running from building new capacity (depreciation includes amortisation of acquired intangibles, so it overstates upkeep for acquirers). R&amp;D is an expense in the accounts but is money spent on future products. ${anyA?"Acquisitions = cash paid for businesses, net of cash acquired.":"Acquisitions arrive with the next stock snapshot refresh (the 2nd of each month)."} Operating cash flow is after R&amp;D, before capex and acquisitions. A dash means the figure isn't in the free data for that year.</p>`}
 // 4. What will the model's investment bring in?
 let s4="";const F=r.forecast,nm=r.nopat_margin;
 if(F&&(ins||nm!=null)){const K=["bear","base","bull"];
  const one=c=>{const f=F[c];if(!f)return null;const rw=f.rows,n=rw.length;let re,gain,cf;
   if(ins){if(!f.ni)return null;re=rw.reduce((s,q,i)=>s+f.ni[i]-q.fcf,0);gain=f.ni[n-1]-f.ni[0];cf=rw[n-1].fcf-rw[0].fcf}
   else{re=rw.reduce((s,q)=>s+q.rev*nm-q.fcf,0);gain=(rw[n-1].rev-r.rev)*nm;cf=rw[n-1].fcf-r.rev*r.start_margin}
   return {n,re,gain,cf,ron:re>0&&gain>0?gain/re:null}};
  const rs=K.map(one);if(rs.some(Boolean)){const N=rs.find(Boolean).n;
  s4=`<h4>What will the planned investment bring in? (model, ${N} years)</h4><div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th><th>Reinvested</th><th>Extra ${ins?"net income":"profit"} a year</th><th>Extra ${ins?"payout":"cash"} a year</th><th>Return</th><th style="text-align:left">vs ${p}</th></tr>`+
  K.map((c,i)=>{const z=rs[i];if(!z)return "";const ok=z.ron!=null&&z.ron>k;
   return `<tr><td style="text-align:left">${c[0].toUpperCase()+c.slice(1)}</td><td>${B(z.re)}</td><td>${B(z.gain)}</td><td>${B(z.cf)}</td><td>${z.ron==null?"–":z.ron>2?"over 200%":p0(z.ron)}</td><td style="text-align:left;white-space:normal">${z.gain<=0?'<span class="down">shrinking</span>':z.re<=0?"grows with little reinvestment":ok?'<span class="up">adds value</span>':'<span class="down">adds no value</span>'}</td></tr>`}).join("")+`</table></div>
  <p class="muted">${ins?"Reinvested = net income kept to grow the book (net income − payouts), summed over the forecast; extra net income and payout = the last forecast year's − year 1's (year 1, not the last 12 months, so a one-off profit today doesn't read as shrinkage) = the last forecast year's − the first's.":`Reinvested = after-tax operating profit (today's ${pc1(nm)} margin, held flat) − free cash flow before interest, summed over the forecast; extra profit = the growth in sales × that margin; extra cash flow = the last forecast year's − today's.`} All in year-${N} terms. Return = extra yearly profit ÷ total reinvested: above ${p} the growth is worth paying for. Not discounted; the NPV above is the discounted answer, and the track record in the looking-back half shows what it has earned so far.</p>`}}
 return part==="post"?s2+s3:s1+s4}

// ---------- Underwriters (book value and ROE model): how the value is built, what the price implies, how long the edge must last
function insForecast(r){const F=r.forecast,I=r.insurer||{},pc=x=>(x*100).toFixed(1)+"%",B=x=>(x<0?"−$":"$")+Math.abs(x).toFixed(Math.abs(x)<10?2:1)+"B",rr=r.required_return;
 const tab=k=>{const d=F[k],n=d.rows.length;return `<div class="fct" data-k="${k}" style="${k==="base"?"":"display:none"}"><div class="scroll"><table class="s"><tr><th style="text-align:left">Year</th><th>Book growth</th><th>Book value (end)</th><th>ROE</th><th>Net income</th><th>Paid out</th><th>Worth today</th></tr>`+
  d.rows.map((x,i)=>`<tr><td style="text-align:left">${x.t}</td><td>${pc(x.g)}</td><td>${B(x.rev)}</td><td>${pc(x.m)}</td><td>${d.ni?B(d.ni[i]):"–"}</td><td>${B(x.fcf)}</td><td title="× ${x.df.toFixed(3)} discount">${B(x.pv)}</td></tr>`).join("")+
  `<tr><td style="text-align:left" colspan="6">${n} years of payouts, in today's money</td><td><b>${B(d.pv_fcf)}</b></td></tr>
  <tr><td style="text-align:left;white-space:normal" colspan="6">+ value after year ${n}: book value ${B(d.rows[n-1].rev)} × (ROE ${pc(d.roe_terminal)} − 2.5%) ÷ (${pc(rr)} − 2.5%) = ${B(d.tv)} in year-${n} money</td><td><b>${B(d.pv_tv)}</b></td></tr>
  ${Math.abs(r.net_cash)>0.0005?`<tr><td style="text-align:left" colspan="6">${r.net_cash>=0?"+":"−"} other adjustments</td><td>${B(Math.abs(r.net_cash))}</td></tr>`:""}
  <tr><td style="text-align:left" colspan="6">= value for shareholders ÷ ${r.shares.toFixed(4)}B shares</td><td><b>$${d.per_share.toFixed(2)}</b></td></tr>
  <tr><td style="text-align:left;white-space:normal" colspan="7" class="muted">The same value, split: book value today ${B(d.bv0)} + excess returns ${B(d.excess)} (each year's (ROE − ${pc(rr)}) × book value, in today's money).${d.excess<0?" Negative: the ROE is below the required return, so the business is worth less than its book.":""}</td></tr></table></div></div>`};
 return `<h3>How the value is built, year by year</h3><details class="fcdet"><summary>Show the calculation for each year</summary>
 <p class="muted">Method for an insurer: <b>book value and return on equity</b> (excess return), not free cash flow, because an insurer's cash flow mixes in premiums it holds for future claims. Each year net income = ROE × book value at the start of the year; the book grows with the business; what is left over (net income − growth in book value) can be paid out as dividends and buybacks. Those payouts are discounted at the ${pc(rr)} required return. Today: book value ${B(I.bv||r.rev)} ($${(I.bv_ps||0).toFixed(2)} a share, price ${(I.pb||0).toFixed(2)}× book), net income ${B(I.ni||0)} over the last 12 months (ROE ${pc(I.roe_ttm||0)}); the model starts at ${pc(r.start_margin)} and moves to the scenario ROE over 5 years. Book growth fades from year 1 to year 10, then to 2.5% by year ${r.cap_years} (${MOATN[r.moat]||r.moat}). After that ${r.moat==="none"?"the ROE falls to the required return, so further growth adds nothing":r.moat==="narrow"?"the ROE fades halfway to the required return":"the ROE stays at the scenario level"}; a ROE already below the required return stays where it is.</p>
 <div class="chips fctabs">${["bear","base","bull"].map(k=>`<button class="chip${k==="base"?" on":""}" data-k="${k}">${k[0].toUpperCase()+k.slice(1)} · $${F[k].per_share.toFixed(2)}</button>`).join("")}</div>${["bear","base","bull"].map(tab).join("")}</details>`}
function insImplied(r){const I=r.insurer||{},pc=x=>(x*100).toFixed(1).replace(".0","")+"%",rr=pc(r.required_return),c=r.implied_cap,b=(r.scenarios||{}).base||{};
 const need=I.roe_needed==null?`The price can't be matched by changing the long-run ROE alone.`:`At today's price (${(I.pb||0).toFixed(2)}× book) and a ${rr} required return, the market is pricing in a long-run <b>ROE of about ${pc(I.roe_needed)}</b>, against ${pc(b.m)} in our base case and ${pc(I.roe_ttm||0)} over the last 12 months.`;
 const capTxt=c==null?`Not meaningful here: the base-case ROE is at or below the ${rr} required return, so a longer period would not add value.`:
  c<=1?`Today's price needs <b>1 year or less</b> of base-case ROE above the required return: the price is low even before counting a lasting edge.`:
  c>80?`Today's price needs <b>more than 80 years</b> of base-case ROE above the required return: the market expects a higher ROE than our base case, or accepts a lower return.`:
  `Today's price needs about <b>${c} years</b> of the base-case ROE (${pc(b.m)}) before it drops to the ${rr} required return. Our valuation uses ${r.cap_years} (${MOATN[r.moat]||"default"}${r.moat_reason?`: ${r.moat_reason.replace(/\.$/,"")}`:""}).`;
 return `<h3>How long the edge must last</h3><p>${capTxt}</p><p>${need} Terminal value is ${(r.tv_share*100).toFixed(0)}% of the base case.</p>
 <p class="muted">For an insurer the edge is a return on equity above the required return: underwriting discipline, cheaper distribution or a niche. Growth only adds value while the ROE is above ${rr}; at or below it, a bigger book is worth no more than its cost.</p>`}

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
 box.innerHTML=`<p class="muted">${M.n.toLocaleString()} runs: Bear / Base / Bull in proportion to the weights, each with ${INS(r)?"book growth, long-run book growth and ROE":"growth, long-run growth and margin"} varied together (correlated) and terminal growth around 2.5%. The ${rrs} required return is fixed: it's your choice, not an uncertainty. <b>Values</b> are what the business is worth <b>today</b> at ${rrs}; <b>returns</b> are what you'd earn a year buying at today's price.</p>
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
 ${HX||RX?`<h3>Yearly return if you buy at today's price</h3>
 <div class="scroll"><table class="s"><tr><th style="text-align:left">Version</th><th>Median</th><th>10th – 90th</th><th style="text-align:left;white-space:normal">What it assumes</th></tr>
 ${[5].filter(h=>I&&I["hold"+h]&&m0).map(h=>{const X=mix(irrAt(I,m0,"hold"+h).Q,w),q=p=>X.inv(p);return `<tr><td style="text-align:left"><b>${h}-year hold</b>${MY.hz===h?" ⭐ your horizon":""}</td><td>${rp(q(.5))}</td><td>${rp(q(.1))} – ${rp(q(.9))}</td><td style="text-align:left;white-space:normal">Like the 10-year hold, but you sell at the end of year ${h}. Chance of a loss ${pf(X.F(0))}.</td></tr>`}).join("")}
 ${HX?`<tr><td style="text-align:left"><b>10-year hold</b>${MY.hz===10?" ⭐ your horizon":""}</td><td><b>${rp(hq(.5))}</b></td><td>${rp(hq(.1))} – ${rp(hq(.9))}</td><td style="text-align:left;white-space:normal">You buy at ${$f(px)}, receive 10 years of ${INS(r)?"the cash it can pay out (net income less the growth in book value)":"the business's free cash flow"}, then sell at the end of year 10 at the price that gives the next buyer ${rrs} (the gap closes in year 10). Can be negative: chance of a loss ${pf(pLoss)}.</td></tr>`:""}
 ${[20].filter(h=>I&&I["hold"+h]&&m0).map(h=>{const X=mix(irrAt(I,m0,"hold"+h).Q,w),q=p=>X.inv(p);return `<tr><td style="text-align:left"><b>${h}-year hold</b>${MY.hz===h?" ⭐ your horizon":""}</td><td>${rp(q(.5))}</td><td>${rp(q(.1))} – ${rp(q(.9))}</td><td style="text-align:left;white-space:normal">Like the 10-year hold, but you sell at the end of year ${h}. Chance of a loss ${pf(X.F(0))}.</td></tr>`}).join("")}
 ${RX?`<tr><td style="text-align:left"><b>Hold for good</b>${MY.hz==null?" ⭐ your horizon":""}</td><td>${rp(rq(.5))}</td><td>${rp(rq(.1))} – ${rp(rq(.9))}</td><td style="text-align:left;white-space:normal">You never sell: 10 years of cash flow, then cash growing at terminal growth forever. Can't go below about 2.5%, so a low number means "poor return", not "safe".</td></tr>`:""}</table></div>
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
  S.cards.map((c,i)=>`<button class="qc" data-i="${i}" aria-expanded="false"><span class="qt">${c.title}</span>${cardAns(c).enough?`<span class="gr ${GC[c.grade]||"g-n"}"><i></i>${c.grade}</span>`:`<span class="gr g-n"><i></i>Not enough data</span>`}
   <span class="qq">${esc(c.question)}</span><span class="qh">${c.headline.map(esc).join(" · ")||"–"}</span>${spark2(c.trend)}${ansLine(c)}</button>`).join("")+`</div><div id="qdet" class="qdet" hidden></div>`;
  window.__snapCards=S.cards.map(c=>`<div class="qdh"><b>${c.title}</b> <span class="gr ${GC[c.grade]||"g-n"}"><i></i>${c.grade}</span> <span class="muted">${esc(c.question)}${c.note?" "+esc(c.note):""}</span></div>
   <div class="scroll"><table class="s qtab"><tr><th style="text-align:left">Metric</th><th>Value</th><th>Grade</th><th style="text-align:left" title="Percentile among ${esc(sn)} companies (or the industry, where the note says so)">vs peers</th></tr>`+
   c.metrics.map(m=>`<tr class="${m.graded?"":"info"}"><td style="text-align:left;white-space:normal">${esc(m.label)}${m.note?`<div class="muted mnote">${esc(m.note)}</div>`:""}</td><td${String(m.value).length>28?' style="white-space:normal;min-width:190px"':""}>${esc(m.value)}</td>
    <td>${m.graded?`<span class="gd ${["g-w","g-o","g-s"][m.score]}" title="${["Weak","OK","Strong"][m.score]}"></span>`:`<span class="muted" title="Shown for context, not graded here">info</span>`}</td><td style="text-align:left">${pbar(m.pct,m.grp||sn)}</td></tr>`).join("")+
   `</table></div>${c.trend&&c.trend.points&&c.trend.points.length?`<p class="muted">${esc(c.trend.label)}: ${c.trend.points.map(p=>p[0]+" "+p[1]+(c.trend.unit||"")).join(" · ")}</p>`:""}`)}
 // valuation strip
 const lo=Math.min(r.bear,px,r.buy_below)*0.92,hi=Math.max(r.bull,px)*1.06,X=v=>((v-lo)/(hi-lo)*100).toFixed(2)+"%";
 let pA=null,h10=null;if(r.mc&&r.mc.regimes){const Q={};KS.forEach(k=>Q[k]=r.mc.regimes[k].quantiles);const w={bear:A.probabilities.bear,base:A.probabilities.base,bull:A.probabilities.bull};pA=1-mix(Q,w).F(px);
  h10=h10Of(r,px)}
 const V=S&&S.valuation,L=V&&V.live,live={pe:L&&L.trailing_eps>0?px/L.trailing_eps:V&&V.now.pe,ev_ebitda:L&&L.ebitda>0&&L.shares?(px*L.shares+(L.net_debt||0))/L.ebitda:V&&V.now.ev_ebitda,fcf_yield:L&&L.fcf_ttm&&L.shares?L.fcf_ttm/(px*L.shares)*100:V&&V.now.fcf_yield};
 const mrow=(k,lab,low,unit)=>{const h=V.history[k]||[],now=live[k];if(now==null||!isFinite(now))return "";const vals=h.map(x=>x[1]);const mn=Math.min(...vals,now),mx=Math.max(...vals,now),pos=x=>((x-mn)/((mx-mn)||1)*100).toFixed(1)+"%";
  const hmn=Math.min(...vals),hmx=Math.max(...vals),where=!vals.length?"":now>hmx?"above its range":now<hmn?"below its range":now>hmn+(hmx-hmn)*2/3?"top of its range":now<hmn+(hmx-hmn)/3?"bottom of its range":"middle of its range";
  const cheap=!vals.length?null:low?(now<hmn+(hmx-hmn)/3):(now>hmn+(hmx-hmn)*2/3);const dear=!vals.length?null:low?(now>hmn+(hmx-hmn)*2/3):(now<hmn+(hmx-hmn)/3);
  return `<tr><td style="text-align:left">${lab}</td><td><b>${now.toFixed(1)}${unit}</b></td><td style="text-align:left">${vals.length?`<span class="vr" title="${h.map(x=>x[0]+": "+x[1]+unit).join(", ")}"><span class="vrb" style="left:${pos(hmn)};width:calc(${pos(hmx)} - ${pos(hmn)})"></span><i class="${cheap?"up":dear?"down":""}" style="left:${pos(now)}"></i></span> <span class="muted">${hmn.toFixed(1)}–${hmx.toFixed(1)}${unit} · ${where}</span>`:"–"}</td><td style="text-align:left">${pbar(V.sector_pct[k],V.sector_pct.name)}</td></tr>`};
 const vt=V?`<div class="scroll"><table class="s vtab"><tr><th style="text-align:left">Multiple</th><th>Now</th><th style="text-align:left">vs its own last ${Math.max(...["pe","ev_ebitda","fcf_yield"].map(k=>(V.history[k]||[]).length))} years</th><th style="text-align:left" title="Percentile in the sector; further right = cheaper">vs sector</th></tr>
  ${mrow("pe","P/E",true,"")}${INS(r)?"":mrow("ev_ebitda","EV / EBITDA",true,"")+mrow("fcf_yield","FCF yield",false,"%")}</table></div>${INS(r)?`<p class="muted">EV/EBITDA and FCF yield are left out for an insurer: its debt and cash flow mix in policyholder money. Price to book: <b>${((r.insurer||{}).pb||0).toFixed(2)}×</b> (book value $${((r.insurer||{}).bv_ps||0).toFixed(2)} a share).</p>`:""}`:"";
 const val=`<div class="snaphd"><b>Valuation</b><span class="muted">Is it a good price?</span><span class="badge ${BANDS[r.status][1]}" style="margin-left:auto">${BANDS[r.status][0]}</span></div>
 <div class="vstrip"><div class="vbar"><span class="vband" style="left:${X(r.bear)};width:calc(${X(r.bull)} - ${X(r.bear)})"></span><span class="vbb" style="left:${X(r.buy_below)}" title="Buy below ${$f(r.buy_below)}"></span><span class="vfv" style="left:${X(r.fair_value)}"></span><span class="vpx ${r.diff>0?"bad":"good"}" style="left:${X(px)}" title="Price ${$f(px)}"></span></div>
  <div class="vlab"><span style="left:${X(r.bear)}">Bear ${$f(r.bear)}</span><span style="left:${X(r.fair_value)}"><b>FV ${$f(r.fair_value)}</b></span><span style="left:${X(r.bull)}">Bull ${$f(r.bull)}</span></div></div>
 <p class="vline">Price <b>${$f(px)}</b> is <b class="${r.diff>0?"down":"up"}">${Math.abs(r.diff*100).toFixed(0)}% ${r.diff>0?"above":"below"}</b> fair value · buy below ${$f(r.buy_below)} (${(r.mos*100).toFixed(0)}% margin of safety)</p>
 <div class="vstats"><div><span>Chance value > price</span><b>${pA==null?"–":(pA*100).toFixed(0)+"%"}</b></div><div><span>10-yr return (median)</span><b>${h10==null?"–":(h10*100).toFixed(1)+"%"}</b></div>
  ${INS(r)?`<div><span>ROE priced in (long run)</span><b>${(r.insurer||{}).roe_needed==null?"–":((r.insurer.roe_needed)*100).toFixed(1)+"%"}</b></div><div><span>Price to book</span><b>${((r.insurer||{}).pb||0).toFixed(2)}×</b></div>`:`<div><span>Growth priced in (year 1)</span><b>${r.reverse_g1==null?"–":(r.reverse_g1>0?"+":"")+(r.reverse_g1*100).toFixed(0)+"%"}</b></div>`}<div><span>No-growth value (EPV)</span><b>${r.epv?$f(r.epv):"–"}</b></div></div>`;
 const mult=vt?`<div class="snaphd"><b>Multiples vs history</b><span class="muted">Trailing P/E, EV/EBITDA and FCF yield against its own past years and its sector</span></div>${vt}`:"";
 // what to watch: the two biggest drivers (not the required return)
 let watch="";if(r.mc&&r.mc.tornado&&r.scenarios&&r.scenarios.base){const b=r.scenarios.base,addb=r.wacc&&r.rev?(r.wacc.after_tax_interest||0)/r.rev:0,pc=x=>(x*100).toFixed(1).replace(".0","")+"%";
  const KEY=l=>l.startsWith("Year-1")?"g1":l.startsWith("Target")||/return on equity/.test(l)?"m":l.startsWith("Long-run")?"g10":l.startsWith("Terminal")?"gt":null;
  const items=r.mc.tornado.rows.filter(o=>!o.choice).slice(0,2).map(o=>{const k=KEY(o.label),base=k==="g1"?b.g1:k==="g10"?b.g10:k==="m"?b.m+addb:0.025;
   const check=INS(r)?(k==="g1"?`Each quarter: is book value per share (plus dividends paid) growing near ${pc(base)} a year?`:k==="m"?`Each quarter: net income ÷ book value at the start of the year, vs ${pc(base)}. Watch the combined ratio and reserve changes, which drive it.${(r.insurer||{}).roe_needed!=null?` Today's price needs about ${pc(r.insurer.roe_needed)} for good.`:""}`:k==="g10"?"Yearly: is the business still growing premiums without cutting prices?":"Mostly the economy and inflation; little to check quarter to quarter."):k==="g1"?`Each quarter: is revenue growing near ${pc(base)} a year?${r.reverse_g1!=null?` Today's price needs about ${pc(r.reverse_g1)}.`:""}`:k==="m"?`Each quarter: free cash flow minus stock pay${addb>0.0005?" (plus after-tax interest)":""}, as a share of revenue, vs ${pc(base)}.`:k==="g10"?"Yearly: is the market still growing and is the company holding its share?":"Mostly the economy and inflation; little to check quarter to quarter.";
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
 return {top:flags+covHTML(r),post:[perfHTML(r,px,"post"),q,driversHTML(DR),sectorHTML(r),mult,fh],ante:[val,perfHTML(r,px,"ante"),watch]}}
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
 const v=(ms,n=2)=>ms.filter(m=>!m.na).map(m=>`${m.label.replace(" (YoY)","").replace(" (3 years combined)","")}: <b>${esc(m.value)}</b>`).join(" · ");
 const R=sgrade(t,["Revenue growth, latest quarter","Revenue growth, 3-year CAGR"]),C=sgrade(t,["FCF margin trend","Operating margin trend","FCF / net income"]);
 const B=sgrade(t,["Net debt / EBITDA","Interest coverage","Debt ÷ (debt + book value)"]),M=sgrade(t,["ROIC vs cost of capital","ROIC above cost of capital","Gross margin trend","ROE vs required return","ROE above required return"]);
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
const MY0={h:null,max:0.10,eq:0.35,hz:null,lb:0.02,pl:0.10};let MY={...MY0};try{MY={...MY0,...JSON.parse(localStorage.getItem("my")||"{}")}}catch(e){}
rows.forEach(r=>{r.fv0=r.fair_value;r.bb0=r.buy_below});
const pc1=x=>(x*100).toFixed(1).replace(".0","")+"%";
function hurdleOf(r){return MY.h==null?r.required_return:MY.h}
function applyHurdle(){rows.forEach(r=>{let fv=r.fv0;
  if(MY.h!=null&&r.rate_table){const x=r.rate_table.find(x=>Math.abs(x.r-MY.h)<1e-9);if(x)fv=x.fv}
  r.fair_value=fv;r.buy_below=MY.h!=null&&r.rate_table?fv*(1-r.mos):r.bb0;r.diff=r.price/fv-1;r.status=status(r)})}
// Yearly return from buying at today's price and holding (Monte Carlo, Bear/Base/Bull 30/50/20): median, p10, p90
function retDist(r){const M=r.mc;if(!M||!M.irr||r.price==null)return null;const I=M.irr,m=r.price/I.fair_value,hk=MY.hz==null?"regimes":"hold"+MY.hz,ir=irrAt(I,m,I[hk]?hk:"regimes"),X=mix(ir.Q,A.probabilities);
  return {med:X.inv(.5),p10:X.inv(.1),p90:X.inv(.9),inside:ir.inside,F:X.F}}
// Size ("Risk to you": Durand's Whitworth, Bernoulli and Cramer adjustments; none of them changes a fair value).
//  1 Return:   max position x edge x confidence. Edge = median yearly return above your hurdle, full at +5 points (FULL_EDGE);
//              confidence = chance the return beats your hurdle, 0 at 50% rising to 1 at 90%. Zero above fair value.
//  2 Whitworth (affordable risk) + Bernoulli (your situation): at most your loss budget / the bad-case drop, so one bad
//              idea costs at most the budget. Bad-case drop = price to the Monte Carlo 10th-percentile value, at least
//              DROP_FLOOR because prices can fall far below value in a crash even when the model is right.
//  3 Cramer (diminishing utility): bigger upside never buys more than the max position, no theme above THEME_CAP of the
//              portfolio, and all sizes scale down together if they add up to more than your stock share.
const FULL_EDGE=0.05,DROP_FLOOR=0.35,THEME_CAP=0.25;
function badDrop(r){const M=r.mc,v=M&&M.p10>0&&r.price?M.p10*(r.fair_value/r.fv0):null,model=v==null?null:1-v/r.price;
  return {v,model,drop:Math.max(DROP_FLOOR,model??0),floor:model==null||model<DROP_FLOOR}}
function sizeAll(){const raw={};rows.forEach(r=>{r.sz=null;r.size=null;if(r.type!=="stock"&&r.type!=="etf")return;const d=retDist(r);if(!d)return;
  const h=hurdleOf(r),ex=d.med-h,pb=1-d.F(h),edge=Math.min(1,Math.max(0,ex/FULL_EDGE)),conf=Math.min(1,Math.max(0,(pb-0.5)/0.4)),k0=r.diff<0?MY.max*edge*conf:0;
  const bd=badDrop(r),kL=MY.lb/bd.drop,k=Math.min(k0,kL),lim=k0<=0?null:kL<k0?"loss":edge*conf>=1?"max":"return";
  r.sz={d,h,ex,pb,edge,conf,k0,kL,k,bd,lim,ts:1,theme:null};raw[r.ticker]=k});
  const ts={},tn={};for(const [th,L] of Object.entries(TH)){if(!Array.isArray(L))continue;const tot=L.reduce((a,t)=>a+(raw[t]||0),0);
    if(tot>THEME_CAP)L.forEach(t=>{if(raw[t]>0&&THEME_CAP/tot<(ts[t]??1)){ts[t]=THEME_CAP/tot;tn[t]=th}})}
  for(const t in ts)raw[t]*=ts[t];
  const tot=Object.values(raw).reduce((a,b)=>a+b,0),sc0=tot>MY.eq?MY.eq/tot:1;let loss=0;
  // Whitworth for the whole portfolio: stocks fall together in a crash, so if every suggested position hit its bad case at
  // once and that would cost more than your portfolio loss limit, all positions scale down together.
  const L0=rows.reduce((a,r)=>a+(raw[r.ticker]>0?raw[r.ticker]*sc0*r.sz.bd.drop:0),0),pls=MY.pl!=null&&L0>MY.pl?MY.pl/L0:1,sc=sc0*pls;
  rows.forEach(r=>{if(raw[r.ticker]==null)return;const z=r.sz;r.size=raw[r.ticker]*sc;z.scale=sc0;z.pls=pls;
    if(ts[r.ticker]){z.ts=ts[r.ticker];z.theme=tn[r.ticker];if(r.size>0)z.lim="theme"}   // the stock-share scaling hits every position alike, so it is shown once (summary, KPI) rather than as the limit
    z.loss=r.size*z.bd.drop;loss+=z.loss});
  const byTh=Object.entries(TH).filter(([,L])=>Array.isArray(L)).map(([th,L])=>[th,L.reduce((a,t)=>a+((rows.find(x=>x.ticker===t)||{}).size||0),0)]).sort((a,b)=>b[1]-a[1]);
  SZ={tot:tot*sc,n:Object.values(raw).filter(x=>x>0).length,scaled:sc0<1,plScaled:pls<1,pls,loss,theme:byTh[0]&&byTh[0][1]>0?byTh[0]:null};return SZ}
const LIM={return:"Expected return",max:"Max position",loss:"Loss budget",theme:"Theme cap"};
// Moat scorecard (scripts/moat_scorecard.py): question 4. Never changes the class in data/moat.json.
function moatHTML(r){const x=(MS.stocks||{})[r.ticker];if(r.type!=="stock"||!x)return "";
 const N={n:"Network effects",s:"Switching costs",i:"Brand, patents, licences",c:"Cost advantage",e:"Efficient scale"},L=["none","some","strong"];
 const dots=v=>`<span class="mdots">${[0,1].map(i=>`<i class="${i<v?"on":""}"></i>`).join("")}</span> ${L[v]}`;
 const P=x.parts||{},pp=(v,m)=>v==null?`<span class="unk">unknown</span>`:`${(+v).toFixed(1).replace(".0","")} / ${m}`;
 const verdict=x.suggested==null?`No class is suggested: the filings can't measure returns on capital, and an unknown never counts as positive. The model uses <b>${MOATN[x.current]||x.current}</b>.`:x.differs?`The scorecard suggests <b>${MOATN[x.suggested]}</b>, but the model uses <b>${MOATN[x.current]}</b>. That's worth a look; edit data/moat.json to change it, which moves the fair value.`:`This agrees with the model's ${MOATN[x.current]||x.current}.`;
 return `<h3>How durable is the edge?</h3><p><b>${x.total.toFixed(1)} / ${x.out_of||10}</b>: ${x.source_score.toFixed(1)} from the sources of advantage, ${x.numbers_score==null?`the filings half <span class="unk">unknown, not scored</span>`:x.numbers_score.toFixed(1)+" from the filings"+((x.unknown||[]).length?` (${x.unknown.map(k=>k==="new_money"?"returns on new money":"gross margin").join(" and ")} unknown, scored 0)`:"")}. ${verdict}</p>
 <div class="scroll"><table class="s rq"><tr><th style="text-align:left">Source of advantage</th><th style="text-align:left">Strength</th></tr>${Object.keys(N).map(k=>`<tr><td style="text-align:left">${N[k]}</td><td style="text-align:left">${dots(x.sources[k])}</td></tr>`).join("")}
 <tr><td style="text-align:left">Main evidence</td><td style="text-align:left">${x.why}${x.src?` (<a href="${x.src}" target="_blank" rel="noopener">source</a>)`:""}</td></tr>
 <tr><td style="text-align:left">Main threat</td><td style="text-align:left">${x.risk}</td></tr></table></div>
 ${x.numbers_score!=null?`<p class="muted">From the filings: returns well above the hurdle in past years ${pp(P.persistence,2)}, no fade ${pp(P.fade,1)}, returns on new money ${pp(P.new_money,1)}, steady gross margin ${pp(P.margins,1)}${P.gm_std!=null?` (typical swing ${(P.gm_std*100).toFixed(1)} pts)`:""}.</p>`:""}
 <p class="muted">The sources are Claude's judgement as of ${MS.checked}, re-checked after each earnings report. 7.5+ suggests a wide moat, 5+ narrow.</p>`}
// ---------- Rating: Excellent / Good / Average / Bad from three pillars, each scored 0-2 (Weak / OK / Strong).
// Uses only what the drawer already shows; follows My hurdle (fair value, buy-below and bear case move with it). Not advice.
const RT={iv_cheap:0.10,iv_dear:0.10,qcards:["Earnings","Cash flow","Business performance","Financial strength"]};
const RTL=["Weak","OK","Strong"],RTC=["g-w","g-o","g-s"];
function ratingOf(r){if(r.type!=="stock"||r.price==null||!r.fair_value)return null;
 const S=(SN.stocks||{})[r.ticker];if(!S)return null;
 const px=r.price,fv=r.fair_value,$f=x=>"$"+x.toFixed(2),p0=x=>(Math.abs(x)*100).toFixed(0)+"%";
 // 1. Intrinsic value: price against the base fair value
 const d=px/fv-1,iv=px<=fv*(1-RT.iv_cheap)?2:px<=fv*(1+RT.iv_dear)?1:0;
 const ivW=`Price ${$f(px)} is ${p0(d)} ${d<=0?"below":"above"} the ${$f(fv)} fair value`+(iv===2?` (${p0(RT.iv_cheap)} or more below)`:iv===1?` (within ${p0(RT.iv_dear)})`:` (more than ${p0(RT.iv_dear)} above)`)+".";
 // 2. Margin of safety: cushion if the estimate is wrong (buy-below = fair value less the margin; bear case at the same rate)
 const h=hurdleOf(r),rw=r.rate_table&&r.rate_table.find(x=>Math.abs(x.r-h)<1e-9),bear=rw&&rw.bear!=null?rw.bear:r.bear,half=fv*(1-r.mos/2);
 const ms=px<=r.buy_below||px<=bear?2:px<=half?1:0;
 const msW=ms===2?(px<=r.buy_below?`At or below the ${$f(r.buy_below)} buy-below price: the full ${p0(r.mos)} margin of safety.`:`Below the ${$f(bear)} bear case: even the pessimistic scenario covers the price.`)
  :ms===1?`Below ${$f(half)} (fair value less half the ${p0(r.mos)} margin), but above the ${$f(r.buy_below)} buy-below price.`
  :`Above ${$f(half)}, so less than half the ${p0(r.mos)} margin of safety is left${px>fv?" (no cushion at all)":""}.`;
 // 3. Business quality: four quality cards (price not included) plus the moat class the model uses
 const C=S.cards.filter(c=>RT.qcards.includes(c.title)&&c.grade in {Strong:1,OK:1,Weak:1}&&cardAns(c).enough),g=C.map(c=>({Strong:2,OK:1,Weak:0})[c.grade]);
 if(g.length<3)return null;
 const av=g.reduce((a,b)=>a+b,0)/g.length,nw=g.filter(x=>x===0).length,moat=r.moat==="wide"||r.moat==="narrow";
 const q=av>=1.5&&nw===0&&moat?2:av<1||nw>=2?0:1;
 const qW=`<span class="rtq">${C.map(c=>`<span>${c.title}<span class="gr ${GC[c.grade]}"><i></i>${c.grade}</span></span>`).join("")}<span>Moat<span class="gr ${moat?"g-s":"g-n"}"><i></i>${r.moat||"not set"}</span></span></span>`+
  (q===2?"Mostly Strong, nothing Weak, and a lasting edge.":q===0?(nw>=2?`${nw} cards are Weak.`:"More Weak than Strong across the cards."):
   [av<1.5?"not mostly Strong":"",nw?"one card is Weak":"",!moat?"no wide or narrow moat":""].filter(Boolean).join(", ").replace(/^./,c=>c.toUpperCase())+": not enough for Strong.");
 const tot=iv+ms+q,lab=q===2&&tot>=5?0:tot>=3&&q>=1&&iv>=1?1:tot<=1?3:2;
 const why=lab===0?"Strong business, priced well below fair value, with a cushion."
  :lab===1?"At least OK on quality and price, and 3+ points in all."
  :lab===3?"1 point or less: paying too much for what the business is."
  :q===0&&tot>=3?"Cheap enough for Good, but a Weak business is held to Average (value-trap risk)."
  :iv===0?"Good business, but the price is more than "+p0(RT.iv_dear)+" above fair value."
  :q===0?"Weak business: the discount alone is not enough."
  :"OK business at about fair value, with little cushion.";
 return {lab,tot,why,P:[["Intrinsic value","Is the price below what the business is worth?",iv,ivW],["Margin of safety","Is there a cushion if the estimate is wrong?",ms,msW],["Business quality","Is it a good company?",q,qW]]}}
const RATE=[["Excellent","rt-ex"],["Good","rt-gd"],["Average","rt-av"],["Bad","rt-bd"]];
function ratingHTML(r){const x=ratingOf(r);if(!x)return "";
 return `<div class="rating"><div class="rth"><span class="rtb ${RATE[x.lab][1]}">${RATE[x.lab][0]}</span><span class="rtp">${x.tot} of 6 points</span><span class="muted">${x.why}</span></div>
 <div class="rtg">${x.P.map(p=>`<div class="rtc"><div class="rtt"><b>${p[0]}</b><span class="gr ${RTC[p[2]]}"><i></i>${RTL[p[2]]} · ${p[2]}</span></div><div class="muted">${p[1]}</div><div>${p[3]}</div></div>`).join("")}</div>
 <details class="rtrule"><summary>How the rating works</summary><p>Each pillar scores 0 (Weak), 1 (OK) or 2 (Strong); the rating adds them up, out of 6.</p>
 <ul class="rk"><li><b>Intrinsic value</b>: Strong at ${p0r(RT.iv_cheap)} or more below fair value, OK within ${p0r(RT.iv_dear)} either side, Weak above that.</li>
 <li><b>Margin of safety</b>: Strong at or below the buy-below price (fair value less the stock's margin of safety) or below the bear case; OK below fair value less half the margin; Weak otherwise.</li>
 <li><b>Business quality</b>: the Earnings, Cash flow, Business performance and Financial strength cards (Strong 2, OK 1, Weak 0). Strong = average 1.5+, no Weak card, and a wide or narrow moat. Weak = average below 1 or two Weak cards. OK otherwise.</li></ul>
 <p>Excellent: 5-6 points with Strong quality. Good: 3+ points, quality and intrinsic value at least OK. Bad: 0-1 points. Average: everything else. Prices are live and fair values follow My hurdle, so the rating can change during the day. Not investment advice.</p></details></div>`}
const p0r=x=>(x*100).toFixed(0)+"%";
// Returns on capital over ~10 years of 10-Ks (scripts/returns_history.py): questions 1, 2 and 5. Diagnostics only.
function retHTML(r){const x=(RH.stocks||{})[r.ticker],h=retHTML0(r);if(!x||x.measure!=="ROE"||!h)return h;
 return h.replace("Return on invested capital by year","Return on equity by year").replace(/Return on invested capital each year \(10-K figures, capped at 200% on the chart; the dashed line is the ([^)]*) required return\)\. Invested capital includes goodwill, so acquirers look lower than the businesses they bought\./,"Return on equity each year (net income ÷ book value at the start of the year, 10-K figures; the dashed line is the $1 required return). For an insurer, equity is the capital that backs its policies, so return on equity is the measure of its edge.")
  .replace(/invested capital/g,"book value").replace(/return on capital/g,"return on equity").replace(/on all capital/g,"on all equity").replace(/after-tax operating profit/g,"net income").replace(/capital added/g,"book value added").replace(/new capital/g,"new equity")}
function retHTML0(r){const x=(RH.stocks||{})[r.ticker];if(r.type!=="stock"||!x)return "";
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
// Advantage over bonds and profit durability (scripts/durability.py -> data/durability.json). Information only.
// ---------- Research framework blocks (scripts/framework.py -> data/framework.json). Information only, no fair value changes.
// Unanswered is never positive: an unknown answer is grey, "not scored", and never counts toward a grade.
const fwOf=t=>(FW.stocks||{})[t];
const sp1=(x,d=1)=>x==null?"–":(x>=0?"+":"−")+Math.abs(x*100).toFixed(d)+"%";
const UNK=(t="Unknown, not scored")=>`<span class="unk">${t}</span>`;
const TONE={good:"up",bad:"down",caution:"warn",key:"key"};
const mon=d=>{if(!d)return "";const m=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+d.slice(5,7)-1];return m+" "+d.slice(0,4)};
function h10Of(r,px){if(!r.mc||!r.mc.regimes||!r.mc.irr||!r.mc.irr.hold10||px==null)return null;const Q={};KS.forEach(k=>Q[k]=r.mc.regimes[k].quantiles);
 const w={bear:A.probabilities.bear,base:A.probabilities.base,bull:A.probabilities.bull},hr=irrAt(r.mc.irr,px/r.mc.irr.fair_value,"hold10");return mix(hr.Q,w).inv(.5)}
function cardAns(c){const ms=(c.metrics||[]).filter(m=>!m.na),bad=v=>v==null||v===""||v==="–"||/not in free data/i.test(String(v));const miss=ms.filter(m=>bad(m.value)).map(m=>m.label);
 return {n:ms.length,a:ms.length-miss.length,miss,enough:!ms.length||(ms.length-miss.length)*2>=ms.length}}
function ansLine(c){const x=cardAns(c);if(!x.n)return "";return `<span class="ans">${x.a} of ${x.n} answered${x.miss.length?` · ${x.miss.map(l=>esc(l.toLowerCase())).join(", ")} ${UNK("unknown")}`:""}</span>`}
function covHTML(r){const x=fwOf(r.ticker);if(!x||!x.coverage)return "";const c=x.coverage,w=v=>(v/c.total*100).toFixed(1)+"%",Qs=FW.questions||{};
 const list=st=>c.fixed.filter(f=>f[1]===st).map(f=>`<li>${esc(Qs[f[0]]||f[0])}</li>`).join("")+(st==="unknown"?((x.sector||{}).questions||[]).filter(q=>q.answer==null).map(q=>`<li>${esc(q.q)} <span class="muted">(${esc(x.sector.module)})</span></li>`).join(""):"");
 return `<details class="cov"><summary><b>Answered ${c.answered} of ${c.total}</b> <span class="muted">· ${c.partly} partly · ${c.unknown} unknown, not scored${c.na?` · ${c.na} not applicable`:""}</span>
  <span class="covbar" aria-hidden="true"><i style="width:${w(c.answered)};background:var(--good)"></i><i style="width:${w(c.partly)};background:color-mix(in srgb,var(--warn) 45%,var(--line))"></i><i style="width:${w(c.unknown)};background:color-mix(in srgb,var(--mut) 30%,var(--line))"></i></span>
  <span class="covwhich">which ones?</span></summary>
  <div class="covlist"><div><b>Partly answered</b><ul>${list("partly")}</ul></div><div><b>Unknown, not scored</b><ul>${list("unknown")}</ul></div>${c.na?`<div><b>Not applicable to this business</b><ul>${list("na")}</ul></div>`:""}</div>
  <p class="muted">The 64 questions every stock gets (valuation vs bonds, growth, advantage, cash flow, capital allocation, risk, market performance, what the price assumes, duration) plus the questions for its type of business. An unknown is never counted as good${c.na?`; questions that don't apply (for an insurer: free-cash-flow and debt-to-EBITDA tests) are left out of the total`:""}.</p></details>`}
function perfHTML(r,px,part){const x=fwOf(r.ticker);if(!x||(!x.business&&!x.market))return "";const b=x.business||{},m=x.market||{},a=x.assumes||{},sp=x.split;
 const row=(l,v)=>`<div class="r"><span>${l}</span>${v}</div>`,B=v=>v==null?UNK("–"):`<b>${sp1(v)}</b>`;
 const bm=(o,lab)=>o&&o.ytd!=null&&m.ytd!=null?row(`vs ${lab} YTD`,`<b class="${m.ytd>=o.ytd?"up":"down"}">${(m.ytd-o.ytd>=0?"+":"−")+Math.abs((m.ytd-o.ytd)*100).toFixed(1)} pts</b>`):row(`vs ${lab}`,UNK("not loaded yet"));
 const g1=a.g1_needed!=null?a.g1_needed:r.reverse_g1,bg=a.base_g1!=null?a.base_g1:(r.scenarios&&r.scenarios.base?r.scenarios.base.g1:null),cap=a.cap_needed!=null?a.cap_needed:r.implied_cap;
 const asks=g1!=null&&bg!=null&&g1>bg+0.02;
 let split="";if(sp){const lp=Math.log(1+sp.price),le=Math.log(1+sp.eps);
  const why=sp.price>0&&sp.eps<=0?"The rise came from a higher P/E while earnings fell.":sp.price>0&&le>=0.67*lp?"The rise came mostly from earnings, not a higher multiple.":sp.price>0&&sp.pe>sp.eps?"Most of the rise came from a higher P/E, not from earnings.":sp.price>0?"Earnings and a higher P/E both added to the rise.":sp.eps>0?"Earnings grew but the P/E fell by more.":"Earnings and the P/E both fell.";
  split=`<p class="psplit">Fiscal year to ${mon(sp.fy)}: price <b>${sp1(sp.price)}</b> = EPS <b>${sp1(sp.eps)}</b> and P/E <b>${sp1(sp.pe)}</b> (${sp.pe0} → ${sp.pe1}). ${why}</p>`}
 const pin=INS(r)?`<div class="${a.m_needed!=null&&a.m_needed>a.base_m+0.02?"cr":""}"><h4>Priced in</h4><div class="psub">At the ${(r.required_return*100).toFixed(1)}% required return</div>${row("Long-run ROE",a.m_needed==null?UNK("–"):`<b>${(a.m_needed*100).toFixed(1)}%</b>`)}<div class="psub">model base case: ${a.base_m==null?"–":(a.base_m*100).toFixed(1)+"%"}</div>
  ${row("Price to book",a.pb==null?UNK("–"):`<b>${a.pb.toFixed(2)}×</b>`)}<div class="psub">book value $${a.bv_ps==null?"–":a.bv_ps.toFixed(2)} a share</div></div>`:`<div class="${asks?"cr":""}"><h4>Priced in</h4><div class="psub">At the ${(r.required_return*100).toFixed(1)}% required return</div>${row("Year-1 sales growth",g1==null?UNK("–"):`<b>${(g1*100).toFixed(0)}%</b>`)}<div class="psub">model base case: ${bg==null?"–":(bg*100).toFixed(0)+"%"}</div>
  ${row("Edge must last",cap==null?UNK("–"):`<b>${cap>80?"80+":cap} years</b>`)}<div class="psub">${MOATN[r.moat]||"model"}: ${r.cap_years||"–"} years</div></div>`;
 if(part==="ante")return `<div class="snaphd"><b>Market expectations</b><span class="muted">What today's price needs from the business</span></div><div class="perf perf1">${pin}</div>`;
 return `<div class="snaphd"><b>Two performances</b><span class="muted">Did the business keep up with the stock?</span></div><div class="perf perf2">
 <div><h4>Business</h4><div class="psub">Fiscal year to ${mon(b.fy)} vs the year before</div>${row("Sales",B(b.sales))}${row("EPS",B(b.eps))}${row("Free cash flow",B(b.fcf))}</div>
 <div><h4>Market</h4><div class="psub">Share price</div>${row("Year to date",B(m.ytd))}${row("with dividends",B(m.ytd_total))}${row("1 · 3 · 5 yrs",`<b>${[m.y1,m.y3,m.y5].map(v=>v==null?"–":sp1(v,0)).join(" · ")}</b>`)}${bm(m.spy,"S&amp;P 500")}${bm(m.sector,"its sector")}</div></div>${split}`}
function sectorHTML(r){const x=fwOf(r.ticker);if(!x||!x.sector)return "";const S=x.sector;
 return `<div class="snaphd"><b>Sector questions</b><span class="muted">${esc(S.module)}</span></div><div class="scroll"><table class="s sp"><tr><th>Question</th><th class="n">Answer</th><th>Reading</th></tr>
 ${S.questions.map(q=>`<tr><td>${esc(q.q)}</td><td class="n">${q.answer==null?UNK():`<span class="${TONE[q.tone]||"key"}">${esc(q.answer)}</span>`}</td><td class="muted">${q.answer==null?"not in our data":esc(q.reading||"")}</td></tr>`).join("")}</table></div>
 <p class="muted">Questions for this type of business, answered from the annual statements where they can be. Unknowns need company disclosures we don't collect; they are never scored.</p>`}
function spreadsHTML(r,part){const x=fwOf(r.ticker),b=x&&x.bonds;if(!b)return "";const h=h10Of(r,r.price),hr=hurdleOf(r),f=v=>v==null?"–":v.toFixed(2)+"%";
 const g1=v=>v==null?"–":`<span class="${v<0?"down":v<3?"warn":"up"}">${(v>=0?"+":"−")+Math.abs(v).toFixed(2)}</span>`,
  g2=v=>v==null?UNK("–"):`<span class="${v<0?"down":"warn"}">${(v>=0?"+":"−")+Math.abs(v).toFixed(1)}</span>`;
 const ey=b.ey,er=h==null?null:h*100;
 if(part==="ante")return `<div class="scroll"><table class="s sp"><tr><th>Spread</th><th class="n">Stock</th><th class="n">Bond or hurdle</th><th class="n">Gap, pts</th></tr>
 <tr><td><b>Growth-adjusted spread</b><span class="ftag est">estimate</span><div class="muted">expected 10-year return − 10-year yield</div></td><td class="n">${er==null?UNK("–"):er.toFixed(1)+"% a year"}</td><td class="n">10-year ${f(b.t10)}</td><td class="n">${g2(er!=null&&b.t10!=null?er-b.t10:null)}</td></tr>
 <tr><td><b>Intrinsic-value spread</b><span class="ftag est">estimate</span><div class="muted">expected return − your hurdle</div></td><td class="n">${er==null?UNK("–"):er.toFixed(1)+"% a year"}</td><td class="n">hurdle ${(hr*100).toFixed(1)}%</td><td class="n">${g2(er!=null?er-hr*100:null)}</td></tr></table></div>
 <p class="muted">Expected return = median 10-year return at today's price from the Monte Carlo (the tile under Valuation), so the horizon matches the 10-year bond. Both rows are model estimates, never marked green, and follow My settings. Bond yields ${b.month||""} monthly averages from FRED.</p>`;
 return `<div class="scroll"><table class="s sp"><tr><th>Spread</th><th class="n">Stock</th><th class="n">Bond or hurdle</th><th class="n">Gap, pts</th><th class="n">Usual</th></tr>
 <tr><td><b>Current earnings spread</b><span class="ftag fact">fact</span><div class="muted">earnings yield − bond yield</div></td><td class="n">${f(ey)}</td>
  <td class="n">Aaa ${f(b.aaa)}<br>10-year ${f(b.t10)}<br>10-year real (TIPS)${b.tips!=null?" "+f(b.tips):""}</td><td class="n">${g1(ey!=null&&b.aaa!=null?ey-b.aaa:null)}<br>${g1(ey!=null&&b.t10!=null?ey-b.t10:null)}<br>${b.tips!=null&&ey!=null?g1(ey-b.tips):UNK("not loaded yet")}</td><td class="n">${b.median_gap==null?"–":(b.median_gap>=0?"+":"−")+Math.abs(b.median_gap).toFixed(2)}<br><br></td></tr>
</table></div>
 <p class="muted">Earnings yield = trailing EPS ÷ today's price. All in ${esc(x.currency||"USD")}; bond yields ${b.month||""} monthly averages from FRED. The earnings yield is close to a real yield, since earnings rise with inflation, so the TIPS line is the like-for-like comparison.</p>`}
function assumesHTML(r){const x=fwOf(r.ticker),a=x&&x.assumes;if(!a)return "";const px=r.price,$f=v=>v==null?"–":"$"+(v>=1000?v.toFixed(0):v.toFixed(2)),pc=v=>v==null?"–":(v*100).toFixed(1).replace(".0","")+"%";
 const vs=v=>v==null||!px?"":`<span class="${v>=px?"warn":"down"}">${sp1(v/px-1,0)}</span>`,rows=[];
 const row=(l,n,b,v)=>rows.push(`<tr><td>${l}</td><td class="n">${n}</td><td class="n">${b}</td><td class="n">${v}</td></tr>`);
 if(a.method==="excess_roe"){
 row("Book value growth needed in year 1",a.g1_needed==null?UNK("–"):`<span class="${a.g1_needed>a.base_g1+0.02?"warn":"key"}">${pc(a.g1_needed)}</span>`,pc(a.base_g1),"");
 row("Long-run ROE needed",a.m_needed==null?UNK("–"):`<span class="${a.m_needed>a.base_m+0.02?"warn":"key"}">${pc(a.m_needed)}</span>`,pc(a.base_m),"");
 if(a.half_value!=null)row(`If book growth is half that (${pc(a.half_g1)})`,$f(a.half_value),"",vs(a.half_value));
 if(a.pb!=null)row("Price to book",`${a.pb.toFixed(2)}×`,`$${(a.bv_ps||0).toFixed(2)} book a share`,"");
 if(a.pe_sector&&a.eps_ttm>0)row(`If P/E falls to the sector median (${a.pe_sector})`,$f(a.pe_sector*a.eps_ttm),"",vs(a.pe_sector*a.eps_ttm));
 row("Bear / base / bull value",`${$f(r.bear)} / ${$f(r.base)} / ${$f(r.bull)}`,"",[r.bear,r.base,r.bull].map(vs).join(" "));
 if(a.cap_needed!=null)row("Years of excess ROE the price needs vs the moat class",`${a.cap_needed>80?"80+":a.cap_needed} years`,`${r.cap_years||"–"} years`,a.cap_needed>(r.cap_years||0)?`<span class="down">not covered</span>`:"covered");
 return `<h3>What the price assumes</h3><div class="scroll"><table class="s sp"><tr><th>At ${$f(a.price)} and a ${(a.r*100).toFixed(1)}% required return</th><th class="n">Needed or result</th><th class="n">Model base</th><th class="n">vs today's price</th></tr>${rows.join("")}</table></div>
 <p class="muted">Same book value and ROE model as the fair value, base case unless stated. Growth and ROE needed solve the model for today's price. Estimates, not forecasts; nothing here changes the fair value.</p>`}
 row("Sales growth needed in year 1",a.g1_needed==null?UNK("–"):`<span class="${a.g1_needed>a.base_g1+0.02?"warn":"key"}">${pc(a.g1_needed)}</span>`,pc(a.base_g1),"");
 row("Cash margin needed at base growth",a.m_needed==null?UNK("–"):`<span class="${a.m_needed>a.base_m+0.02?"warn":"key"}">${pc(a.m_needed)}</span>`,pc(a.base_m),"");
 if(a.half_value!=null)row(`If growth is half that (${pc(a.half_g1)})`,$f(a.half_value),"",vs(a.half_value));
 if(a.pe_sector&&a.eps_ttm>0)row(`If P/E falls to the sector median (${a.pe_sector})`,$f(a.pe_sector*a.eps_ttm),"",vs(a.pe_sector*a.eps_ttm));
 if(a.pe_own&&a.eps_ttm>0)row(`If P/E goes back to its own median (${a.pe_own}, ${a.pe_own_years})`,$f(a.pe_own*a.eps_ttm),"",vs(a.pe_own*a.eps_ttm));
 row("Bear / base / bull value",`${$f(r.bear)} / ${$f(r.base)} / ${$f(r.bull)}`,"",[r.bear,r.base,r.bull].map(vs).join(" "));
 if(a.cap_needed!=null)row("Edge the price needs vs the moat class",`${a.cap_needed>80?"80+":a.cap_needed} years`,`${r.cap_years||"–"} years`,a.cap_needed>(r.cap_years||0)?`<span class="down">not covered</span>`:"covered");
 return `<h3>What the price assumes</h3><div class="scroll"><table class="s sp"><tr><th>At ${$f(a.price)} and a ${(a.r*100).toFixed(1)}% required return</th><th class="n">Needed or result</th><th class="n">Model base</th><th class="n">vs today's price</th></tr>${rows.join("")}</table></div>
 <p class="muted">Same cash-flow model as the fair value, base case unless stated. Growth and margin needed solve the model for today's price; the P/E rows use trailing EPS${a.sector?` and the median P/E of ${esc(a.sector)} stocks in the latest growth screen`:""}. Estimates, not forecasts; nothing here changes the fair value.</p>`}
// ---------- Can it pay its debts in a bad year? (scripts/debt_stress.py -> data/debt_stress.json). Information only.
function debtHTML(r){const x=(DS.stocks||{})[r.ticker];if(r.type!=="stock"||!x)return "";
 if(x.insurer)return `<h3>Can it pay its debts in a bad year?</h3><p class="muted">Not tested here. An insurer's risk is in its reserves and capital, not its borrowing: the tests that matter are statutory capital ratios (risk-based capital), reserve adequacy and reinsurance cover in a catastrophe year, which our free data doesn't have. Not scored, and it never counts as a pass. ${UNK()}</p>`;
 if(x.lender)return `<h3>Can it pay its debts in a bad year?</h3><p class="muted">Not tested here: a lender or insurer needs capital-ratio tests (loan losses, capital and liquidity ratios), which our data doesn't have. ${UNK()}</p>`;
 const B=v=>v==null?"–":(v<0?"−$":"$")+Math.abs(v).toFixed(v>=100||v<=-100?0:2)+"B",T=(c,t)=>`<span class="${TONE[c]||"key"}">${t}</span>`,rows=[];
 const row=(q,a,how)=>rows.push(`<tr><td>${q}</td><td class="n">${a}</td><td class="muted">${how}</td></tr>`);
 const q1=x.q1,q2=x.q2,q3=x.q3,q4=x.q4,q5=x.q5,q7=x.q7;
 row("Does bad-year free cash flow cover interest, debt due and dividends?",q1?T(q1.tone,q1.v>=50?"easily":q1.v.toFixed(2)+"×"):UNK(),
  q1?`${B(q1.fcf_b)} cash flow vs ${B(q1.interest_b)} interest + ${q1.due_b==null?`debt due ${UNK("unknown")}`:B(q1.due_b)+" due"} + ${B(q1.div_b)} dividends${q1.due_note==="cash covers all debt"?" (cash covers all debt)":""}`:"not enough data");
 row("Debt vs earnings at the bottom (net debt ÷ bad-year EBITDA)",!q2?UNK():q2.v==null?T("bad","EBITDA below zero"):T(q2.tone,q2.v<0?"net cash":q2.v.toFixed(1)+"×"),q2&&q2.v!=null?`lenders start to worry above 3.5×`:q2?`bad-year EBITDA ${B(q2.ebitda_b)}`:"");
 row(`Interest cover if all debt cost today's ${x.ref?x.ref.name+" yield ("+x.ref.y.toFixed(2)+"%)":"corporate yield"}`,q3?T(q3.tone,q3.v.toFixed(1)+"×"):UNK(),"bad-year operating profit ÷ that interest");
 row("Months the cash on hand covers the gap",q4?T(q4.tone,q4.gap_b<=0?"no gap":q4.v>=999?"999+":q4.v+" months"):UNK(),q4?(q4.gap_b<=0?"cash flow covers it all":`${B(q4.cash_b)} cash vs ${B(q4.gap_b)} a year short`):"");
 row("What it did last time",!q5?UNK():[q5.paid_dividend?(q5.dividend_cut?T("bad","cut the dividend"):T("good","kept the dividend")):"no dividend then",q5.shares==null?"":q5.shares>0.02?T("bad",`shares +${(q5.shares*100).toFixed(0)}%`):T("good","no share issue")].filter(Boolean).join(" · "),q5?`fiscal ${q5.year}`:"no recession year in its filings");
 row("Interest cover at its 10-year median margin",q7?T(q7.tone,q7.v.toFixed(1)+"×"):UNK(),q7?`median operating margin ${(q7.margin*100).toFixed(1)}% over ${q7.years} years`:"");
 row("Credit rating, loan conditions, floating-rate debt",UNK(),"paid data or annual-report text");
 const V={"pays its debts":["ok","Pays its debts"],tight:["warn","Tight"],"at risk":["bad","At risk"]}[x.verdict];
 const ep=x.episode?`Bad year = ${x.estimate?"<b>estimate</b>: ":""}${esc(x.episode)}${x.episode_year?` (fiscal ${x.episode_year})`:""}: revenue ${sp1(x.rev,0)}, operating margin ${x.margin>=0?"+":"−"}${Math.abs(x.margin*100).toFixed(1)} pts${x.ocf_change!=null?`, operating cash flow ${sp1(x.ocf_change,0)}`:""}, applied to fiscal ${x.year.slice(0,4)} and today's debt (${B(x.debt_b)}, cash ${B(x.cash_b)}). Operating profit ${B(x.op_now_b)} → ${B(x.op_stressed_b)}.`:"No recession in its filings and no sector comparison, so it can't be tested.";
 return `<h3>Can it pay its debts in a bad year?</h3><p>${V?`<span class="pill ${V[0]}">${V[1]}</span> `:`<span class="pill">Not enough data</span> `}${ep}</p>
 <div class="scroll"><table class="s sp"><tr><th>Question</th><th class="n">Answer</th><th>How</th></tr>${rows.join("")}</table></div>
 <p class="muted">Pays its debts = bad-year cash flow (or 2+ years of cash) covers interest, debt due and dividends, debt under 3.5× bad-year EBITDA and interest covered 3×+ at today's ${x.ref?x.ref.name:"corporate"} yield. At risk = debt over 5×, cover under 1.5×, or a cash shortfall with under a year of cash. Capex is kept at today's level. An unknown never helps the verdict. Nothing here changes the fair value.</p>`}
function bondHTML(r,part){const x=((DU.stocks||{})[r.ticker]||{}).bond;if(r.type!=="stock"||!x||!x.years||!x.years.length)return "";
 const f=v=>v==null?"–":v.toFixed(2)+"%",pt=v=>v==null?"–":(v>=0?"+":"")+v.toFixed(2)+" pts",ys=x.years.filter(p=>p[1]!=null);if(!ys.length)return "";
 const L={large:["ok","Large advantage"],thin:["warn","Thin advantage"],negative:["bad","No advantage"]}[x.label]||["","–"];
 const W=520,H=150,pl=34,pr=10,pt0=10,pb=20,all=ys.flatMap(p=>[p[1],p[2],p[3]]).filter(v=>v!=null),mx=Math.max(...all,1)*1.08,mn=Math.min(0,...all);
 const X=y=>pl+(y-ys[0][0])/((ys[ys.length-1][0]-ys[0][0])||1)*(W-pl-pr),Y=v=>pt0+(mx-v)/((mx-mn)||1)*(H-pt0-pb);
 const line=(i,c)=>{const q=ys.filter(p=>p[i]!=null);const st={spkl:'stroke="var(--acc)" stroke-width="2"',bdaaa:'stroke="var(--c2)" stroke-width="1.8"',bdt10:'stroke="var(--mut)" stroke-width="1.4" stroke-dasharray="4 3"'}[c];return q.length?`<polyline points="${q.map(p=>X(p[0]).toFixed(1)+","+Y(p[i]).toFixed(1)).join(" ")}" fill="none" ${st} class="${c}"/>`:""};
 const both=ys.filter(p=>p[3]!=null),area=both.length>1?`<polygon fill="var(--acc)" fill-opacity=".12" stroke="none" class="bdgap" points="${both.map(p=>X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1)).concat(both.slice().reverse().map(p=>X(p[0]).toFixed(1)+","+Y(p[3]).toFixed(1))).join(" ")}"/>`:"";
 const tk=[...new Set([mn,(mn+mx)/2,mx].map(v=>Math.round(v)))];
 const svg=`<svg viewBox="0 0 ${W} ${H}" class="mcsvg" role="img" aria-label="Earnings yield against bond yields by year"><title>${ys.map(p=>`${p[0]}: earnings yield ${f(p[1])}, Aaa ${f(p[3])}, 10-year Treasury ${f(p[2])}`).join("\n")}</title>`+
  tk.map(v=>`<text x="${pl-4}" y="${Y(v)+3}" text-anchor="end" class="rtx">${v}%</text>`).join("")+(mn<0?`<line x1="${pl}" x2="${W-pr}" y1="${Y(0)}" y2="${Y(0)}" class="spkref"/>`:"")+
  area+line(2,"bdt10")+line(3,"bdaaa")+line(1,"spkl")+ys.map(p=>`<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="2.6" fill="var(--acc)" class="spkd"/>`).join("")+
  [ys[0][0],ys[ys.length-1][0]].map((y,i)=>`<text x="${X(y)}" y="${H-5}" text-anchor="${i?"end":"start"}" class="rtx">${y}</text>`).join("")+`</svg>`;
 const med=x.gap_median,cmp=med==null||x.gap_now==null?"":x.gap_now>med+1?` That's wider than its usual gap of ${pt(med)} (median of the years shown), so the stock is cheaper against bonds than it normally is.`:x.gap_now<med-1?` That's narrower than its usual gap of ${pt(med)} (median of the years shown), so the stock is dearer against bonds than it normally is.`:` That's close to its usual gap of ${pt(med)} (median of the years shown).`;
 if(part==="ante"){const sp=spreadsHTML(r,"ante");return sp?`<h3>Stocks vs bonds: expected spreads</h3>${sp}`:""}
 const pe=x.ey_now>0?` (P/E ${(100/x.ey_now).toFixed(1)})`:"";
 return `<h3>Stocks vs bonds: earnings yield</h3>${spreadsHTML(r,"post")}<p><span class="pill ${L[0]}">${L[1]}</span> Earnings yield today <b>${f(x.ey_now)}</b>${pe} against <b>${f(x.aaa_now)}</b> on the safest company bonds (Moody's Aaa) and ${f(x.t10_now)} on the 10-year Treasury (${x.yields_month||"latest"}). Extra return from the stock: <b>${pt(x.gap_now)}</b> over Aaa, ${pt(x.gap_t10_now)} over Treasuries.${cmp}</p>
 <div class="mydet"><div>${svg}</div><p class="muted"><span class="bdleg"><svg width="18" height="8" aria-hidden="true" style="vertical-align:middle;margin:0 4px 0 10px"><line x1="0" y1="4" x2="18" y2="4" stroke="var(--acc)" stroke-width="2.4"/></svg>earnings yield <svg width="18" height="8" aria-hidden="true" style="vertical-align:middle;margin:0 4px 0 10px"><line x1="0" y1="4" x2="18" y2="4" stroke="var(--c2)" stroke-width="2.4"/></svg>Moody's Aaa <svg width="18" height="8" aria-hidden="true" style="vertical-align:middle;margin:0 4px 0 10px"><line x1="0" y1="4" x2="18" y2="4" stroke="var(--mut)" stroke-width="2.4" stroke-dasharray="4 3"/></svg>10-year Treasury <svg width="18" height="10" aria-hidden="true" style="vertical-align:middle;margin:0 4px 0 10px"><rect width="18" height="10" rx="2" fill="var(--acc)" fill-opacity=".15"/></svg>gap</span><br>Earnings yield = EPS ÷ price at each fiscal year end; bond yields are yearly averages from FRED. The shaded band is the gap to Aaa. Over 3 points is a large advantage, 0 to 3 thin, below 0 none.</p></div>
 <p class="muted">The earnings yield leaves out growth, so a growing company can be worth more than a bond that pays more today. A bond's interest is fixed, while a stock's earnings can fall. Nothing here changes the fair value.</p>`}
function durHTML(r){const x=((DU.stocks||{})[r.ticker]||{}).stress;if(r.type!=="stock"||!x||(!x.normal&&!x.bad))return "";
 const p1=v=>v==null?"–":(v*100).toFixed(1)+"%",ch=v=>v==null?"–":(v>=0?"+":"")+(v*100).toFixed(0)+"%",n=x.normal,b=x.bad;
 const bn=v=>(v<0?"−$":"$")+Math.abs(v).toFixed(2)+"B";
 const L={durable:["ok","Durable"],"somewhat cyclical":["warn","Somewhat cyclical"],cyclical:["bad","Cyclical"]}[x.label];
 const td=(q,a)=>`<tr><td style="text-align:left">${q}</td><td style="text-align:left">${a}</td></tr>`,rows=[];
 rows.push(td(x.basis==="ROE"?"If ROE goes back to normal":"If margins go back to normal",n?`The median ${x.basis} of the last ${n.years} years was <b>${p1(n.median_margin)}</b> (range ${p1(n.low)} to ${p1(n.high)}), against ${p1(n.margin_now)} now and ${p1(n.base_margin)} in the base case. With that margin in every scenario, the same model gives <b>${usd(n.fv_normal)}</b> instead of ${usd(n.fv_model)} (<b>${ch(n.change)}</b>).`:x.basis==="ROE"?"Not enough years of filings to measure a normal ROE.":"Not enough years of filings to measure a normal margin."));
 if(b){const m=b.measure,cov=b.cover_stressed==null?"It has little or no interest to pay.":b.cover_stressed<=0?"Operating profit wouldn't cover its interest.":`Interest would be covered <b>${b.cover_stressed.toFixed(1)}×</b> (${b.cover_now.toFixed(1)}× now).`;
  rows.push(td("If the economy turns bad",`Its weakest year in the ${b.episode}: revenue ${ch(b.worst_rev)}, ${m==="net income"?"net":"operating"} margin ${b.worst_margin_drop>=0?"+":""}${(b.worst_margin_drop*100).toFixed(1)} pts, ${m} ${ch(b.worst_profit)}${b.one_off?" (revenue still grew, so this was probably a one-off charge rather than the economy)":""}. The same hit on ${b.latest_year}: ${m} <b>${bn(b.profit_stressed_b)}</b> instead of ${bn(b.profit_now_b)} (<b>${ch(b.op_change)}</b>), ${b.profitable?"still profitable":"<b>a loss</b>"}. ${cov}`))}
 else rows.push(td("If the economy turns bad",`Can't test it: no profitable year just before the 2008-09 recession or 2020 in the filings${x.years_from?` (they start in ${x.years_from})`:""}.`));
 const ep=(x.episodes||[]).map(e=>`${e.name}: ${ch(e.profit)} vs ${e.base_year}${e.recovery_years==null?"":e.recovery_years==="not yet"?", not back yet":`, back ${e.recovery_years} year${e.recovery_years>1?"s":""} later`}${e.one_off?" (likely one-off)":""}`).join(" · ");
 const why=x.label==="durable"?"Profits held up in past recessions and today's margins aren't far above normal.":x.label==="cyclical"?"A repeat of its worst recession year would leave a loss or halve profits.":"Profits would take a noticeable hit in a bad year, or today's margins are well above normal.";
 return `<h3>Are the profits durable?</h3>${L?`<p><span class="pill ${L[0]}">${L[1]}</span> ${why}</p>`:""}
 <div class="scroll"><table class="s rq"><tr><th style="text-align:left;width:30%">Stress test</th><th style="text-align:left">Answer from the filings</th></tr>${rows.join("")}</table></div>
 ${ep?`<p class="muted">${b?b.measure[0].toUpperCase()+b.measure.slice(1):"Operating profit"} in each recession: ${ep}.</p>`:""}
 <p class="muted">Durable = a repeat costs under 25% of profit and normal margins cost under 20% of fair value. Cyclical = a loss or profits halved. 10-K figures as first reported. History only, and nothing here changes the fair value.</p>`}
function sizeHTML(r){const z=r.sz;if(!z)return "";const d=z.d,h=z.h,eq=MY.eq,b=z.bd;
 const s1=z.k0<=0?(r.diff>=0?`Price is above fair value at your ${pc1(h)} hurdle, so no new money.`:`The expected return (median ${pc1(d.med)}, ${pc1(z.pb)} chance of beating ${pc1(h)}) isn't enough above your hurdle.`)
  :`Expected return ${pc1(d.med)} a year (median; p10 ${pc1(d.p10)}, p90 ${pc1(d.p90)}) vs your ${pc1(h)} hurdle → edge ${pc1(z.edge)} of full (full at +5 points). Chance of beating the hurdle ${pc1(z.pb)} → confidence ${pc1(z.conf)}. Your ${pc1(MY.max)} max × ${pc1(z.edge)} × ${pc1(z.conf)} = <b>${pc1(z.k0)}</b>.`;
 const s2=`Bad case: ${b.v==null?"no model range for this asset":`the 10th-percentile value is ${usd(b.v)}, ${b.model>0?`${pc1(b.model)} below`:"above"} today's price`}${b.floor?`; we use a ${pc1(DROP_FLOOR)} drop instead, because prices can fall far below value in a crash even when the model is right`:""}. Your ${pc1(MY.lb)} loss budget ÷ ${pc1(b.drop)} = at most <b>${pc1(z.kL)}</b>.`;
 const s3=[z.theme?`${esc(z.theme)} would be over ${pc1(THEME_CAP)} of your portfolio, so its stocks scale ×${z.ts.toFixed(2)}`:`No theme over ${pc1(THEME_CAP)} of your portfolio`,z.scale<1?`all suggested positions scale ×${z.scale.toFixed(2)} to fit your ${pc1(eq)} in stocks`:`the total fits your ${pc1(eq)} in stocks`,SZ&&SZ.plScaled?`all positions scale ×${SZ.pls.toFixed(2)} so your portfolio's bad case stays within ${pc1(MY.pl)}`:`your portfolio's bad case stays within ${MY.pl==null?"no set limit":pc1(MY.pl)}`].join("; ")+".";
 return `<h3>How much to hold</h3><p>Suggested position: <b>${pc1(r.size||0)} of your whole portfolio</b>${r.size>0?` (${pc1((r.size||0)/eq)} of the ${pc1(eq)} you keep in stocks). In the bad case this position costs you about <b>${pc1(z.loss)}</b> of your portfolio`:""}.${r.size>0&&z.lim?` Limited by: <b>${LIM[z.lim]}</b>${z.scale<1?`, then scaled with all positions to fit your ${pc1(eq)} in stocks`:""}.`:""}</p>
 <ol class="szsteps"><li><b>What the return justifies.</b> ${s1}</li><li><b>What you can afford to lose</b> (Whitworth; the budget reflects your situation, Bernoulli). ${s2}</li><li><b>Caps</b> (Cramer: more upside never buys a bigger bet). The smaller of steps 1 and 2. ${s3}</li></ol>
 <p class="muted">Settings: hurdle ${MY.h==null?`our judgement for this stock (${pc1(r.required_return)})`:pc1(MY.h)}, loss budget ${pc1(MY.lb)} a stock, max position ${pc1(MY.max)}, stocks ${pc1(eq)} of portfolio. Change them under "My settings". A sizing guide from the model's own range, not advice: the range does not include the risk that the model itself is wrong.</p>`}
function myUI(){const S=sizeAll();
 const grp=(lab,key,opts,fmt)=>`<div class="chips"><span class="lbl">${lab}</span>${opts.map(o=>`<button class="chip${(MY[key]===o||(o!=null&&MY[key]!=null&&Math.abs(MY[key]-o)<1e-9))?" on":""}" data-my="${key}" data-v="${o}">${fmt(o)}</button>`).join("")}</div>`;
 const top=[...rows].filter(r=>r.size>0).sort((a,b)=>b.size-a.size);
 $("#mybox").innerHTML=`<details class="mydet"${MY.open?" open":""}><summary><b>My settings</b> <span class="muted">hurdle ${MY.h==null?"our judgement":pc1(MY.h)} · ${MY.hz==null?"hold for good":MY.hz+"-year horizon"} · max ${pc1(MY.max)} a stock · ${pc1(MY.eq)} in stocks · loss budget ${pc1(MY.lb)} → ${S.n} stocks suggested, ${pc1(S.tot)} invested, about −${pc1(S.loss)} in the bad case</span></summary>
  ${grp("My hurdle","h",[null,.08,.09,.10,.11,.12],o=>o==null?"Our judgement per stock":pc1(o))}
  ${grp("My horizon","hz",[5,10,20,null],o=>o==null?"Hold for good":o+" years")}
  ${grp("Loss budget a stock","lb",[.01,.02,.03],o=>pc1(o)+(o===.01?" (most of my savings)":o===.02?" (steady income)":" (small part of my wealth)"))}
  ${grp("Worst portfolio loss","pl",[.05,.10,.15,null],o=>o==null?"No limit":pc1(o))}
  ${grp("Max position","max",[.10,.125,.15],pc1)}
  ${grp("Stocks in portfolio","eq",[.20,.35,.60,1],o=>pc1(o)+(o===.2?" (cautious)":o===.35?" (balanced)":o===.6?" (growth)":" (all stocks)"))}
  <p class="muted"><b>My hurdle</b> is the yearly return your alternative would earn (for example QQQ or bonds plus a premium); fair value, buy-below and status are recalculated at it. "Our judgement" uses each stock's own required return and reason. <b>My horizon</b> is how long you expect to hold: the expected return behind suggested size is for that holding period (you sell at the end at the price that gives the next buyer the required return), and each drawer's "How far away is the value?" shows how much of the value you would collect as cash within it. <b>Loss budget</b> is the most of your whole portfolio you accept losing on one stock if its bad case happens: lower it if this money is most of what you have, raise it if it is a small part (Bernoulli: the same loss hurts more when you have less). <b>Suggested size</b> is a share of your <b>whole</b> portfolio and the smallest of: what the return justifies (max position × edge × confidence, from the Monte Carlo range at today's price; zero above fair value), your loss budget ÷ the bad-case drop (at least ${pc1(DROP_FLOOR)}), and the caps: no theme above ${pc1(THEME_CAP)} and the total within your stock share. <b>Worst portfolio loss</b> applies the loss budget to the whole portfolio: if every suggested stock hit its bad case at once (they tend to fall together) and that would cost more than this, all positions scale down together. The rest stays in your alternative. Details on the <a href="risk.html">Risk</a> page.</p>
  ${top.length?`<p class="muted"><b>Suggested now:</b> ${top.slice(0,12).map(r=>`${r.ticker} ${pc1(r.size)}`).join(" · ")}${top.length>12?` · +${top.length-12} more`:""}. Not advice.</p>`:`<p class="muted">Nothing clears your hurdle at today's prices.</p>`}</details>`;
 const det=$("#mybox details");det.ontoggle=()=>{MY.open=det.open;save()};
 document.querySelectorAll("#mybox .chip").forEach(c=>c.onclick=()=>{const v=c.dataset.v;MY[c.dataset.my]=v==="null"?null:+v;save();refresh()})}
function save(){try{localStorage.setItem("my",JSON.stringify(MY))}catch(e){}}
// Rating filter: ratings depend on live price and My hurdle, so they are worked out again on every refresh
function ratingUI(){rows.forEach(r=>{const x=ratingOf(r);r.rating=x?x.lab:null});
 $("#ratingsel").innerHTML=`<option value="all">All ratings (${rows.length})</option>`+RATE.map((t,i)=>`<option value="${i}">${t[0]} (${rows.filter(r=>r.rating===i).length})</option>`).join("");
 $("#ratingsel").value=rf}
$("#ratingsel").onchange=e=>{rf=e.target.value;render()};
function refresh(){applyHurdle();ratingUI();myUI();riskAll();kpis();render()}
refresh();
if(PAGE==="fv")dropUI();
if(location.hash.length>1&&rows.some(r=>r.ticker===location.hash.slice(1).toUpperCase()))open(location.hash.slice(1).toUpperCase());
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
// 5- and 20-year holds for My horizon (model/montecarlo.py -> data/mc_horizon.json), loaded after the page is up
fetch("data/mc_horizon.json?"+Date.now()).then(x=>x.ok?x.json():null).then(H=>{if(!H||!H.stocks)return;rows.forEach(r=>{const x=H.stocks[r.ticker],I=r.mc&&r.mc.irr;if(x&&I&&Math.abs(x.fair_value-I.fair_value)<1e-6){I.hold5=x.hold5;I.hold20=x.hold20}});if(MY.hz===5||MY.hz===20)refresh();const t=location.hash.slice(1).toUpperCase();if($("#drawer").classList.contains("on")&&rows.some(r=>r.ticker===t))open(t)}).catch(()=>{});

// ---------- How far away is the value? (scripts/duration.py -> data/duration.json). Durand's Petersburg-paradox questions:
// how much of the value is distant cash, how hard a rate rise hits it, and how much is lost if the edge ends early.
// Information only: the fair value, rating and margin of safety are unchanged.
function farHTML(r){const x=(DN.stocks||{})[r.ticker];if(r.type!=="stock"||!x||!x.horizon||!x.horizon.base)return "";
 const T=DN.treasury||{},Bk=DN.buckets||["1-5","6-10","11-20","21-30","30+"],pc=v=>(v*100).toFixed(0)+"%",ch=v=>(v>=0?"+":"−")+Math.abs(v*100).toFixed(0)+"%",rr=(x.r*100).toFixed(1).replace(".0","")+"%";
 const OP=[1,.78,.58,.4,.24],H=x.horizon,b=H.base,R=x.reliability||{},D=x.duration,S=x.stress,ins=x.kind==="insurer";
 const hz=MY.hz,cum=hz==null?1:b.shares.slice(0,hz===5?1:hz===10?2:3).reduce((a,v)=>a+v,0),cash=ins?"cash it can pay out":"free cash flow";
 const hzP=hz==null?`<p><b>Your horizon: hold for good</b> (My settings). You collect all of the cash yourself, so the price along the way matters less than whether the distant ${cash} arrives.</p>`
  :`<p><b>Your horizon: ${hz} years</b> (My settings). Within it you would collect about <b>${pc(cum)}</b> of the base value as ${cash}; the other <b>${pc(1-cum)}</b> depends on the price the next buyer pays at the end of year ${hz}, which is only as good as their belief in the cash still to come. ${b.half_year!=null&&b.half_year<=hz?"Your horizon covers where half of the value comes from.":`Half of the value arrives after your horizon (year ${b.half_year??"–"}): a long-duration asset for a shorter holding period, so the sale price carries most of your return.`}</p>`;
 const p1=v=>(v*100).toFixed(1).replace(".0","")+"%",Mo=x.mos,MR=DN.mos_rule||{},bbS=Mo?r.fair_value*(1-Mo.suggested):null;
 const mosP=!Mo?"":Mo.extra>0?`<p><b>Suggested margin of safety: ${p1(Mo.suggested)}</b> (ours ${p1(Mo.current)} + ${(Mo.extra*100).toFixed(1).replace(".0","")} points: ${(MR.step*100).toFixed(1).replace(".0","")} ${Mo.counted.length>1?`for each of the ${Mo.counted.length} concerns above`:"for the concern above"}${(R.concerns||[]).includes("price")?", leaving out the price one":""}), so buy below <b>${usd(bbS)}</b> instead of ${usd(r.buy_below)}.${r.price!=null&&(r.price<=r.buy_below)!==(r.price<=bbS)?` At today's ${usd(r.price)} that would change: the price is below one but not the other.`:""} <span class="muted">Not applied yet: the table, status and rating use ${p1(Mo.current)}. To be reviewed ${esc(MR.review||"later")}.</span></p>`
  :`<p class="muted">Suggested margin of safety: unchanged at ${p1(Mo.current)} (no distant-cash concern other than price).</p>`;
 const tone={"well supported":"ok","some reliance on distant cash":"warn","leans on distant cash":"bad"}[R.label]||"warn";
 const bar=`<div class="hzbar" role="img" aria-label="Share of base value by years: ${Bk.map((k,i)=>`years ${k} ${pc(b.shares[i])}`).join(", ")}">${b.shares.map((v,i)=>`<i style="width:${Math.max(v,0)*100}%;opacity:${OP[i]}" title="Years ${Bk[i]}: ${pc(v)}"></i>`).join("")}</div>
  <div class="hzlg">${Bk.map((k,i)=>`<span><i style="opacity:${OP[i]}"></i>Years ${k} · ${pc(b.shares[i])}</span>`).join("")}</div>`;
 const rows=["bear","base","bull"].filter(k=>H[k]).map(k=>`<tr><td style="text-align:left" class="${k==="base"?"hl":""}">${k[0].toUpperCase()+k.slice(1)}</td>${H[k].shares.map(v=>`<td>${pc(v)}</td>`).join("")}<td>${H[k].half_year??"–"}</td></tr>`).join("");
 const CL={wide:"wide moat, 20 years",narrow:"narrow moat, 15 years",none:"no moat, 12 years",end10:"edge ends at year 10"};
 const st=S?`<div class="scroll"><table class="s"><tr><th style="text-align:left">If the edge…</th><th>Fair value</th><th>Change</th></tr>
  <tr><td style="text-align:left">lasts as modelled (${MOATN[x.moat]||x.moat}, ${x.cap_years} years)</td><td>${usd(x.fv)}</td><td>–</td></tr>
  ${S.lower!=="end10"?`<tr><td style="text-align:left">is one class shorter (${CL[S.lower]})</td><td>${usd(S.lower_fv)}</td><td class="${S.lower_chg<0?"down":""}">${ch(S.lower_chg)}</td></tr>`:""}
  <tr><td style="text-align:left">${ins?`ends at year 11 (book growth fades by then; ROE then falls to ${rr})`:`ends at year 10 (growth fades by then; later investment earns only ${rr})`}</td><td>${usd(S.end10_fv)}</td><td class="${S.end10_chg<0?"down":""}">${ch(S.end10_chg)}</td></tr></table></div>`
  :`<p class="muted">Not tested: a short-advantage stock is already valued over 10 years, with growth at or below 2.5%.</p>`;
 const CN=DN.concerns||{},cl=(R.concerns||[]).map(k=>`<li>${esc(CN[k]||k)}${k==="price"&&R.implied_cap!=null?` (${R.implied_cap>80?"more than 80":R.implied_cap} years against ${x.cap_years})`:k==="fade"&&R.half_life!=null?` (about ${R.half_life.toFixed(1)} years)`:k==="score"&&R.suggested?` (${MOATN[R.suggested]||R.suggested}, score ${R.score}/10)`:""}</li>`).join("");
 return `<h3>How far away is the value?</h3><p><span class="pill ${tone}">${R.label?R.label[0].toUpperCase()+R.label.slice(1):"–"}</span> Half of the base value arrives by <b>year ${b.half_year??"–"}</b>. <b>${pc(b.beyond10)}</b> of it comes after year 10 and <b>${pc(b.beyond20)}</b> after year 20.</p>
 ${bar}
 ${hzP}
 <details class="fcdet"><summary>By case: share of ${ins?"value (cash paid out and the value after the last year)":"operating value (before net debt)"} received in each period</summary><div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th>${Bk.map(k=>`<th>Yrs ${k}</th>`).join("")}<th>Half by year</th></tr>${rows}</table></div>
 <p class="muted">The value after the last forecast year (year ${x.cap_years}) is cash growing at 2.5% forever, so it is split by year as well: every stock is cut at the same years whatever its advantage period. Discounted at the ${rr} required return.</p></details>
 <p><b>Duration.</b> If the required return rises 1 point to ${((x.r+.01)*100).toFixed(1).replace(".0","")}%, fair value falls <b>${pc(-D.down)}</b>; if it falls 1 point, fair value rises <b>${pc(D.up)}</b>. That is an equity duration of about <b>${D.years.toFixed(0)} years</b>, ${esc(D.vs)} (${T.d10} and ${T.d30} years at today's ${T.yield_pct}% 10-year yield).</p>
 <p class="muted">Assumes a rise in interest rates passes fully into the required return. In practice it often passes only partly, because profits can also rise with inflation. Debt lengthens the duration: the value left for shareholders after debt moves more than the business.</p>
 ${st}
 ${cl?`<p>What makes the distant cash less certain:</p><ul class="muted">${cl}</ul>`:`<p class="muted">No concerns about the distant cash flows on our five checks (share after year 10, edge ending at year 10, moat score, fade of excess returns, years the price needs).</p>`}
 ${mosP}
 <p class="muted">Information only: the fair value, rating and margin of safety are unchanged. Fair values here are at the stock's own ${rr} required return.</p>`}
})();
