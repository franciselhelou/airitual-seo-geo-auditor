import assert from 'node:assert/strict';
import worker from '../src/worker.js';

class FakeR2 {
  constructor(){this.map=new Map();}
  async put(k,v){this.map.set(k,v);}
  async get(k){const v=this.map.get(k);return v?{body:v,json:async()=>JSON.parse(typeof v==='string'?v:new TextDecoder().decode(v))}:null;}
  async delete(k){this.map.delete(k);}
}
const env={
  AUDITS:new FakeR2(),ASSETS:{fetch:async()=>new Response('<h1>Static assets</h1>')},
  TURNSTILE_SITE_KEY:'test',TURNSTILE_SECRET_KEY:'secret',
  GITHUB_TOKEN:'private_token',GITHUB_OWNER:'owner',GITHUB_REPO:'airitual-seo-geo-auditor',GITHUB_REF:'main'
};
const originalFetch=globalThis.fetch;
globalThis.fetch=async (url,opts)=>{
  if(String(url).includes('siteverify'))return new Response(JSON.stringify({success:true,hostname:'audit.example.com'}),{status:200});
  if(String(url).includes('api.github.com')){
    assert.equal(opts.method,'POST');
    assert.equal(JSON.parse(opts.body).ref,'main');
    return new Response(JSON.stringify({workflow_run_id:42}),{status:200});
  }
  throw Error('Unexpected external call: '+url);
};
try {
  const config=await worker.fetch(new Request('https://audit.example.com/api/config'),env);
  assert.equal((await config.json()).turnstile_site_key,'test');
  const result=await worker.fetch(new Request('https://audit.example.com/api/audits/invalid'),env);
  assert.equal(result.status,400);
  const notFound=await worker.fetch(new Request('https://audit.example.com/api/audits/ab1aaa11-2222-4444-8888-666666666666'),env);
  assert.equal(notFound.status,404);
  const rejected=await worker.fetch(new Request('https://audit.example.com/api/audits',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({website:'http://localhost/',turnstile_token:'abc'})}),env);
  assert.equal(rejected.status,400);
  const submitted=await worker.fetch(new Request('https://audit.example.com/api/audits',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({website:'https://example.com/',extra_urls:['https://yelp.com/'],turnstile_token:'abc'})}),env);
  assert.equal(submitted.status,202);
  const {audit_id:id}=await submitted.json();
  assert.match(id,/^[0-9a-f-]{36}$/);
  const queued=await worker.fetch(new Request('https://audit.example.com/api/audits/'+id),env);
  assert.equal(queued.status,202);
  await env.AUDITS.put(`audits/${id}/result.json`,JSON.stringify({status:'complete',audit_id:id}));
  await env.AUDITS.put(`audits/${id}/report.pdf`,new TextEncoder().encode('%PDF fake'));
  const complete=await worker.fetch(new Request('https://audit.example.com/api/audits/'+id),env);
  assert.equal((await complete.json()).status,'complete');
  const pdf=await worker.fetch(new Request('https://audit.example.com/api/audits/'+id+'/pdf'),env);
  assert.equal(pdf.status,200); assert.equal(pdf.headers.get('content-type'),'application/pdf');
  console.log('Worker API dispatch, queue, results and PDF download tests passed.');
} finally {globalThis.fetch=originalFetch;}
