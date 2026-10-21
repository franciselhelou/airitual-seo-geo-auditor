const $ = id => document.getElementById(id);
const htmlEscape = v => String(v ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
const safeLink = v => {try{const u=new URL(String(v));return ["http:","https:"].includes(u.protocol)?u.href:"#";}catch{return "#";}};
let currentReport=null, chart=null, turnstileWidget=null, turnstileToken="", activeId="", polling=null;
function show(id){["landing","job-progress","report"].forEach(x=>$(x).hidden=x!==id);}
function dateText(t){if(!t)return "";const d=new Date(t);return isNaN(d)?String(t):d.toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"});}
function scoreCard(label,value){const valid=Number.isFinite(value);const display=valid?Math.round(value)+"%":"N/A";return `<div class="score-card"><div class="score-title">${htmlEscape(label)}</div><div class="score-value ${valid?'':'score-none'}">${display}</div><div class="score-track"><span style="width:${valid?Math.max(0,Math.min(100,value)):0}%"></span></div></div>`;}
function renderReport(r,isDemo=false){
  clearInterval(polling);currentReport=r;show("report");$("demo-warning").hidden=!isDemo;
  $("report-heading").textContent=r.website||"Website audit";
  $("report-meta").textContent=`Completed ${dateText(r.completed_at)} · ${r.coverage?.pages_crawled||0} pages crawled · SEO / GEO evidence-based analysis`;
  const scores=r.scores||{};
  $("score-grid").innerHTML=[["Overall health",scores.overall],["Technical SEO",scores.technical],["Content quality",scores.content],["GEO readiness",scores.geo]].map(x=>scoreCard(...x)).join("");
  const findings=r.findings||[];
  const counter=s=>findings.filter(f=>f.severity===s).length;
  const kpis=[[findings.length,"Total findings"],[counter("critical"),"Critical issues"],[counter("high"),"High priority"],[counter("info"),"Improvement opportunities"]];
  $("kpi-grid").innerHTML=kpis.map(([n,label])=>`<div class="kpi-card"><div class="kpi-number">${n}</div><div class="kpi-caption">${htmlEscape(label)}</div></div>`).join("");
  $("executive-summary").textContent=r.summary||"The audit did not produce an executive summary.";
  const coverage=r.coverage||{};
  $("coverage").innerHTML=[["Pages crawled",coverage.pages_crawled],["URLs discovered",coverage.urls_discovered],["URLs failed",coverage.pages_failed],["External sources",(r.external_profiles||[]).length]].map(([label,n])=>`<div class="mini-metric"><b>${htmlEscape(n??"—")}</b>${label}</div>`).join("");
  const counts={};for(const f of findings)counts[f.category||"Other"]=(counts[f.category||"Other"]||0)+1;
  const labels=Object.keys(counts);const data=Object.values(counts);const fallback=$("chart-fallback");fallback.textContent="";
  if(chart){chart.destroy();chart=null;}
  $("issue-chart").style.display="";
  if(window.Chart && data.length){chart=new window.Chart($("issue-chart"),{type:"bar",data:{labels,datasets:[{label:"Findings",data,backgroundColor:"#e65160",borderRadius:5,maxBarThickness:38}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:"y",plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,ticks:{precision:0},grid:{color:"#edf1f5"}},y:{grid:{display:false}}}}});}
  else {$("issue-chart").style.display="none";fallback.innerHTML=labels.map((k,i)=>`<p>${htmlEscape(k)}: ${data[i]}</p>`).join("")||"No findings";}
  const sections=[["overview","Overview"],["findings","Findings"],["action-plan","Action plan"],["pages","Pages"],["external","External sources"],["method","Methodology"]];
  $("section-nav").innerHTML=sections.map(([id,label])=>`<a href="#${id}">${label}</a>`).join("");
  const cats=[...new Set(findings.map(f=>f.category||"Other"))].sort();$("category-filter").innerHTML='<option value="">All categories</option>'+cats.map(c=>`<option value="${htmlEscape(c)}">${htmlEscape(c)}</option>`).join("");
  ["severity-filter","category-filter","finding-search"].forEach(id=>{$(id).value="";$(id).oninput=renderFindings;});renderFindings();
  const phases=r.roadmap||[];$("roadmap").innerHTML=phases.length?phases.map(p=>`<div class="roadmap-group"><h3>${htmlEscape(p.period)}</h3><ul>${(p.tasks||[]).map(t=>`<li>${htmlEscape(t)}</li>`).join("")}</ul></div>`).join(""):"No roadmap generated.";
  $("pages-tbody").innerHTML=(r.pages||[]).map(p=>`<tr><td><a href="${htmlEscape(safeLink(p.url))}" target="_blank" rel="noopener noreferrer">${htmlEscape(p.url)}</a></td><td>${htmlEscape(p.status)}</td><td>${htmlEscape(p.word_count)}</td><td>${htmlEscape(p.title||"—")}</td></tr>`).join("")||'<tr><td colspan="4">No pages were collected.</td></tr>';
  $("external-list").innerHTML=(r.external_profiles||[]).map(p=>`<div class="profile"><a href="${htmlEscape(safeLink(p.url))}" target="_blank" rel="noopener noreferrer">${htmlEscape(p.url)}</a><span class="status-pill">${htmlEscape(p.access||"not tested")}</span>${p.note?`<div class="muted small">${htmlEscape(p.note)}</div>`:""}</div>`).join("")||'<p class="muted">No additional sources were submitted.</p>';
  $("limitations").innerHTML=(r.limitations||[]).map(s=>`<p class="method-note">${htmlEscape(s)}</p>`).join("");
  $("pdf-link").href=isDemo?"#":`/api/audits/${encodeURIComponent(activeId)}/pdf`;
  $("pdf-link").onclick=isDemo?e=>{e.preventDefault();alert("Sample preview only. Run a live audit to download the PDF.");}:null;
  document.title=`${r.website} | AI Ritual Audit`;
  window.scrollTo({top:0,behavior:"instant"});
}
function renderFindings(){
  if(!currentReport)return;
  const severity=$("severity-filter").value,category=$("category-filter").value,q=$("finding-search").value.toLowerCase().trim();
  const items=(currentReport.findings||[]).filter(f=>(!severity||f.severity===severity)&&(!category||f.category===category)&&(!q||JSON.stringify(f).toLowerCase().includes(q)));
  $("finding-count").textContent=`Showing ${items.length} of ${(currentReport.findings||[]).length} findings`;
  $("findings-list").innerHTML=items.map(f=>`<details class="finding"><summary><span class="severity ${htmlEscape(f.severity)}">${htmlEscape(f.severity)}</span><span><span class="finding-title">${htmlEscape(f.title)}</span><br><span class="finding-cat">${htmlEscape(f.category)} · ${htmlEscape(f.effort||"Effort not estimated")}</span></span></summary><div class="finding-body"><div class="label">Affected page</div><p><a href="${htmlEscape(safeLink(f.url))}" target="_blank" rel="noopener noreferrer">${htmlEscape(f.url||"Not applicable")}</a></p><div class="label">Evidence</div><p>${htmlEscape(f.evidence||"Not available")}</p><div class="label">Why it matters</div><p>${htmlEscape(f.why||"Not specified")}</p><div class="label">Recommended correction</div><p>${htmlEscape(f.recommendation||"Not specified")}</p>${f.confidence?`<span class="small muted">Evidence confidence: ${htmlEscape(f.confidence)}</span>`:""}</div></details>`).join("")||'<p class="muted">No matching findings.</p>';
}
async function loadAudit(id){activeId=id;currentReport=null;$("pdf-link").hidden=false;show("job-progress");$("progress-url").textContent=`Audit reference: ${id}`;
  const tick=async()=>{try{const r=await fetch(`/api/audits/${encodeURIComponent(id)}`,{cache:"no-store"});const data=await r.json();if(!r.ok)throw Error(data.error||"Could not load audit");if(data.status==="complete"||data.status==="failed"){renderReport(data);if(data.status==="failed"){$("pdf-link").hidden=true;}return;}
    $("progress-title").textContent=data.status==="running"?"Audit in progress":"Audit queued";
    $("progress-message").textContent=data.message||"Processing website";
  }catch(e){$("progress-message").textContent=`${e.message}. You may retry by reloading this URL.`;}};
  await tick();if(!currentReport){polling=setInterval(tick,5000);}
}
async function submitAudit(e){e.preventDefault();$("submit-error").hidden=true;const button=$("submit-button");button.disabled=true;button.textContent="Starting audit…";
  const extras=$("extra-urls").value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  try{if(extras.length>8)throw Error("Use no more than eight additional URLs.");
    const res=await fetch("/api/audits",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({website:$("website").value.trim(),extra_urls:extras,turnstile_token:turnstileToken})});
    const data=await res.json();if(!res.ok)throw Error(data.error||"Could not submit audit");
    history.pushState({},"",`/report/${data.audit_id}`);await loadAudit(data.audit_id);
  }catch(err){$("submit-error").textContent=err.message;$("submit-error").hidden=false;window.turnstile?.reset(turnstileWidget);turnstileToken="";}
  finally{button.textContent="Run comprehensive audit →";button.disabled=false;}
}
async function init(){
  $("audit-form").addEventListener("submit",submitAudit);
  $("copy-link").addEventListener("click",()=>{navigator.clipboard?.writeText(location.href).then(()=>{$("copy-link").textContent="Copied!";setTimeout(()=>{$("copy-link").textContent="Copy report link";},2000);});});
  $("sample-link").addEventListener("click",async e=>{e.preventDefault();try{const r=await fetch("/sample-report.json");renderReport(await r.json(),true);}catch{alert("Sample report unavailable");}});
  const pathname=location.pathname.match(/^\/report\/([0-9a-f-]{36})\/?$/i);
  if(pathname){await loadAudit(pathname[1]);return;}
  try{const response=await fetch("/api/config");const conf=await response.json();const key=conf.turnstile_site_key;
    if(!key || key.startsWith("REPLACE_"))throw Error("Turnstile site key is not configured.");
    const script=document.createElement("script");script.src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.onload=()=>{turnstileWidget=window.turnstile.render("#turnstile-container",{sitekey:key,callback:token=>{turnstileToken=token;$("submit-button").disabled=false;},"expired-callback":()=>{turnstileToken="";$("submit-button").disabled=true;}});$("turnstile-message").textContent="";};
    script.onerror=()=>{$("turnstile-message").textContent="Could not load Cloudflare verification.";};document.head.append(script);
  }catch(e){$("turnstile-message").textContent=e.message;}
}
init();
