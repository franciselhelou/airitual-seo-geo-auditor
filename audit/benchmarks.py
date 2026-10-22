"""Public AI discovery benchmarking: provider status, traceable sources and validity.

Citation attribution MUST come from provider source metadata, not bracketed [1]
text, generated Markdown links, or the fact an answer mentions the site.
"""
import os
import re
from urllib.parse import urlparse
import requests

TIMEOUT=65

def _host(url):
    try:return (urlparse(url).hostname or '').lower().removeprefix('www.')
    except Exception:return ''

def _dedupe_cites(items):
    seen=set();out=[]
    for item in items:
        u=item.get('url','') if isinstance(item,dict) else str(item)
        if urlparse(u).scheme not in ('http','https') or u in seen:continue
        out.append({'url':u,'title':str(item.get('title',''))[:160] if isinstance(item,dict) else ''})
        seen.add(u)
    return out[:24]

def _citations_from_openai(raw):
    answers=[];cites=[]
    for item in raw.get('output',[]):
        if item.get('type')!='message':continue
        for block in item.get('content',[]):
            if block.get('type') not in ('output_text','text'):continue
            answers.append(block.get('text',''))
            for a in block.get('annotations',[]):
                if a.get('type') in ('url_citation','citation'):
                    cites.append({'url':a.get('url',''),'title':a.get('title','')})
    return '\n'.join(answers),_dedupe_cites(cites)

def _citations_from_perplexity(raw):
    """Agent API sources arrive as `output[]` search_results, often NOT annotations."""
    answer,annotations=_citations_from_openai(raw)
    found=list(annotations)
    metadata_present=False
    for item in raw.get('output',[]):
        if item.get('type')!='search_results':continue
        metadata_present=True
        sources=item.get('results',item.get('search_results',[]))
        if isinstance(sources,dict):sources=sources.get('results',[])
        if isinstance(sources,list):
            for result in sources:
                if isinstance(result,dict) and result.get('url'):
                    found.append({'url':result['url'],'title':result.get('title','')})
    return answer,_dedupe_cites(found),metadata_present or bool(annotations)

def _http_error(exc):
    response=getattr(exc,'response',None)
    status=getattr(response,'status_code',None)
    err={}
    if response is not None:
        try:
            data=response.json()
            err=data.get('error',{}) if isinstance(data,dict) else {}
            if isinstance(err,str):err={'message':err}
        except (ValueError,TypeError,AttributeError):pass
    # Never include auth headers, request payloads, or unfiltered provider bodies.
    return {'status':'api_error','http_status':status,'error_code':str(err.get('code') or err.get('status') or 'unknown')[:90],
            'error_type':str(err.get('type') or type(exc).__name__)[:90],
            'error_message':str(err.get('message') or 'Provider request failed')[:200], 'target_cited':None}

def _openai(question):
    key=os.getenv('OPENAI_API_KEY','')
    if not key:return {'status':'not_configured'}
    model=os.getenv('OPENAI_WEB_MODEL') or os.getenv('OPENAI_MODEL') or 'gpt-5-mini'
    body={'model':model,'input':question,'tools':[{'type':'web_search','search_context_size':'medium'}],
          'tool_choice':'required','max_output_tokens':2500}
    if model in ('gpt-5','gpt-5-mini','gpt-5-nano'):body['reasoning']={'effort':'low'}
    r=requests.post('https://api.openai.com/v1/responses',json=body,
                    headers={'Authorization':f'Bearer {key}'},timeout=TIMEOUT)
    r.raise_for_status();raw=r.json();answer,cites=_citations_from_openai(raw)
    searched=any(x.get('type')=='web_search_call' for x in raw.get('output',[]))
    return {'status':'completed' if raw.get('status')=='completed' and searched else 'not_measured',
            'answer':answer[:3500], 'citations':cites,'citation_metadata_valid':bool(cites) and searched,
            'search_executed':searched,'model':model,'usage':raw.get('usage') or {}}

def _perplexity(question):
    key=os.getenv('PERPLEXITY_API_KEY','')
    if not key:return {'status':'not_configured'}
    r=requests.post('https://api.perplexity.ai/v1/agent',
                    headers={'Authorization':f'Bearer {key}'},json={'preset':'fast-search','input':question},timeout=TIMEOUT)
    r.raise_for_status();raw=r.json();answer,cites,metadata=_citations_from_perplexity(raw)
    return {'status':'completed' if raw.get('status')=='completed' and answer else 'not_measured',
            'answer':answer[:3500],'citations':cites,'citation_metadata_valid':metadata and bool(cites),
            'model':raw.get('model','agent:fast-search'),'usage':raw.get('usage') or {}}

def _gemini(question):
    key=os.getenv('GEMINI_API_KEY','')
    if not key:return {'status':'not_configured'}
    model=os.getenv('GEMINI_MODEL') or 'gemini-3.8-flash'
    r=requests.post('https://generativelanguage.googleapis.com/v1beta/interactions',
        headers={'x-goog-api-key':key},json={'model':model,'input':question,
         'tools':[{'type':'google_search'}]},timeout=TIMEOUT)
    r.raise_for_status();raw=r.json();answer=[];cites=[]
    searched=any(x.get('type')=='google_search_call' for x in raw.get('steps',[]))
    for step in raw.get('steps',[]):
        if step.get('type')!='model_output':continue
        for part in step.get('content',[]):
            if part.get('type')!='text':continue
            answer.append(part.get('text',''))
            for a in part.get('annotations',[]):
                if a.get('type')=='url_citation':cites.append({'url':a.get('url',''),'title':a.get('title','')})
    citations=_dedupe_cites(cites)
    return {'status':'completed' if answer and searched else 'not_measured',
            'answer':'\n'.join(answer)[:3500],'citations':citations,
            'citation_metadata_valid':searched and bool(citations), 'search_executed':searched,
            'model':model,'usage':raw.get('usage') or {}}

PROVIDERS={'openai':_openai,'perplexity':_perplexity,'gemini':_gemini}

def _assess_answer(answer,context):
    text=' '.join(str(answer or '').split())
    if len(text)<90:return False,'too_short'
    lowered=text.casefold()
    if re.search(r'(which|what|tell me the|specify the|need the) (city|town|county|location)',lowered):
        return False,'asks_for_missing_location'
    if re.search(r'(i (can|could) help|please provide) .{0,75}(city|location|municipality)',lowered):
        return False,'asks_for_missing_location'
    return True,'substantive_response'

def run_benchmarks(website,questions,progress=lambda x:None):
    limit=max(0,min(8,int(os.getenv('AUDIT_BENCHMARK_QUESTIONS') or '6')))
    selected=[]
    for q in questions:
        if not isinstance(q,dict):continue
        if q.get('question') and q.get('context') and q.get('evidence_url') and q['context'].casefold() in q['question'].casefold():
            if q['question'] not in [x['question'] for x in selected]:selected.append(q)
    selected=selected[:limit]
    target=_host(website);results=[]
    for provider,fn in PROVIDERS.items():
        for spec in selected:
            progress(f'Public AI citation benchmark: {provider} question {sum(x["provider"]==provider for x in results)+1}/{len(selected)}')
            try:
                record=fn(spec['question'])
                if record.get('status')=='completed':
                    valid,reason=_assess_answer(record.get('answer',''),spec['context'])
                    record['valid_answer']=valid;record['validation_reason']=reason
                    if not valid:record['status']='invalid_answer'
                    elif record.get('citation_metadata_valid') is False or not record.get('citations'):
                        record['status']='unverifiable_sources'
                        record['validation_reason']='Provider response lacked verified source metadata'
                if record.get('status')=='completed' and record.get('valid_answer'):
                    record['target_cited']=any((_host(c['url'])==target or _host(c['url']).endswith('.'+target)) for c in record['citations'])
                else:record['target_cited']=None
            except requests.HTTPError as e:
                record=_http_error(e)
            except (ValueError,TypeError,requests.RequestException) as e:
                record={'status':'api_error','error_type':type(e).__name__,'error_message':str(e)[:150], 'target_cited':None}
            results.append({'provider':provider,**spec,**record})
    valid=[r for r in results if r.get('status')=='completed' and r.get('valid_answer') and r.get('target_cited') is not None]
    byprovider={name:{'tests_completed':sum(x['provider']==name for x in valid),
                      'target_cited':sum(x['provider']==name and x['target_cited'] is True for x in valid),
                      'attempts':sum(x['provider']==name for x in results),
                      'errors':sum(x['provider']==name and x['status']=='api_error' for x in results)} for name in PROVIDERS}
    return {'method':'Dynamic, source-grounded questions with valid source metadata only; API benchmarks do not equal consumer search rankings',
            'target_domain':target,'questions_selected':len(selected),'questions':selected,'results':results,'summary':byprovider,
            'status':'completed' if valid else 'unavailable'}
