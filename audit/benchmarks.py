"""Measured public-web API benchmarks; not consumer-product rankings.

Stores raw answer text (bounded), actual citation URLs and provider status.
Provider failures are *not* counted as negative search/citation results.
"""
import os
from urllib.parse import urlparse
import requests

TIMEOUT=65


def _host(url):
    try:return (urlparse(url).hostname or '').lower().removeprefix('www.')
    except Exception:return ''


def _citations_from_openai(raw):
    answer=[];cites=[]
    for item in raw.get('output',[]):
        if item.get('type')!='message':continue
        for part in item.get('content',[]):
            if part.get('type') not in ('output_text','text'):continue
            answer.append(part.get('text',''))
            for a in part.get('annotations',[]):
                if a.get('type') in ('url_citation','citation'):
                    cites.append({'url':a.get('url',''),'title':a.get('title','')})
    return '\n'.join(answer),_dedupe_cites(cites)


def _dedupe_cites(citations):
    seen=set();out=[]
    for a in citations:
        u=a.get('url','')
        if urlparse(u).scheme not in ('http','https') or u in seen:continue
        out.append({'url':u,'title':str(a.get('title',''))[:160]});seen.add(u)
    return out[:24]


def _openai(question):
    key=os.getenv('OPENAI_API_KEY','')
    if not key:return {'status':'not_configured'}
    model=os.getenv('OPENAI_WEB_MODEL') or os.getenv('OPENAI_MODEL') or 'gpt-5-mini'
    body={'model':model,'input':question,'tools':[{'type':'web_search','search_context_size':'low'}],
          'tool_choice':'required','max_output_tokens':1800}
    if model in ('gpt-5','gpt-5-mini','gpt-5-nano'):body['reasoning']={'effort':'low'}
    r=requests.post('https://api.openai.com/v1/responses',json=body,
                    headers={'Authorization':f'Bearer {key}'},timeout=TIMEOUT)
    r.raise_for_status();raw=r.json();answer,cites=_citations_from_openai(raw)
    searched=any(x.get('type')=='web_search_call' for x in raw.get('output',[]))
    return {'status':'completed' if raw.get('status')=='completed' and searched else 'not_measured',
            'answer':answer[:2500], 'citations':cites, 'search_executed':searched,
            'model':model,'usage':raw.get('usage') or {}}


def _perplexity(question):
    key=os.getenv('PERPLEXITY_API_KEY','')
    if not key:return {'status':'not_configured'}
    # Perplexity Agent API; not the retired Sonar synchronous endpoint.
    r=requests.post('https://api.perplexity.ai/v1/agent',
                    headers={'Authorization':f'Bearer {key}'},json={'preset':'fast-search','input':question},timeout=TIMEOUT)
    r.raise_for_status();raw=r.json();answer,cites=_citations_from_openai(raw)
    return {'status':'completed' if raw.get('status')=='completed' and answer else 'not_measured',
            'answer':answer[:2500],'citations':cites,'model':raw.get('model','agent:fast'),
            'usage':raw.get('usage') or {}}


def _gemini(question):
    key=os.getenv('GEMINI_API_KEY','')
    if not key:return {'status':'not_configured'}
    model=os.getenv('GEMINI_MODEL') or 'gemini-2.5-flash'
    # Google Interactions API grounding. URLs come from model_output annotations.
    r=requests.post('https://generativelanguage.googleapis.com/v1beta/interactions',
        headers={'x-goog-api-key':key},json={'model':model,'input':question,
         'tools':[{'type':'google_search'}]},timeout=TIMEOUT)
    r.raise_for_status();raw=r.json();answer=[];cites=[]
    for step in raw.get('steps',[]):
        if step.get('type')!='model_output':continue
        for part in step.get('content',[]):
            if part.get('type')!='text':continue
            answer.append(part.get('text',''))
            for a in part.get('annotations',[]):
                if a.get('type')=='url_citation':cites.append({'url':a.get('url',''),'title':a.get('title','')})
    return {'status':'completed' if answer else 'not_measured',
            'answer':'\n'.join(answer)[:2500],'citations':_dedupe_cites(cites),
            'model':model,'usage':raw.get('usage') or {}}


PROVIDERS={'openai':_openai,'perplexity':_perplexity,'gemini':_gemini}


def run_benchmarks(website,questions,progress=lambda x:None):
    """Cap all provider calls and log failures without treating them as missing citations."""
    limit=max(0,min(8,int(os.getenv('AUDIT_BENCHMARK_QUESTIONS') or '4')))
    questions=[q.get('question') if isinstance(q,dict) else q for q in questions]
    questions=list(dict.fromkeys(q.strip() for q in questions if isinstance(q,str) and q.strip()))[:limit]
    target=_host(website)
    items=[]
    for provider,fn in PROVIDERS.items():
        for question in questions:
            progress(f'Public AI citation benchmark: {provider} question {len([x for x in items if x["provider"]==provider])+1}/{len(questions)}')
            try:
                measured=fn(question)
                citations=measured.get('citations',[])
                measured['target_cited']=any((_host(c.get('url',''))==target or
                          _host(c.get('url','')).endswith('.'+target)) for c in citations) if measured.get('status')=='completed' else None
            except requests.HTTPError as e:
                measured={'status':'api_error','http_status':e.response.status_code if e.response is not None else None,'target_cited':None}
            except (ValueError,TypeError,requests.RequestException) as e:
                measured={'status':'api_error','error_type':type(e).__name__,'target_cited':None}
            items.append({'provider':provider,'question':question,**measured})
    completed=[x for x in items if x.get('status')=='completed']
    summary={name:{'tests_completed':sum(x['provider']==name for x in completed),
                   'target_cited':sum(x['provider']==name and x.get('target_cited') is True for x in completed),
                   'attempts':sum(x['provider']==name for x in items)} for name in PROVIDERS}
    return {'method':'Public, API-grounded question tests; does not measure consumer ChatGPT/Google AI Mode/Perplexity UI',
            'target_domain':target,'questions_selected':len(questions),'results':items,'summary':summary,
            'status':'completed' if completed else 'unavailable'}
