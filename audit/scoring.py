"""Interpretable *sample-scoped* SEO check and API GEO citation scores.

Neither metric is a Google rank, a whole-site SEO grade, or consumer AI visibility.
Unknown measurements are excluded and denominators remain visible.
"""
from collections import defaultdict

SEO_WEIGHTS={'html_access':25,'title':22,'h1':12,'unique_title':13,'description':8,'mobile_performance':20}

def seo_audit_score(review,pages,speeds):
    html=[p for p in pages if p.get('status')==200 and not p.get('error') and (not p.get('type') or 'html' in p.get('type','html'))]
    if not html:return {'score':None,'scope':'Not measured: no evaluable HTML','breakdown':[],'pages':0}
    checked=review.tests
    def frac(name,dim):
        v=checked.get(dim,{}).get('checks',{}).get(name,{})
        n=v.get('passed',0)+v.get('failed',0)
        return (v.get('passed',0)/n,n) if n else (None,0)
    vals={'html_access':frac('html_fetch_200','technical'),
          'title':frac('html_title_present','content'),
          'h1':frac('primary_heading_present','content'),
          'unique_title':frac('unique_title_for_distinct_content','content')}
    # A meta description is a useful snippet-control opportunity, not a guaranteed
    # ranking factor; deliberately assign low weight.
    vals['description']=(sum(bool(p.get('description')) for p in html)/len(html),len(html))
    valid_ps=[x['performance_score'] for x in speeds if isinstance(x.get('performance_score'),(float,int))]
    vals['mobile_performance']=(sum(valid_ps)/len(valid_ps)/100,len(valid_ps)) if valid_ps else (None,0)
    scored=[(key,ratio,n) for key,(ratio,n) in vals.items() if ratio is not None]
    points=sum(SEO_WEIGHTS[k]*v for k,v,n in scored)
    weight=sum(SEO_WEIGHTS[k] for k,v,n in scored)
    return {'score':round(100*points/weight) if weight else None,
            'scope':'Sampled public SEO checks; not a verified whole-site search ranking',
            'weight_covered':weight,'pages':len(html),
            'breakdown':[{'check':k,'result_percent':round(v*100), 'samples':n, 'weight':SEO_WEIGHTS[k]} for k,v,n in scored],
            'omitted':[k for k in SEO_WEIGHTS if vals[k][0] is None]}

def geo_citation_score(benchmark):
    valid=[x for x in benchmark.get('results',[]) if x.get('status')=='completed' and x.get('valid_answer') is True and x.get('target_cited') is not None]
    cited=sum(x.get('target_cited') is True for x in valid)
    return {'score':round(100*cited/len(valid)) if valid else None,
            'cited':cited,'valid_tests':len(valid),'attempts':len(benchmark.get('results',[])),
            'scope':'Target-domain citation rate in valid public AI API tests only; not broad AI search visibility',
            'provider_results':{provider:{'valid_tests':sum(x['provider']==provider for x in valid),
                        'cited':sum(x['provider']==provider and x.get('target_cited') is True for x in valid)}
                        for provider in ('openai','perplexity','gemini')}}

def action_counts(findings,opportunities):
    urgent=[f for f in findings if f.get('kind')=='issue' and f.get('severity') in ('high','critical')]
    review=[f for f in findings if f.get('kind')!='issue' and f.get('severity') in ('high','critical')]
    return {'urgent_verified':len(urgent),'high_priority_to_verify':len(review),
            'content_proposals':len([x for x in opportunities if x.get('quote') and x.get('supporting_urls')]),
            'urgent_finding_ids':[x.get('id') for x in urgent]}
