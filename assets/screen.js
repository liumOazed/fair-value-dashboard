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
$("#kpis").innerHTML=[["Stocks screened",S.universe,"latest month: "+S.month],["Top 50",top.length,"by Growth Quality Score"],["Consistent",cons.length,"top 50 in both months"],
 ["Biggest sector in top 50",topSec[0],topSec[1]+" of 50 stocks"],["With a fair value",rows.filter(r=>!!fv[r.ticker]).length,"full model on the Fair Value tab"]]
 .map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v" style="font-size:${String(k[1]).length>8?18:26}px">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("");
let sec="All",th="All",only="",showAll=false,filt="",sortK="rank",dir=1;
function chips(el,label,list,cur,cb){el.innerHTML=`<span class="lbl">${label}</span>`+list.map(n=>`<button class="chip${n===cur?" on":""}" data-v="${n}">${n}</button>`).join("");
 el.querySelectorAll(".chip").forEach(c=>c.onclick=()=>{cb(c.dataset.v);el.querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x===c));render()})}
chips($("#secchips"),"Sector",["All",...S.sectors],sec,v=>sec=v);
chips($("#thchips"),"Theme",["All",...S.themes],th,v=>th=v);
chips($("#extra"),"Show",["All","Consistent only","Has fair value"],"All",v=>only=v==="All"?"":v);
const flagCls=f=>f==="Loss-making"||f==="One-off growth?"?"bad":f==="Cyclical"?"warn":"";
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
  const ig=r.implied_fcf_growth==null?"–":(r.implied_fcf_growth*100).toFixed(0)+"%"+(r.implied_tag?` <span class="pill ${r.implied_tag==="Demanding"?"bad":r.implied_tag==="Undemanding"?"ok":""}">${r.implied_tag}</span>`:"");
  return `<tr data-t="${r.ticker}"><td class="num">${r.rank}</td><td><div class="tk">${r.ticker}${r.consistent?'<span class="pill ok">Consistent</span>':""}</div><div class="nm">${r.name}${r.flags.filter(x=>x!=="Cyclical"||1).map(x=>`<span class="pill ${flagCls(x)}">${x}</span>`).join("")}</div></td>
  <td><div>${r.sector}</div><div class="nm">${r.themes.join(" · ")}</div></td>
  <td class="num"><span class="sbar"><i style="width:${r.score}%"></i></span><b>${r.score.toFixed(1)}</b></td><td class="r num">${ch}</td>
  <td class="r num">${fmt(r.rev_growth_pct,1,"%")}</td><td class="r num">${fmt(r.profit_margin_pct,1,"%")}</td><td class="r num">${fmt(r.fcf_yield_pct,1,"%")}</td><td class="r num">${fmt(r.forward_pe,1)}</td>
  <td class="r num">${ig}</td><td>${v?`<a class="fvlink" href="index.html#${r.ticker}" onclick="event.stopPropagation()">${usd(v.fair)}</a> <span class="${v.diff>0?"down":"up"}">${v.diff>0?"+":""}${(v.diff*100).toFixed(0)}%</span>`:'<span class="muted">not modelled</span>'}</td></tr>`}).join("")||'<tr><td colspan="11" class="err">No stocks match these filters</td></tr>';
 document.querySelectorAll("tbody tr[data-t]").forEach(tr=>tr.onclick=()=>open(tr.dataset.t))}
document.querySelectorAll("th[data-k]").forEach(h=>h.onclick=()=>{const k=h.dataset.k;dir=sortK===k?-dir:(k==="rank"||k==="ticker"||k==="sector"?1:-1);sortK=k;render()});
$("#q").oninput=e=>{filt=e.target.value.toLowerCase();render()};
$("#more").onclick=()=>{showAll=!showAll;render()};
function open(t){const r=rows.find(x=>x.ticker===t);const v=fv[t];
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:22px">${r.ticker} <span class="muted">${r.name}</span></h2>
 <p>${r.sector}${r.themes.length?" · "+r.themes.join(" · "):""}${r.consistent?' <span class="pill ok">Consistent</span>':""}${r.flags.map(x=>`<span class="pill ${flagCls(x)}">${x}</span>`).join("")}</p>
 <div class="grid2"><div class="mini">Score now<b>${r.score.toFixed(1)}</b><span class="muted">rank ${r.rank} of ${S.universe}</span></div>
 <div class="mini">Score last month<b>${r.prev_score==null?"–":r.prev_score.toFixed(1)}</b><span class="muted">${r.prev_rank==null?"not in last month's file":"rank "+r.prev_rank}</span></div>
 <div class="mini">Original score<b>${r.old_score.toFixed(1)}</b><span class="muted">the old method, for comparison</span></div><div class="mini">Market cap<b>${cap(r.market_cap)}</b></div></div>
 <h3>Key numbers</h3><table class="s"><tr><th style="text-align:left">Metric</th><th>Value</th></tr>
 ${[["Sales growth",fmt(r.rev_growth_pct,1,"%")],["Gross margin",fmt(r.gross_margin_pct,1,"%")],["Net margin",fmt(r.profit_margin_pct,1,"%")],["Return on equity",fmt(r.roe_pct,1,"%")],["FCF yield",fmt(r.fcf_yield_pct,1,"%")],["P/E",fmt(r.pe,1)],["Forward P/E",fmt(r.forward_pe,1)],["EV/EBITDA",fmt(r.ev_ebitda,1)],["Price/Sales",fmt(r.ps,1)]].map(x=>`<tr><td style="text-align:left">${x[0]}</td><td>${x[1]}</td></tr>`).join("")}</table>
 <h3>What today's price assumes</h3><p>${r.implied_fcf_growth==null?"Not available (free cash flow is zero or negative).":`The market value already assumes free cash flow growing about <b>${(r.implied_fcf_growth*100).toFixed(0)}% a year for 10 years</b>${r.implied_tag?` (${r.implied_tag.toLowerCase()} compared with recent sales growth)`:""}. Indicative only.`}</p>
 <h3>Fair value</h3><p>${v?`Modelled: fair value <b>${usd(v.fair)}</b> vs price ${usd(v.price)} (${v.diff>0?"+":""}${(v.diff*100).toFixed(0)}%). <a class="fvlink" href="index.html#${t}">Open the full calculation</a>`:"No full fair-value model yet for this stock. A screen score alone does not say whether the price is fair."}</p>
 <p class="muted">Estimates from screen data only, not investment advice.</p>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close}
function close(){$("#drawer").classList.remove("on");$("#scrim").classList.remove("on")}
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
render();
})();
