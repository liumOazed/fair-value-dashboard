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
