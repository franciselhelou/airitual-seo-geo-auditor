"""Sample-scoped, explainable SEO and verifiable AI citation measurements.

All scores must disclose which dimensions are missing. Scores do not represent
Google rankings, visitor analytics, or consumer-AI market visibility.
"""

SEO_WEIGHTS={'html_access':15,'title':15,'h1':10,'unique_title':10,'description':10,'mobile_performance':40}
SEO_GROUPS={'html_access':'Technical availability','title':'Search presentation','h1':'Search presentation',
            'unique_title':'Search presentation','description':'Search presentation','mobile_performance':'Page experience'}

def seo_audit_score(review,pages,speeds):
    html=[p for p in pages if p.get('status')==200 and not p.get('error') and 'html' in p.get('type','text/html')]
    if not html:return {'score':None,'scope':'Not measured: no HTML','breakdown':[],'pages':0,'weight_covered':0}
    checks=review.tests
    def frac(name,dim):
        t=checks.get(dim,{}).get('checks',{}).get(name,{})
        n=t.get('passed',0)+t.get('failed',0)
        return (t.get('passed',0)/n,n) if n else (None,0)
    vals={'html_access':frac('html_fetch_200','technical'),'title':frac('html_title_present','content'),
          'h1':frac('primary_heading_present','content'),'unique_title':frac('unique_title_for_distinct_content','content'),
          'description':(sum(bool(p.get('description')) for p in html)/len(html),len(html))}
    scores=[v.get('performance_score') for v in speeds if isinstance(v.get('performance_score'),(float,int))]
    vals['mobile_performance']=(sum(scores)/len(scores)/100,len(scores)) if scores else (None,0)
    observed=[(k,ratio,n) for k,(ratio,n) in vals.items() if ratio is not None]
    weight=sum(SEO_WEIGHTS[k] for k,_,_ in observed)
    score=round(sum(SEO_WEIGHTS[k]*ratio for k,ratio,_ in observed)*100/weight) if weight else None
    return {'score':score,'scope':'Weighted public SEO checks on sampled URLs; not whole-site rankings',
            'weight_covered':weight,'pages':len(html),
            'breakdown':[{'check':k,'category':SEO_GROUPS[k],'result_percent':round(ratio*100),
                          'samples':n,'weight':SEO_WEIGHTS[k]} for k,ratio,n in observed],
            'omitted':[k for k in SEO_WEIGHTS if vals[k][0] is None],
            'weight_policy':'Technical availability 15%; search presentation 45%; mobile page experience 40%. Unmeasured weights omitted and remainder renormalized.'}

def geo_citation_score(benchmark):
    valid=[x for x in benchmark.get('results',[]) if x.get('status')=='completed'
           and x.get('valid_answer') is True and x.get('target_cited') is not None
           and x.get('citations') and x.get('citation_metadata_valid') is not False]
    cited=sum(x['target_cited'] is True for x in valid)
    return {'score':round(100*cited/len(valid)) if valid else None,
            'cited':cited,'valid_tests':len(valid),'attempts':len(benchmark.get('results',[])),
            'scope':'Target-domain citation rate across valid API results with structured citations, not broad consumer AI rankings',
            'provider_results':{p:{'valid_tests':sum(x['provider']==p for x in valid),
                'cited':sum(x['provider']==p and x['target_cited'] is True for x in valid)}
                for p in ('openai','perplexity','gemini')}}

def action_counts(findings,opportunities):
    urgent=[f for f in findings if f.get('kind')=='issue' and f.get('severity') in ('high','critical')]
    review=[f for f in findings if f.get('kind')!='issue' and f.get('severity') in ('high','critical')]
    return {'urgent_verified':len(urgent),'high_priority_to_verify':len(review),
            'content_proposals':len([x for x in opportunities if x.get('quote') and x.get('supporting_urls')]),
            'urgent_finding_ids':[x.get('id') for x in urgent]}
