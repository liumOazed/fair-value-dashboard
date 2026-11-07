(async function(){
const $=s=>document.querySelector(s);
const root=document.documentElement;try{const t=localStorage.getItem("theme");if(t)root.dataset.theme=t}catch(e){}
$("#theme").onclick=()=>{const dark=getComputedStyle(root).getPropertyValue("--bg").trim()==="#0b1020";const n=dark?"light":"dark";root.dataset.theme=n;try{localStorage.setItem("theme",n)}catch(e){}};
const usd=n=>n==null?"–":"$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const M=["January","February","March","April","May","June","July","August","September","October","November","December"];
const nice=m=>M[+m.slice(5)-1]+" "+m.slice(0,4);
{const t=$("#tscroll"),b=$("#bscroll");let lock=0;t.onscroll=()=>{if(lock){lock=0;return}lock=1;b.scrollLeft=t.scrollLeft};b.onscroll=()=>{if(lock){lock=0;return}lock=1;t.scrollLeft=b.scrollLeft}}
function sync(){const t=$("#tscroll"),b=$("#bscroll"),w=$("#tbl").scrollWidth;$("#tspacer").style.width=w+"px";t.style.display=w>b.clientWidth+2?"":"none"}
window.addEventListener("resize",sync);
let R=null;
try{R=await fetch("data/russell.json?"+Date.now()).then(r=>{if(!r.ok)throw 0;return r.json()})}catch(e){}
if(!R||!R.rows){$("#tbl tbody").innerHTML='<tr><td colspan="11" class="err">No Russell 2000 screen yet. It runs on the 2nd of each month, or by hand: Actions → Russell 2000 screen → Run workflow.</td></tr>';$("#gate").style.display="none";return}
const top=R.rows.filter(r=>r.top50);
const valued=top.filter(r=>r.fair_value);
const below=valued.filter(r=>r.price_at_eval<=r.fair_value);
$("#sub").textContent=`Russell 2000 small caps · ${nice(R.month)}`;
$("#stamp").textContent=`built ${R.built} · members as of ${R.members_as_of||"?"} · required return = sector rate + ${(R.small_cap_premium*100).toFixed(0)} pts`;
$("#kpis").innerHTML=[["Members screened",R.screened,"IWM holdings as of "+(R.members_as_of||"?")],["Passed the quality gate",R.passed,`${Math.round(R.passed/R.screened*100)}% of the index`],
 ["Top 50 with a quick fair value",valued.length,"the rest fail a sanity filter"],["At or below fair value",below.length,"of those valued"]]
 .map(k=>`<div class="kpi"><div class="l">${k[0]}</div><div class="v">${k[1]}</div><div class="s">${k[2]}</div></div>`).join("");
let view="Top 50";
const views=["Top 50","Valued only","Check first","All that passed"];
$("#vchips").innerHTML='<span class="lbl">Show</span>'+views.map(v=>`<button class="chip${v===view?" on":""}" data-v="${v}">${v}</button>`).join("");
$("#vchips").querySelectorAll(".chip").forEach(c=>c.onclick=()=>{view=c.dataset.v;$("#vchips").querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x===c));render()});
let checks="All",sec="All";
// Sector filter. Insurers can't answer the cash-flow and debt questions (N/A); inside the Insurance filter N/A counts
// as passed, the same rule as the Growth Screen's Insurance top 5. Everywhere else the checks stay strict.
const SEC={"All":null,"Insurance":r=>(r.industry||"").includes("Insurance")};
const naOk=()=>sec==="Insurance";
const yesN=r=>(r.answers||[]).filter(x=>x.v==="yes"||(naOk()&&x.v==="na")).length;
const allOk=r=>naOk()?(r.answers||[]).length>0&&yesN(r)===r.answers.length:r.all_checks;
const CHK={"All":null,"Passes at least 4 checks":r=>yesN(r)>=4,"Passes all 5 checks":allOk};
const CTIP={"Passes at least 4 checks":"Yes to at least four of the five quick questions (all five also count). Hover the Checks badge for which one missed","Passes all 5 checks":"Yes to all five quick questions: revenue growing, profits healthy, cash flow strong, debt manageable, financial position improving"};
const STIP={"Insurance":"Insurers only (industry contains Insurance, brokers included). The cash-flow and debt questions don't apply to them, so N/A counts as passed in the Checks filters"};
$("#schips").innerHTML='<span class="lbl">Sector</span>'+Object.keys(SEC).map(v=>`<button class="chip${v===sec?" on":""}" data-v="${v}"${STIP[v]?` title="${STIP[v]}"`:""}>${v}${SEC[v]?` <span class="cnt">${R.rows.filter(SEC[v]).length}</span>`:""}</button>`).join("");
$("#schips").querySelectorAll(".chip").forEach(c=>c.onclick=()=>{sec=c.dataset.v;$("#schips").querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x===c));drawChecks();render()});
function drawChecks(){
 const base=SEC[sec]?R.rows.filter(SEC[sec]):R.rows;
 $("#cchips").innerHTML='<span class="lbl">Checks</span>'+Object.keys(CHK).map(v=>`<button class="chip${v===checks?" on":""}" data-v="${v}"${CTIP[v]?` title="${CTIP[v]}${naOk()?" (N/A counts as passed for insurers)":""}"`:""}>${v}${CHK[v]?` <span class="cnt">${base.filter(CHK[v]).length}</span>`:""}</button>`).join("");
 $("#cchips").querySelectorAll(".chip").forEach(c=>c.onclick=()=>{checks=c.dataset.v;$("#cchips").querySelectorAll(".chip").forEach(x=>x.classList.toggle("on",x===c));render()});
}
drawChecks();
const chkPill=r=>{const a=r.answers||[];if(!a.length)return "";const y=yesN(r),ok=allOk(r);
 return ` <span class="pill${ok?" chk":""}" title="${esc(a.map(x=>x.q+" "+x.v+": "+x.t).join("\n"))}${naOk()?"\n(N/A counts as passed for insurers)":""}">${y}/5${ok?" ✓":""}</span>`};
function render(){
 let list=view==="Top 50"?top:view==="Valued only"?valued:view==="Check first"?top.filter(r=>r.check_first):R.rows;
 if(SEC[sec])list=list.filter(SEC[sec]);
 if(CHK[checks])list=list.filter(CHK[checks]);
 $("#tbl tbody").innerHTML=list.map(r=>{
  const p=r.parts||{};const diff=r.fair_value&&r.price_at_eval?r.price_at_eval/r.fair_value-1:null;
  const note=r.fv_skip?esc(r.fv_skip):(r.flags||[]).concat(r.risks||[]).map(esc).join(" · ");
  const months=r.months_in_top50>1?` <span class="pill ok">${r.months_in_top50} months in top 50</span>`:"";
  return `<tr><td>${r.rank}</td><td><b>${esc(r.ticker)}</b><div class="nm">${esc(r.name)}${months}${chkPill(r)}</div></td><td>${esc(r.sector)}<div class="nm">${esc(r.industry)}</div></td>
   <td class="r">${r.score.toFixed(1)}</td><td class="r">${[p.quality,p.growth,p.value,p.resilience].map(x=>x==null?"–":x).join(" · ")}</td>
   <td class="r">${r.market_cap_b==null?"–":"$"+r.market_cap_b.toFixed(1)+"B"}</td><td class="r">${usd(r.price_at_eval)}</td><td class="r">${usd(r.fair_value)}</td><td class="r">${usd(r.buy_below)}</td>
   <td class="r">${diff==null?"–":(diff>0?"+":"")+(diff*100).toFixed(0)+"%"}</td><td class="nm">${note}</td></tr>`}).join("")||'<tr><td colspan="11" class="muted">Nothing in this view.</td></tr>';
 sync();
}
render();
const g=Object.entries(R.gate_failed||{}).sort((a,b)=>b[1]-a[1]);
$("#gate").innerHTML=`<h2>Why most of the index is left out</h2><p class="muted">${R.screened-R.passed} of ${R.screened} stocks failed the quality gate (first failed test shown).</p>
 <table><tbody>${g.map(([k,v])=>`<tr><td>${esc(k)}</td><td class="r">${v}</td></tr>`).join("")}</tbody></table>`;
})();
