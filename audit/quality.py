"""V4 evidence gate: keep audit claims grounded and reject low-value placeholders.

This module deliberately distinguishes observed HTML from editorial hypotheses.
"""
import re
from collections import Counter
from urllib.parse import urlparse


def representative_pages(pages, max_docs=44, max_chars=4600):
    """Prefer distinct task-relevant content over URL order and aliases."""
    eligible=[p for p in pages if p.get('status')==200 and not p.get('error') and p.get('text')]
    groups={}
    for p in eligible:
        normalized=' '.join(p.get('text','').lower().split())
        if len(normalized)<100:
            key=p.get('url')
        else:
            key=(p.get('title','').lower(),normalized)
        groups.setdefault(key,p)
    unique=list(groups.values())
    task_terms=('permit','application','contact','directory','hours','parking','business','service',
                'pricing','fee','emergency','water','trash','recreation','council','meeting',
                'records','zoning','inspection','event','safety','about')
    def weight(p):
        path=urlparse(p.get('url','')).path.lower()
        title=(p.get('title') or '').lower()
        score=sum(2 if x in path else 1 if x in title else 0 for x in task_terms)
        if not path or path=='/':score+=5
        if p.get('word_count',0)<70:score-=3
        return (-score,-min(p.get('word_count',0),1600),len(path))
    unique.sort(key=weight)
    return [{'url':p['url'],'title':p.get('title',''),'text':p.get('text','')[:max_chars]}
            for p in unique[:max_docs]]


def full_inventory(pages, discovered=()):
    return [{'url':p['url'],'title':p.get('title',''),'headings':p.get('h1',[])[:2],
             'words':p.get('word_count',0)} for p in pages if p.get('status')==200][:90] + [
             {'url':u,'title':'Not fetched; candidate only','headings':[],'words':None}
             for u in list(discovered)[:260]]


def classify_opportunities(items, inventory):
    """Conservatively flag existing resources; never assert absence from a bounded sample."""
    for item in items:
        title=(item.get('title') or '').lower()
        desc=(item.get('proposed_content') or '').lower()
        clues=({'permit':('permit','application','building'),
                'business':('business','economic-development'),
                'contact':('contact','directory'),
                'parking':('parking',),
                'event':('event','festival'),
                'emergency':('emergency','public-safety','police'),
                'water':('water',),
                'zoning':('zoning',),
                'council':('council','agendacenter')})
        matches=[]
        for token, variants in clues.items():
            if token not in title and token not in desc[:100]:continue
            matches += [i.get('url') for i in inventory
                        if any(v in (urlparse(i.get('url','')).path+' '+i.get('title','')).lower()
                               for v in variants)]
        matches=list(dict.fromkeys(m for m in matches if m))[:5]
        item['existing_related_urls']=matches
        item['status']='Research hypothesis; existing relevant site resources must be reviewed'
        item['verification_required']=True
        if matches and re.search(r'\b(create|new|publish|build|add)\b',title):
            item['recommended_first_step']='Review and improve existing resource before creating a new page.'
        else:
            item['recommended_first_step']='Confirm site-wide coverage and user demand before implementing.'
    return items


def roadmap(findings, opportunities):
    """Every proposed action is linked to either a finding or a research hypothesis."""
    reviews=sorted(findings,key=lambda f:({'critical':0,'high':1,'medium':2,'low':3,'info':4}.get(f.get('severity'),5),
                                           -f.get('affected_count',0)))
    phases=[{'period':'First 7 days — validate evidence and urgent risks','tasks':[]},
            {'period':'Days 8–30 — implement verified high-value improvements','tasks':[]},
            {'period':'Days 31–90 — enhance, measure, and reassess','tasks':[]}]
    for f in reviews[:10]:
        action='Correct confirmed markup' if f.get('kind')=='issue' else 'Verify observed signal'
        phases[0]['tasks'].append(f"{action}: {f['title']} — {f.get('url','')} — {f.get('recommendation','')}")
    for f in reviews:
        if f.get('kind')=='issue':
            phases[1]['tasks'].append(f"After verification: {f['title']} — {f.get('recommendation','')}")
    for i,item in enumerate(opportunities[:12]):
        task=(f"Research-backed proposal: {item.get('title','Improvement')} — "
              f"{item.get('recommended_first_step','Verify existing coverage.')} "
              f"{item.get('proposed_content','')[:240]} "
              f"Evidence: {(item.get('supporting_urls') or ['not supplied'])[0]}")
        phases[1 if i<5 else 2]['tasks'].append(task)
    phases[2]['tasks'].append('Repeat documented public PageSpeed and AI API citation benchmarks; compare stored questions and cited URLs.')
    return [p for p in phases if p['tasks']]


def audit_quality(result):
    """Report quality flags are informative; do not manufacture a site score."""
    pages=result.get('pages',[]);findings=result.get('findings',[])
    canonical=[(p.get('url') or '').lower().rstrip('/') for p in pages if not p.get('error')]
    duplicates=sum(v-1 for v in Counter(canonical).values() if v>1)
    checks={
      'repeated_resolved_page_records':duplicates,
      'self_referential_duplicate_findings':sum(' vs ' in f.get('evidence','') and
         len(set(f.get('evidence','').split(' vs ')[-2:]))==1 for f in findings),
      'missing_evidence_on_findings':sum(not f.get('evidence') for f in findings),
      'unsourced_content_opportunities':sum(not p.get('quote') for p in result.get('intelligence',{}).get('content_opportunities',[])),
      'pages_with_unreported_failure':sum(bool(p.get('error')) for p in pages)-result.get('coverage',{}).get('pages_failed',0),
    }
    status='pass' if all(x==0 for x in checks.values()) else 'needs_review'
    return {'status':status,'checks':checks,'note':'Validation of document structure only; substantive editorial correctness remains unverified.'}
