// Monthly run panel: "Calculate Top Growth" and "Evaluate Fair Value" buttons with once-a-month status.
// The site is static, so a button opens the GitHub "Run workflow" page; the workflow itself enforces the lock.
window.RunPanel=async function(el){
 const WF="https://github.com/liumOazed/fair-value-dashboard/actions/workflows/monthly.yml";
 const M=["January","February","March","April","May","June","July","August","September","October","November","December"];
 const nice=m=>m?M[+m.slice(5)-1]+" "+m.slice(0,4):"–";
 let R={};try{R=await fetch("data/runs.json?"+Date.now()).then(r=>r.json())}catch(e){}
 const g=R.growth||{},f=R.fair_value||{},dm=R.latest_data_month,cal=new Date().toISOString().slice(0,7);
 const newMonth=!dm||cal>dm;
 const gDone=!newMonth&&!!g[dm],fDone=!newMonth&&!!f[dm];
 const day=s=>s?s.slice(0,10):"";
 const btn=(label,done,blocked,doneTxt,hint)=>`<div class="runbox${done?" done":""}">
   ${done?`<button class="runbtn" disabled>✓ ${label}</button>`:blocked?`<button class="runbtn" disabled>${label}</button>`:`<a class="runbtn" href="${WF}" target="_blank" rel="noopener">${label}</a>`}
   <div class="muted">${done?doneTxt:hint}</div></div>`;
 el.innerHTML=`<div class="card-head"><h2>Monthly run</h2><span class="muted">data month: ${nice(dm)} · each step runs once a month</span></div>
 <div class="runrow">
 ${btn("Calculate Top Growth",gDone,false,`Done for ${nice(dm)} on ${day((g[dm]||{}).ran)}. Locked until next month.`,
   newMonth?`New month: upload <code>growth_screen_results_${cal}.csv</code> to <code>data/screens/</code> (that runs both steps automatically), or click to run.`:"Opens GitHub: choose <b>growth</b> and press Run workflow.")}
 ${btn("Evaluate Fair Value",fDone,!gDone&&!newMonth,`Done for ${nice(dm)} on ${day((f[dm]||{}).ran)}: ${((f[dm]||{}).picks||[]).join(", ")}. Locked until next month.`,
   !gDone&&!newMonth?"Run Calculate Top Growth first.":"Opens GitHub: choose <b>fair_value</b> and press Run workflow.")}
 </div>`;
};
