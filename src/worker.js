// One Cloudflare Worker serves the static UI and a secure API backed by R2.
// Input jobs are capability-addressed: the unguessable audit ID is required to read results.
const jsonHeaders = {"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"};
function json(value, status=200) {return new Response(JSON.stringify(value), {status, headers:jsonHeaders});}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function safeUrl(raw){
  if(typeof raw!=="string" || raw.length>2048)return null;
  let u; try{u=new URL(raw.trim());}catch{return null;}
  if(!["https:","http:"].includes(u.protocol) || u.username || u.password)return null;
  if(u.port && !["80","443"].includes(u.port))return null;
  const h=u.hostname.toLowerCase();
  if(!h.includes(".") || h==="localhost" || h.endsWith(".localhost") || h.endsWith(".local") || h.endsWith(".internal") || h.endsWith(".test"))return null;
  if(/^\d+\.\d+\.\d+\.\d+$/.test(h) || h.includes(":"))return null;
  if(!/^[a-z0-9.-]+$/.test(h) || h.split(".").some(p=>!p || p.length>63 || p.startsWith("-") || p.endsWith("-")))return null;
  u.hash=""; return u.href;
}
async function verifyTurnstile(token,request,env){
  if(!env.TURNSTILE_SECRET_KEY || !token)return false;
  const body=new URLSearchParams({secret:env.TURNSTILE_SECRET_KEY,response:String(token),remoteip:request.headers.get("CF-Connecting-IP")||""});
  const r=await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify",{method:"POST",body,headers:{"content-type":"application/x-www-form-urlencoded"}});
  if(!r.ok)return false;
  const result=await r.json();
  const expected=new URL(request.url).hostname;
  return result.success===true && (result.hostname===expected || (expected.endsWith(".workers.dev") && result.hostname===expected));
}
async function createAudit(request,env){
  if(!env.GITHUB_TOKEN || !env.GITHUB_OWNER || !env.GITHUB_REPO || !env.TURNSTILE_SECRET_KEY) return json({error:"Server configuration incomplete"},503);
  const type=request.headers.get("content-type")||"";
  if(!type.includes("application/json"))return json({error:"Expected application/json"},415);
  let input;try {if(Number(request.headers.get("content-length")||0)>12000)return json({error:"Payload too large"},413);input=await request.json();}catch{return json({error:"Invalid JSON"},400);}
  const website=safeUrl(input?.website);
  if(!website)return json({error:"Provide a valid public website URL with https://"},400);
  const extra=Array.isArray(input?.extra_urls)?input.extra_urls:[];
  if(extra.length>8)return json({error:"Maximum eight additional URLs"},400);
  const extraUrls=extra.map(safeUrl);
  if(extraUrls.includes(null))return json({error:"An additional URL is invalid"},400);
  const turnstileOk=await verifyTurnstile(input?.turnstile_token,request,env).catch(()=>false);
  if(!turnstileOk)return json({error:"Verification failed; retry the security challenge"},403);
  const auditId=crypto.randomUUID();
  const payload={audit_id:auditId,website,extra_urls:[...new Set(extraUrls)],created_at:new Date().toISOString()};
  await env.AUDITS.put(`audits/${auditId}/input.json`,JSON.stringify(payload),{httpMetadata:{contentType:"application/json"}});
  const path=`https://api.github.com/repos/${encodeURIComponent(env.GITHUB_OWNER)}/${encodeURIComponent(env.GITHUB_REPO)}/actions/workflows/audit.yml/dispatches`;
  let response;
  try{
    response=await fetch(path,{method:"POST",headers:{"Accept":"application/vnd.github+json","Authorization":`Bearer ${env.GITHUB_TOKEN}`,"X-GitHub-Api-Version":"2026-03-10","User-Agent":"AI-Ritual-Audit"},body:JSON.stringify({ref:env.GITHUB_REF||"main",inputs:{audit_id:auditId}})});
  }catch{response=null;}
  if(!response?.ok){
    await env.AUDITS.delete(`audits/${auditId}/input.json`);
    return json({error:"Could not start the GitHub workflow. Check GitHub token, repository, workflow and branch."},502);
  }
  return json({audit_id:auditId,status:"queued",url:`/report/${auditId}`},202);
}
async function readAudit(id,env){
  const complete=await env.AUDITS.get(`audits/${id}/result.json`);
  if(complete)return new Response(complete.body,{headers:jsonHeaders});
  const initial=await env.AUDITS.get(`audits/${id}/input.json`);
  if(!initial)return json({error:"Audit not found"},404);
  const progress=await env.AUDITS.get(`audits/${id}/progress.json`);
  const state=progress?await progress.json():{status:"queued",message:"Waiting for GitHub Actions"};
  return json({audit_id:id,website:(await initial.json()).website,...state},202);
}
async function readPdf(id,env){
  const obj=await env.AUDITS.get(`audits/${id}/report.pdf`);
  if(!obj)return json({error:"PDF not ready"},404);
  return new Response(obj.body,{headers:{"content-type":"application/pdf","content-disposition":`attachment; filename="AI-Ritual-SEO-GEO-${id.slice(0,8)}.pdf"`,"cache-control":"private, no-store","x-content-type-options":"nosniff"}});
}
export default {async fetch(request,env){
  const url=new URL(request.url);const path=url.pathname;
  if(path.startsWith("/api/")){
    if(request.method==="GET" && path==="/api/config")return json({turnstile_site_key:env.TURNSTILE_SITE_KEY||""});
    if(request.method==="POST" && path==="/api/audits")return createAudit(request,env);
    const match=path.match(/^\/api\/audits\/([^/]+)(?:\/(pdf))?$/);
    if(match){
      if(request.method!=="GET")return json({error:"Method not allowed"},405);
      const id=match[1];if(!UUID.test(id))return json({error:"Invalid audit ID"},400);
      return match[2]?readPdf(id,env):readAudit(id,env);
    }
    return json({error:"Endpoint not found"},404);
  }
  // Reports load the same SPA shell and retrieve report data using the audit id.
  if(request.method==="GET" && /^\/report\/[0-9a-f-]{36}\/?$/i.test(path)){
    const copy=new URL(request.url);copy.pathname="/index.html";
    return env.ASSETS.fetch(new Request(copy.toString(),request));
  }
  return env.ASSETS.fetch(request);
}};
