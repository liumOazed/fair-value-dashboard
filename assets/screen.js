(async function(){
const $=s=>document.querySelector(s);
const root=document.documentElement;try{const t=localStorage.getItem("theme");if(t)root.dataset.theme=t}catch(e){}
$("#theme").onclick=()=>{const dark=getComputedStyle(root).getPropertyValue("--bg").trim()==="#0b1020";const n=dark?"light":"dark";root.dataset.theme=n;try{localStorage.setItem("theme",n)}catch(e){}};
const fmt=(n,d=1,s="")=>n==null?"–":n.toFixed(d)+s;
const usd=n=>"$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const cap=n=>n==null?"–":n>=1e12?(n/1e12).toFixed(2)+"T":n>=1e9?(n/1e9).toFixed(1)+"B":(n/1e6).toFixed(0)+"M";
let S,A,P;
try{[S,A,P]=await Promise.all(["screen","assets","prices"].map(f=>fetch(`data/${f}.json?`+Date.now()).then(r=>r.json())))}
catch(e){$("main").innerHTML='<div class="err">Could not load data files. Open this page through GitHub Pages (or a local server such as <code>python -m http.server</code>), not by double-clicking the file.</div>';return}
const fv={};A.assets.forEach(a=>{const p=P.prices[a.ticker];if(p)fv[a.ticker]={fair:a.fair_value,price:p.price,diff:p.price/a.fair_value-1}});
$("#sub").textContent=`Growth screen · ${S.month} vs ${S.prev_month||"n/a"}`;
$("#stamp").textContent=`${S.universe} stocks screened · built ${S.built}`;
const rows=S.rows,top=rows.filter(r=>r.top50),cons=rows.filter(r=>r.consistent);
const secTop={};top.forEach(r=>secTop[r.sector]=(secTop[r.sector]||0)+1);const topSec=Object.entries(secTop).sort((a,b)=>b[1]-a[1])[0];
$("#kpis").innerHTML=[["Stocks screened",S.universe,"latest month: "+S.month],["Top 50",top.length,"by Growth Quality Score"],["Consistent",cons.length,"top 50 in 3 of last 4 months"],
 ["Biggest sector in top 50",topSec[0],topSec[1]+" of 50 stocks"],["With a fair value",rows.filter(r=>!!fv[r.ticker]).length,"full model on the Fair Value tab"]]
 .map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v" style="font-size:${String(k[1]).length>8?18:26}px">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("");
let sec="All",th="All",only="",showAll=false,filt="",sortK="rank",dir=1;
function chips(el,label,list,cur,cb){el.innerHTML=`<span class="lbl">${label}</span>`+list.map(n=>`<button class="chip${n===cur?" on":""}" data-v="${n}">${n}</button>`).join("");
 el.querySelectorAll(".chip").forEach(c=>c.onclick=()=>{cb(c.dataset.v);el.querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x===c));render()})}
chips($("#secchips"),"Sector",["All",...S.sectors],sec,v=>sec=v);
chips($("#thchips"),"Theme",["All",...S.themes],th,v=>th=v);
chips($("#extra"),"Show",["All","Consistent only","Has fair value"],"All",v=>only=v==="All"?"":v);
const flagCls=f=>["Loss-making","One-off growth?","High debt","Weak interest cover"].includes(f)?"bad":["Cyclical","Diluting","Below WACC"].includes(f)?"warn":"";
{const t=$("#tscroll"),b=$("#bscroll");let lock=0;t.onscroll=()=>{if(lock){lock=0;return}lock=1;b.scrollLeft=t.scrollLeft};b.onscroll=()=>{if(lock){lock=0;return}lock=1;t.scrollLeft=b.scrollLeft}}
function sync(){const t=$("#tscroll"),b=$("#bscroll"),w=$("#tbl").scrollWidth;$("#tspacer").style.width=w+"px";t.style.display=w>b.clientWidth+2?"":"none"}
window.addEventListener("resize",sync);
function render(){
 let f=rows.filter(r=>(sec==="All"||r.sector===sec)&&(th==="All"||r.themes.includes(th))&&(only!=="Consistent only"||r.consistent)&&(only!=="Has fair value"||!!fv[r.ticker])&&(r.ticker+r.name).toLowerCase().includes(filt));
 const filtered=sec!=="All"||th!=="All"||only||filt;
 if(!filtered&&!showAll)f=f.filter(r=>r.top50);
 f.sort((a,b)=>{const x=a[sortK],y=b[sortK];return (typeof x==="string"?x.localeCompare(y):(x??-1e9)-(y??-1e9))*dir});
 const lim=filtered||showAll?f.length:f.length;
 $("#ttl").textContent=filtered?"Filtered stocks":showAll?"All screened stocks":"Top 50 by Growth Quality Score";
 $("#more").style.display=filtered?"none":"";$("#more").textContent=showAll?"Show top 50 only":`Show all ${S.universe}`;
 $("#count").textContent=`${f.length} stock${f.length===1?"":"s"} shown`;
 $("#tbl tbody").innerHTML=f.slice(0,600).map(r=>{const rc=r.rank_change;const v=fv[r.ticker];
  const ch=rc==null?'<span class="flat">new</span>':rc>0?`<span class="up">▲ ${rc}</span>`:rc<0?`<span class="down">▼ ${-rc}</span>`:'<span class="flat">–</span>';
  const pc=x=>(x*100).toFixed(0)+"%";
  const tagCls={"Demanding":"bad","Undemanding":"ok","FCF distorted":"warn","Sales shrinking":"","In line":""};
  const ig=r.implied_fcf_growth==null?"–":pc(r.implied_fcf_growth)+(r.implied_basis==="earnings"?'<span class="muted" title="Based on earnings yield because free cash flow is distorted"> (earnings)</span>':"")+(r.implied_tag?` <span class="pill ${tagCls[r.implied_tag]||""}">${r.implied_tag}</span>`:"");
  return `<tr data-t="${r.ticker}"><td class="num">${r.rank}</td><td><div class="tk">${r.ticker}${r.consistent?'<span class="pill ok">Consistent</span>':""}</div><div class="nm">${r.name}${r.flags.filter(x=>x!=="Cyclical"||1).map(x=>`<span class="pill ${flagCls(x)}">${x}</span>`).join("")}</div></td>
  <td><div>${r.sector}</div><div class="nm">${r.themes.join(" · ")}</div></td>
  <td class="num"><span class="sbar"><i style="width:${r.score}%"></i></span><b>${r.score.toFixed(1)}</b></td><td class="r num">${ch}</td>
  <td class="r num">${fmt(r.rev_growth_pct,1,"%")}</td><td class="r num">${fmt(r.profit_margin_pct,1,"%")}</td><td class="r num">${fmt(r.fcf_yield_pct,1,"%")}</td><td class="r num">${fmt(r.earnings_yield,1,"%")}</td><td class="r num">${r.fcf_conversion==null?"–":`<span class="${r.fcf_conversion>1.5?"down":r.fcf_conversion<0.25?"warn":""}" title="Free cash flow yield divided by earnings yield">${r.fcf_conversion.toFixed(2)}×</span>`}</td><td class="r num">${fmt(r.forward_pe,1)}</td>
  <td class="r num">${ig}</td><td>${v?`<a class="fvlink" href="index.html#${r.ticker}" onclick="event.stopPropagation()">${usd(v.fair)}</a> <span class="${v.diff>0?"down":"up"}">${v.diff>0?"+":""}${(v.diff*100).toFixed(0)}%</span>`:'<span class="muted">not modelled</span>'}</td></tr>`}).join("")||'<tr><td colspan="13" class="err">No stocks match these filters</td></tr>';
 setTimeout(sync,0);
 document.querySelectorAll("tbody tr[data-t]").forEach(tr=>tr.onclick=()=>open(tr.dataset.t))}
document.querySelectorAll("th[data-k]").forEach(h=>h.onclick=()=>{const k=h.dataset.k;dir=sortK===k?-dir:(k==="rank"||k==="ticker"||k==="sector"?1:-1);sortK=k;render()});
$("#q").oninput=e=>{filt=e.target.value.toLowerCase();render()};
$("#more").onclick=()=>{showAll=!showAll;render()};
function wTxt(r){const w=r.wacc_detail;if(!w)return"";const p=x=>(x*100).toFixed(1)+"%";
 return `WACC ${p(r.wacc)} = ${p(w.equity_weight)} equity (market value) × ${p(w.cost_equity)} + ${p(w.debt_weight)} debt × ${p(w.cost_debt_used)} × (1 − ${p(w.tax)} tax)`+
  (w.cost_debt_raw==null?" · no interest data, 5% assumed":Math.abs(w.cost_debt_raw-w.cost_debt_used)>1e-6?` · cost of debt ${p(w.cost_debt_raw)} from interest ÷ debt, limited to 2–10%`:" · cost of debt = interest ÷ debt")}
function qualHTML(r){const f=(v,d=1,u="")=>v==null?"–":(+v).toFixed(d)+u,sg=v=>v==null?"–":(v>0?"+":"")+(+v).toFixed(1)+"%";
 const rows=[
  ["ROIC (after-tax operating profit ÷ invested capital)",f(r.roic_pct,1,"%"),(r.roic_basis==="operating"?"operating capital (assets − cash − non-debt current liabilities)":r.roic_basis==="debt+equity"?"debt + equity (operating rows missing)":"")+(r.roic_pct>100?" · very high because the business uses little capital":"")],
  ["ROIC vs WACC",r.roic_spread==null?"–":r.roic_spread>=0?`<span class="up">+${(r.roic_spread*100).toFixed(1)} pts</span>`:`<span class="down">${(r.roic_spread*100).toFixed(1)} pts</span>`,wTxt(r)],
  ["Return on equity",f(r.roe_pct,1,"%"),"kept alongside ROIC"],
  ["Net debt ÷ EBITDA",r.net_debt_ebitda==null?"–":r.net_debt_ebitda<0?`net cash (${r.net_debt_ebitda.toFixed(1)}×)`:r.net_debt_ebitda.toFixed(1)+"×",r.net_debt_ebitda>4?'<span class="down">high</span>':""],
  ["Interest coverage (EBIT ÷ interest)",r.interest_coverage==null?"–":r.interest_coverage>=999?"no interest":r.interest_coverage.toFixed(1)+"×",r.interest_coverage!=null&&r.interest_coverage<3?'<span class="down">weak (&lt;3×)</span>':""],
  [`Revenue CAGR (${r.rev_cagr_years||"–"} yrs)`,f(r.rev_cagr_pct,1,"%"),`latest quarter YoY ${f(r.rev_growth_pct,1,"%")}`],
  ["EPS CAGR",f(r.eps_cagr_pct,1,"%"),r.share_jump?"not shown: share count jumped >50% in a year (split or restructuring)":r.eps_cagr_pct==null?"n/a (loss or no EPS at start or end)":""],
  ["Revenue growth volatility",r.rev_growth_std==null?"–":"±"+r.rev_growth_std.toFixed(1)+" pts","std-dev of yearly growth, lower = steadier"],
  ["Earnings variability",f(r.earnings_cv,2),r.earnings_cv==null?"n/a (average ≤ 0 or under 3 years)":"std ÷ mean of net income, lower = steadier"],
  ["FCF variability",f(r.fcf_cv,2),(r.fcf_cv==null?"n/a (average ≤ 0 or under 3 years). ":"")+(r.fcf_years?`${r.fcf_neg_years} of ${r.fcf_years} years negative`:"")],
  ["Share count change",r.share_change_pct_yr==null?"–":sg(r.share_change_pct_yr)+" a year",r.share_change_pct_yr>3?'<span class="down">diluting</span>':r.share_change_pct_yr<-1?'<span class="up">buybacks</span>':""],
  ["FCF ÷ net income",f(r.fcf_ni_conversion,2,"×"),"latest fiscal year"],
  ["Capex % of operating cash flow",f(r.capex_ocf_pct,0,"%"),"capital intensity, same year's statements"]];
 const C=r.components||{},bar=(k,l)=>`<div class="cmp"><span>${l}</span><span class="sbar"><i style="width:${C[k]||0}%"></i></span><b>${C[k]==null?"–":C[k].toFixed(0)}</b></div>`;
 return `<h3>Score breakdown</h3><p class="muted">Each part is a percentile inside the stock's sector (100 = best). Score ${r.score.toFixed(1)} (v3); the previous method gave ${r.score_v2==null?"–":r.score_v2.toFixed(1)}.</p>
 <div class="cmps">${bar("growth","Growth + consistency")}${bar("profit","Profitability (ROIC, ROE, margin)")}${bar("cash","Cash (FCF yield + stability)")}${bar("value","Valuation")}${bar("balance","Balance sheet + dilution")}${bar("quality","Gross margin")}</div>
 <h3>Quality &amp; durability</h3>${r.v3_source&&r.v3_source!=="own"?`<p class="muted">Multi-year figures come from the screener run <code>${r.v3_source}</code> because this month's CSV predates them.</p>`:""}
 <table class="s"><tr><th style="text-align:left">Metric</th><th>Value</th><th style="text-align:left">Note</th></tr>${rows.map(x=>`<tr><td style="text-align:left">${x[0]}</td><td>${x[1]}</td><td style="text-align:left;white-space:normal" class="muted">${x[2]}</td></tr>`).join("")}</table>`}
function mktTxt(r){const M=S.market,rel=x=>`<b>${Math.abs(x*100).toFixed(0)}% ${x>0?"above":"below"}</b>`;
 if(r.pe_vs_market==null&&r.fpe_vs_market==null)return`<b>Versus the market:</b> no positive P/E (losses), so no comparison with the market P/E of ${M.pe.toFixed(1)}.`;
 let t=`<b>Versus the market:</b> `;
 if(r.pe_vs_market!=null)t+=`its P/E of ${r.pe.toFixed(1)} on last year's earnings is ${rel(r.pe_vs_market)} the market's ${M.pe.toFixed(1)}`;
 if(r.fpe_vs_market!=null)t+=`${r.pe_vs_market!=null?"; its forward P/E of ":"its forward P/E of "}${r.forward_pe.toFixed(1)} is ${rel(r.fpe_vs_market)} the market's forward ${M.forward_pe.toFixed(1)}`;
 t+=". ";
 const x=r.fpe_vs_market??r.pe_vs_market;
 t+=x>0.25?"Paying this premium only makes sense if growth stays well above the market's.":x<-0.25?"That discount means the market expects weaker growth or sees more risk; if the business holds up, it is cheap.":"Roughly a market multiple on next year's earnings.";
 if(r.pe>0&&r.forward_pe>0&&(r.pe/r.forward_pe>2||r.forward_pe/r.pe>2))t+=` <span class="muted">Trailing and forward P/E differ by more than 2x, so either the market expects earnings to jump (fast growth or recovery) or one-off items (gains, charges) distort one of them. Check which before relying on either.</span>`;
 return t}
function open(t){const r=rows.find(x=>x.ticker===t);const v=fv[t];
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 <p>${r.sector}${r.themes.length?" · "+r.themes.join(" · "):""}${r.consistent?' <span class="pill ok">Consistent</span>':""}${r.flags.map(x=>`<span class="pill ${flagCls(x)}">${x}</span>`).join("")}</p>
 <div class="grid2"><div class="mini">Score now<b>${r.score.toFixed(1)}</b><span class="muted">rank ${r.rank} of ${S.universe}</span></div>
 <div class="mini">Score in ${S.prev_month||"last month"}<b>${r.prev_score==null?"–":r.prev_score.toFixed(1)}</b><span class="muted">${r.prev_rank==null?"not in that file":"rank "+r.prev_rank}</span></div>
 <div class="mini">Original score<b>${r.old_score.toFixed(1)}</b><span class="muted">the old method, for comparison</span></div><div class="mini">Market cap<b>${cap(r.market_cap)}</b></div></div>
 ${qualHTML(r)}
 <h3>Rank by month</h3><div class="hist">${(r.history||[]).map(h=>`<div class="${h.est?"est":""}" title="${h.est?"estimated month":"real data"}">${h.m}${h.est?" (est.)":""}<b>${h.rank==null?"–":"#"+h.rank}</b><span class="muted">${h.score==null?"":h.score.toFixed(1)}</span></div>`).join("")}</div>
 <p class="muted">${r.months_in_top50} of the last ${S.window.length} months in the top 50.</p>
 <h3>Key numbers</h3><table class="s"><tr><th style="text-align:left">Metric</th><th>Value</th></tr>
 ${[["Latest quarter sales growth (YoY)",fmt(r.rev_growth_pct,1,"%")],["Gross margin",fmt(r.gross_margin_pct,1,"%")],["Net margin",fmt(r.profit_margin_pct,1,"%")],["Return on equity",fmt(r.roe_pct,1,"%")],["FCF yield",fmt(r.fcf_yield_pct,1,"%")],["Earnings yield",fmt(r.earnings_yield,1,"%")],["FCF ÷ earnings yield",r.fcf_conversion==null?"–":r.fcf_conversion.toFixed(2)+"×"],["P/E",fmt(r.pe,1)],["Market P/E",`${S.market.pe.toFixed(1)} <span class="muted">(forward ${S.market.forward_pe.toFixed(1)})</span>`],["Forward P/E",fmt(r.forward_pe,1)],["EV/EBITDA",fmt(r.ev_ebitda,1)],["Price/Sales",fmt(r.ps,1)]].map(x=>`<tr><td style="text-align:left">${x[0]}</td><td>${x[1]}</td></tr>`).join("")}</table>
 <h3>What today's price assumes</h3><p>${r.implied_fcf_growth==null?"Not available (cash flow and earnings are zero or negative).":
 (r.implied_basis==="earnings"?`Free cash flow is <b>distorted</b> for this stock (${r.sector==="Financial Services"?"financial companies' cash flow is not meaningful":"heavy capex swallows most of operating cash flow"}), so I used its <b>earnings yield</b> instead. `:"")+
 `At a ${(r.required_return*100).toFixed(1)}% required return (<span title="${r.required_return_reason}">${r.required_return_source==='stock'?'stock-specific rate':r.required_return_source==='theme'?'chip-group rate':'sector rate'}</span>, same as the Fair Value tab), the market value already assumes ${r.implied_basis==="earnings"?"earnings":"free cash flow"} ${r.implied_fcf_growth<0?`<b>shrinking about ${Math.abs(r.implied_fcf_growth*100).toFixed(0)}% a year</b> for 10 years, a pessimistic view that may reflect risks such as lawsuits or regulation`:`growing about <b>${(r.implied_fcf_growth*100).toFixed(0)}% a year</b> for 10 years`}.${r.implied_tag==="Demanding"||r.implied_tag==="Undemanding"||r.implied_tag==="In line"?` Compared with recent sales growth that is <b>${r.implied_tag.toLowerCase()}</b>.`:r.implied_tag==="Sales shrinking"?" Sales are shrinking, so there is no fair comparison and no verdict is given.":""} Indicative only.`}</p>
 <p>${mktTxt(r)}</p>
 <h3>Fair value</h3><p>${v?`Modelled: fair value <b>${usd(v.fair)}</b> vs price ${usd(v.price)} (${v.diff>0?"+":""}${(v.diff*100).toFixed(0)}%). <a class="fvlink" href="index.html#${t}">Open the full calculation</a>`:"No full fair-value model yet for this stock. A screen score alone does not say whether the price is fair."}</p>
 <p class="muted">Estimates from screen data only, not investment advice.</p>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close}
function close(){$("#drawer").classList.remove("on");$("#scrim").classList.remove("on")}
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
render();
RunPanel($("#runpanel"));
})();
