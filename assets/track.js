(async function(){
const $=s=>document.querySelector(s);
const root=document.documentElement;try{const t=localStorage.getItem("theme");if(t)root.dataset.theme=t}catch(e){}
$("#theme").onclick=()=>{const dark=getComputedStyle(root).getPropertyValue("--bg").trim()==="#0b1020";const n=dark?"light":"dark";root.dataset.theme=n;try{localStorage.setItem("theme",n)}catch(e){}};
const pc=x=>x==null?"–":(x>0?"+":"")+(x*100).toFixed(1)+"%",cl=x=>x==null?"flat":x>0?"up":x<0?"down":"flat";
let D=null;try{D=await fetch("data/tracking/performance.json?"+Date.now()).then(r=>{if(!r.ok)throw 0;return r.json()})}catch(e){}
if(!D||!D.groups.length){$("#tbl tbody").innerHTML='<tr><td colspan="8" class="err">No signals recorded yet. The first snapshot is taken by the "Forward test" workflow.</td></tr>';return}
$("#stamp").textContent="prices updated "+D.updated;
const G=D.groups,ok=G.filter(g=>g.excess!=null),avg=ok.length?ok.reduce((a,g)=>a+g.excess,0)/ok.length:null,first=G.map(g=>g.date).sort()[0];
const days=Math.max(...G.map(g=>g.days));
$("#kpis").innerHTML=[["Signals tracked",G.length,"groups recorded"],["Longest running",days+" days","since "+first],["Average excess vs SPY",pc(avg),"across all groups"],["Verdict",days<365?"Too early":"See groups",days<365?"needs 12+ months":"compare across months"]]
 .map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v" style="font-size:${String(k[1]).length>9?18:26}px">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("");
$("#tbl tbody").innerHTML=G.map((g,i)=>`<tr data-i="${i}"><td>${g.month}</td><td><b>${g.label}</b></td><td>${g.date} <span class="muted">(${g.days} d)</span></td><td class="r num">${g.n}</td>
 <td class="r num"><span class="${cl(g.ret)}">${pc(g.ret)}</span></td><td class="r num">${pc(g.spy_ret)}</td><td class="r num"><b class="${cl(g.excess)}">${pc(g.excess)}</b></td><td class="r num">${g.beat==null?"–":(g.beat*100).toFixed(0)+"%"}</td></tr>`).join("");
document.querySelectorAll("tbody tr[data-i]").forEach(tr=>tr.onclick=()=>{const g=G[+tr.dataset.i];
 $("#dr").innerHTML=`<button class="x" id="cl">✕</button><h2 style="font-size:20px">${g.label} <span class="muted">${g.month}</span></h2>
 <p class="muted">Recorded ${g.date}. Equal-weight return ${pc(g.ret)} vs SPY ${pc(g.spy_ret)}.</p>
 <table class="s"><tr><th style="text-align:left">Stock</th><th>Entry</th><th>Now</th><th>Return</th><th>vs SPY</th></tr>${g.stocks.slice().sort((a,b)=>(b.ret??-9)-(a.ret??-9)).map(s=>`<tr><td style="text-align:left"><b>${s.ticker}</b></td><td>${s.entry==null?"–":"$"+s.entry.toFixed(2)}</td><td>${s.now==null?"–":"$"+s.now.toFixed(2)}</td><td class="${cl(s.ret)}">${pc(s.ret)}</td><td class="${cl(s.ret==null||g.spy_ret==null?null:s.ret-g.spy_ret)}">${s.ret==null||g.spy_ret==null?"–":pc(s.ret-g.spy_ret)}</td></tr>`).join("")}</table>`;
 $("#drawer").classList.add("on");$("#scrim").classList.add("on");$("#cl").onclick=close});
function close(){$("#drawer").classList.remove("on");$("#scrim").classList.remove("on")}
$("#scrim").onclick=close;document.addEventListener("keydown",e=>e.key==="Escape"&&close());
})();

// ---------------- historical backtest (relative, survivorship-biased) ----------------
(async function(){
const $=s=>document.querySelector(s),el=$("#bt");
let R=null;try{R=await fetch("data/backtest/results.json?"+Date.now()).then(r=>{if(!r.ok)throw 0;return r.json()})}catch(e){}
if(!R){el.innerHTML='<h2>Historical backtest</h2><p class="muted">Not run yet.</p>';return}
const pc=(x,d=1)=>x==null||isNaN(x)?"–":(x>0?"+":"")+(x*100).toFixed(d)+"%",G=R.groups,D=R.dates;
const LAB={Q1:"Score Q1 (best 20%)",Q2:"Score Q2",Q3:"Score Q3",Q4:"Score Q4",Q5:"Score Q5 (worst 20%)",TOP50:"Top 50 by score",V1:"Cheapest 20% (quick fair value)",V2:"Value Q2",V3:"Value Q3",V4:"Value Q4",V5:"Dearest 20%",NORMAL:"Risk: Normal",HIGH:"Risk: High",TOP50_CHEAP:"Top 50 that also look cheap",ALL:"All scored stocks (equal weight)",SPY:"SPY",RSP:"RSP (equal-weight S&P 500)"};
const SER=[["Q1","var(--c1)"],["Q5","var(--c2)"],["ALL","var(--mut)"]];
const W=900,H=300,pl=48,pr=150,pt=14,pb=28,n=D.length;
const ys=SER.flatMap(([k])=>[1,...G[k].cum]),lo=Math.min(...ys),hi=Math.max(...ys);
const L=v=>Math.log(v),X=i=>pl+i/(n)*(W-pl-pr),Y=v=>pt+(L(hi)-L(v))/(L(hi)-L(lo))*(H-pt-pb);
const ticks=[0.5,1,1.5,2,3,4,5,6,8,10].filter(v=>v>=lo*0.98&&v<=hi*1.02);
const grid=ticks.map(v=>`<line x1="${pl}" x2="${W-pr}" y1="${Y(v)}" y2="${Y(v)}" class="bgr"/><text x="${pl-6}" y="${Y(v)+4}" text-anchor="end" class="mct">${v}×</text>`).join("");
const years=D.map((d,i)=>[d,i]).filter(([d])=>d.endsWith("12-31")&&+d.slice(0,4)%2===0).map(([d,i])=>`<text x="${X(i+1)}" y="${H-8}" text-anchor="middle" class="mct">${d.slice(0,4)}</text>`).join("");
const lines=SER.map(([k,c])=>{const pts=[[X(0),Y(1)],...G[k].cum.map((v,i)=>[X(i+1),Y(v)])];const last=pts[pts.length-1];
 return `<polyline fill="none" stroke="${c}" stroke-width="2" points="${pts.map(p=>p.map(x=>x.toFixed(1)).join(",")).join(" ")}"/><text x="${last[0]+6}" y="${last[1]+4}" class="mct" style="fill:var(--tx)">${LAB[k].split(" (")[0]} ${G[k].cum[G[k].cum.length-1].toFixed(1)}×</text>`}).join("");
const chart=`<div class="btwrap"><svg viewBox="0 0 ${W} ${H}" class="mcsvg" id="btsvg" role="img" aria-label="Growth of $1, best vs worst score quintile vs all stocks">${grid}${years}${lines}<line id="btx" y1="${pt}" y2="${H-pb}" class="bxh" style="display:none"/></svg><div id="bttip" class="bttip" style="display:none"></div></div>
 <div class="chips">${SER.map(([k,c])=>`<span class="lg"><i style="background:${c}"></i>${LAB[k]}</span>`).join("")}</div>`;
const row=k=>`<tr><td style="text-align:left">${LAB[k]}</td><td>${pc(G[k].ann)}</td><td>${pc(G[k].vol,0)}</td><td>${pc(G[k].maxdd,0)}</td></tr>`;
const grp=(title,keys)=>`<tr><th colspan="4" style="text-align:left;padding-top:12px">${title}</th></tr>`+keys.map(row).join("");
const S=R.spreads;
el.innerHTML=`<div class="card-head"><h2>Historical backtest, ${D[0].slice(0,4)}–${D[n-1].slice(0,4)} (relative)</h2><span class="muted">${n} quarters · built ${R.built}</span></div>
 <p class="warnbox"><b>Compare groups with each other, not with SPY.</b> Companies that were later acquired or went bankrupt have no price history in free data, so every group here is flattered by roughly the same amount (survivorship bias). The <i>gaps</i> between groups are the honest part.</p>
 <p class="muted">Each quarter from ${D[0]}: that day's S&P 500 members, scored with the live score v4 using only annual SEC figures filed before that day (as first reported), held for one quarter, equal weight, dividends included, no trading costs. Differences from the live screen: annual figures instead of the latest quarter, trailing P/E instead of forward, today's sector labels.</p>
 <h3>Growth of $1 (log scale)</h3>${chart}
 <h3>Are the gaps real? (block bootstrap)</h3>
 <div class="scroll"><table class="s"><tr><th style="text-align:left">Gap between groups</th><th>Average a year</th><th>Quarters won</th><th>Likely range (5th–95th)</th><th>Chance the gap is positive</th></tr>
 ${Object.entries(S).map(([k,v])=>`<tr><td style="text-align:left">${k}</td><td><b class="${v.ann_mean>0?"up":"down"}">${pc(v.ann_mean)}</b></td><td>${(v.hit*100).toFixed(0)}%</td><td>${v.bootstrap?pc(v.bootstrap.p5)+" to "+pc(v.bootstrap.p95):"–"}</td><td>${v.bootstrap?(v.bootstrap.p_pos*100).toFixed(0)+"%":"–"}</td></tr>`).join("")}</table></div>
 <p class="muted">Block bootstrap: the quarterly gaps are resampled in 4-quarter blocks 10,000 times (keeping runs of good and bad quarters together) to see how much the average could have come out differently by luck.</p>
 <h3>Every group</h3><div class="scroll"><table class="s"><tr><th style="text-align:left">Group</th><th>Return a year</th><th>Volatility</th><th>Worst drop</th></tr>
 ${grp("Growth Quality Score (v4)",["Q1","Q2","Q3","Q4","Q5","TOP50"])}${grp("Quick fair value (Monthly Top 5 method)",["V1","V2","V3","V4","V5"])}${grp("Risk level",["NORMAL","HIGH"])}${grp("Combined",["TOP50_CHEAP"])}${grp("Baselines",["ALL","SPY","RSP"])}</table></div>
 <p class="muted">Coverage: ${R.coverage[0].scored} of ${R.coverage[0].members} members scored in ${R.coverage[0].date.slice(0,4)}, ${R.coverage[n-1].scored} of ${R.coverage[n-1].members} in ${R.coverage[n-1].date.slice(0,4)} (the rest lack SEC data or prices). Not investment advice.</p>`;
const svg=$("#btsvg"),xl=$("#btx"),tip=$("#bttip");
svg.addEventListener("mousemove",e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W;let i=Math.round((x-pl)/(W-pl-pr)*n)-1;i=Math.max(0,Math.min(n-1,i));
 xl.setAttribute("x1",X(i+1));xl.setAttribute("x2",X(i+1));xl.style.display="";tip.style.display="";tip.style.left=Math.min(r.width-190,(X(i+1)/W)*r.width+8)+"px";
 tip.innerHTML=`<b>${D[i]}</b>`+SER.map(([k,c])=>`<div><i style="background:${c}"></i>${LAB[k].split(" (")[0]}: ${G[k].cum[i].toFixed(2)}× <span class="muted">(${pc(G[k].returns[i])} qtr)</span></div>`).join("")});
svg.addEventListener("mouseleave",()=>{xl.style.display="none";tip.style.display="none"});
})();
