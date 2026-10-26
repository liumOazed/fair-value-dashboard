(async function(){
const $=s=>document.querySelector(s);
const root=document.documentElement;try{const t=localStorage.getItem("theme");if(t)root.dataset.theme=t}catch(e){}
$("#theme").onclick=()=>{const dark=getComputedStyle(root).getPropertyValue("--bg").trim()==="#0b1020";const n=dark?"light":"dark";root.dataset.theme=n;try{localStorage.setItem("theme",n)}catch(e){}};
const usd=n=>n==null?"–":"$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const pct=(n,d=0)=>n==null?"–":(n>0?"+":"")+(n*100).toFixed(d)+"%";
const M=["January","February","March","April","May","June","July","August","September","October","November","December"];
const nice=m=>M[+m.slice(5)-1]+" "+m.slice(0,4);
RunPanel($("#runpanel"));
{const t=$("#tscroll"),b=$("#bscroll");let lock=0;t.onscroll=()=>{if(lock){lock=0;return}lock=1;b.scrollLeft=t.scrollLeft};b.onscroll=()=>{if(lock){lock=0;return}lock=1;t.scrollLeft=b.scrollLeft}}
function sync(){const t=$("#tscroll"),b=$("#bscroll"),w=$("#tbl").scrollWidth;$("#tspacer").style.width=w+"px";t.style.display=w>b.clientWidth+2?"":"none"}
window.addEventListener("resize",sync);
let T={months:{}},P={prices:{}},FULL={};
try{(await fetch("data/assets.json?"+Date.now()).then(r=>r.json())).assets.forEach(a=>FULL[a.ticker]=a)}catch(e){}
try{T=await fetch("data/fair_value_table.json?"+Date.now()).then(r=>{if(!r.ok)throw 0;return r.json()})}catch(e){}
try{P=await fetch("data/prices.json?"+Date.now()).then(r=>r.json())}catch(e){}
const months=Object.keys(T.months||{}).sort().reverse();
if(!months.length){$("#tbl tbody").innerHTML='<tr><td colspan="12" class="err">No month evaluated yet. Use <b>Evaluate Fair Value</b> above (after Calculate Top Growth).</td></tr>';
 $("#kpis").innerHTML="";$("#others").style.display="none";return}
let cur=months[0];
function status(price,fair,buy,mos){if(price==null||fair==null)return["Price pending",""];
 if(price<=buy)return["Attractive","b-attr"];if(price<=fair*(1-mos/2))return["Potentially interesting","b-int"];if(price<=fair)return["Little margin","b-lit"];return["Above estimated value","b-abv"]}
function render(){
 const d=T.months[cur];const now=t=>(P.prices[t]||{}).price??null;
 $("#ttl").textContent=`Fair Value Table · ${nice(cur)}`;$("#stamp").textContent=`evaluated ${d.evaluated} · ${d.candidates} candidates, ${d.passed} passed the checks${d.method?" · method: "+d.method:""}`;
 $("#sub").textContent=`Monthly Top 5 · ${nice(cur)}`;
 const rows=d.picks.map(p=>{const n=now(p.ticker)??p.price_at_eval;const[st,cl]=status(n,p.fair_value,p.buy_below,p.mos);return{...p,now:n,st,cl,
   diff:n!=null&&p.fair_value?n/p.fair_value-1:null,since:n!=null&&p.price_at_eval?n/p.price_at_eval-1:null}});
 const disc=rows.filter(r=>r.diff!=null);
 $("#kpis").innerHTML=[["Month",nice(cur),"evaluated "+d.evaluated],["Checked",`${d.passed} of ${d.candidates}`,"candidates with trustworthy numbers"],
  (()=>{const a=disc.length?disc.reduce((x,r)=>x+r.diff,0)/disc.length:null;return["Average gap",a==null?"–":Math.abs(a*100).toFixed(0)+"% "+(a<0?"below":"above"),"picks' price now vs fair value"]})(),
  ["Below buy price",rows.filter(r=>r.st==="Attractive").length+" of "+rows.length,"price under fair value minus margin of safety"]]
  .map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v" style="font-size:${String(k[1]).length>9?18:26}px">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("");
 $("#tbl tbody").innerHTML=rows.map((r,i)=>`<tr data-t="${r.ticker}"><td class="num">${i+1}</td>
  <td><div class="tk">${r.ticker}${r.consistent?'<span class="pill ok">Consistent</span>':""}${r.cyclical?'<span class="pill warn">Cyclical</span>':""}</div><div class="nm">${r.name} · ${r.sector}${FULL[r.ticker]?` · <a class="fvlink" href="index.html#${r.ticker}" onclick="event.stopPropagation()">full model ${usd(FULL[r.ticker].fair_value)}</a>`:""}</div></td>
  <td class="r num">${usd(r.price_at_eval)}</td><td class="r num">${usd(r.now)}</td><td class="r num"><b>${usd(r.fair_value)}</b></td><td class="r num">${usd(r.buy_below)}</td>
  <td class="r num"><span class="${r.diff>0?"down":"up"}">${pct(r.diff)}</span></td><td><span class="badge ${r.cl}">${r.st}</span></td>
  <td class="r num"><span class="${r.since>0?"up":r.since<0?"down":"flat"}">${pct(r.since,1)}</span></td>
  <td class="r num">${r.scenario_values?`${usd(r.scenario_values.bear)} / ${usd(r.scenario_values.base)} / ${usd(r.scenario_values.bull)}`:"–"}</td>
  <td class="r num">${(r.cash_yield*100).toFixed(1)}% <span class="muted">${r.cash_basis}</span></td><td class="r num">${(r.growth_input*100).toFixed(0)}%</td></tr>`).join("");
 document.querySelectorAll("tbody tr[data-t]").forEach(tr=>tr.onclick=()=>open(rows.find(r=>r.ticker===tr.dataset.t)));
 setTimeout(sync,0);
 $("#others").innerHTML=`<h2>Not picked</h2>
  ${d.check_first.length?`<details class="list" open><summary>Check first (${d.check_first.length}): looks too cheap to trust</summary><ul>${d.check_first.map(c=>`<li><b>${c.ticker}</b> ${c.name}: ${c.reason}</li>`).join("")}</ul></details>`:""}
  <details class="list"><summary>Runners-up (${d.runners_up.length}): passed the checks, smaller discount</summary><ul>${d.runners_up.map(c=>`<li><b>${c.ticker}</b> ${c.name} (${c.sector}): value ${c.value_to_price.toFixed(2)}× price${c.value_to_price<1?" (above estimated value)":""}</li>`).join("")}</ul></details>
  <details class="list"><summary>Skipped (${d.skipped.length}): numbers can't be trusted for a quick estimate</summary><ul>${d.skipped.map(c=>`<li><b>${c.ticker}</b> ${c.name}: ${c.reason}</li>`).join("")}</ul></details>`;
}
function open(r){const s=r.scenarios,R=(r.required_return*100).toFixed(1);
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 <p>${r.sector} · Growth Quality rank ${r.rank} (score ${r.score.toFixed(1)}) <span class="badge ${r.cl}">${r.st}</span></p>
 <div class="grid2"><div class="mini">Fair value<b>${usd(r.fair_value)}</b><span class="muted">buy below ${usd(r.buy_below)} (${(r.mos*100).toFixed(0)}% margin of safety)</span></div>
 <div class="mini">Price now<b>${usd(r.now)}</b><span class="muted">${pct(r.diff)} vs fair value · ${pct(r.since,1)} since picked at ${usd(r.price_at_eval)}</span></div></div>
 <h3>Step 1 · Cash it earns per $1 of share price</h3><p>FCF yield ${r.metrics.fcf_yield_pct.toFixed(1)}%, trailing earnings yield ${r.trailing_ey.toFixed(1)}%. I take the lower: <b>${(r.cash_yield*100/(r.cyclical?0.8:1)).toFixed(1)}%</b> (${r.cash_basis})${r.cyclical?`, then a 20% mid-cycle haircut for a cyclical sector → <b>${(r.cash_yield*100).toFixed(1)}%</b>`:""}.</p>
 <h3>Step 2 · Growth</h3><p>Recent sales growth ${r.metrics.rev_growth_pct.toFixed(1)}% → used <b>${(r.growth_input*100).toFixed(0)}%</b> (clipped to 0-${r.cyclical?10:40}%).</p>
 <div class="scroll"><table class="s"><tr><th style="text-align:left">Case</th><th>Year-1 growth</th><th>Year-10 growth</th><th>Value ÷ price</th><th>Per share</th><th>Weight</th></tr>
 ${["bear","base","bull"].map((k,i)=>`<tr><td style="text-align:left">${k[0].toUpperCase()+k.slice(1)}</td><td>${(s[k].g1*100).toFixed(1)}%</td><td>${(s[k].g10*100).toFixed(0)}%</td><td>${s[k].ratio.toFixed(2)}×</td><td>${r.scenario_values?usd(r.scenario_values[k]):"–"}</td><td>${[30,50,20][i]}%</td></tr>`).join("")}
 <tr><td style="text-align:left"><b>Weighted</b></td><td></td><td></td><td><b>${r.value_to_price.toFixed(2)}×</b></td><td><b>${usd(r.fair_value)}</b></td><td>100%</td></tr></table></div>
 <h3>Step 3 · Discounting</h3><p>Each case projects 10 years of cash, discounts it at the <b>${R}%</b> required return for ${r.sector}, and adds a terminal value at 2.5% growth. "Value ÷ price" is what the business is worth per $1 of today's market value; times the price at evaluation (${usd(r.price_at_eval)}) gives the per-share value.</p>
 <h3>Why it passed the checks</h3><p>${r.metrics.fcf_ni!=null?`Free cash flow is ${r.metrics.fcf_ni.toFixed(2)}× net income${r.metrics.fcf_ni_basis==="3y"?" over 3 years":""} (between 0.25× and 1.5×)`:`FCF is ${(r.metrics.fcf_conversion??0).toFixed(2)}× earnings (between 0.25× and 1.5×)`}, net margin ${r.metrics.profit_margin_pct.toFixed(1)}%, and sales growth didn't swing by more than 30 points since the last real month.</p>
 ${FULL[r.ticker]?`<h3>Full model</h3><p>The hand-checked model on the Fair Value tab gives <b>${usd(FULL[r.ticker].fair_value)}</b> (buy below ${usd(FULL[r.ticker].buy_below)}) vs this quick estimate of ${usd(r.fair_value)}. Where they differ, trust the full model: it uses filings and normalises the business cycle. <a class="fvlink" href="index.html#${r.ticker}">Open the full calculation</a></p>`:""}
 <p class="muted">Quick estimate from screen data, not investment advice. The market value in the CSV is assumed to match the price on the evaluation day.</p>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close}
function close(){$("#drawer").classList.remove("on");$("#scrim").classList.remove("on")}
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
const mc=$("#mchips");mc.innerHTML='<span class="lbl">Month</span>'+months.map(m=>`<button class="chip${m===cur?" on":""}" data-m="${m}">${nice(m)}</button>`).join("");
mc.querySelectorAll(".chip").forEach(c=>c.onclick=()=>{cur=c.dataset.m;mc.querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x===c));render()});
render();
})();
