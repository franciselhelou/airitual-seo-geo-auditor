"""Regression tests for truthful scores, grouped findings and validated AI evidence."""
import os
from unittest.mock import patch
from audit.crawl import extract
from audit.evaluate import analyze_site
from audit.intelligence import research_intelligence
from audit.pdf_report import create_pdf

BASE='https://example.com/'
def page(url,title,body,desc=False):
    html=f'<html><head><title>{title}</title>{"<meta name=description content=hello>" if desc else ""}</head><body><h1>{title}</h1><p>{body}</p></body></html>'
    return extract(html,url,200)

def make_crawl():
    pp=[page(BASE,'Homepage | Example City','Public city government information, community services, applications and guides.'*3),
        page(BASE+'news','Latest News | Example City','A city newsletter and important announcements for local residents.'*3),
        page(BASE+'services','City Services | Example City','Resident services, permits and useful public information.'*3)]
    return {'pages':pp,'urls_discovered':3,'pages_failed':0,'sitemap_status':'present','robots_status':'present'}

def test_no_canonical_score_penalty_and_grouped_meta():
    site=make_crawl(); review=analyze_site(BASE,site,[])
    assert review.scores()['technical']==100
    assert not any('canonical declaration' in x['title'].lower() for x in review.findings)
    metas=[x for x in review.findings if 'meta description' in x['title'].lower()]
    assert len(metas)==1
    assert metas[0]['affected_count']==3

def test_ai_research_avoids_unverifiable_conflicts():
    site=make_crawl();docs=site['pages'];review=analyze_site(BASE,site,[])
    forged={'strengths':[{'point':'Made-up fact','url':BASE,'quote':'NOT A QUOTE FROM PAGE'}],
        'potential_conflicts':[{'title':'Contradiction','observation':'Wrong','source_a':{'url':BASE,'quote':'fake'},
             'source_b':{'url':BASE+'news','quote':'fake'}}],
        'content_opportunities':[{'title':'Fake missing content','source':{'url':BASE,'quote':'fake'}}],
        'geo_questions':['How do I get a permit?'],'executive_analysis':''}
    with patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch('audit.intelligence._llm_json',return_value=forged):
        intel=research_intelligence(BASE,docs,review,[],[])
    assert not intel['research_findings']
    assert not any(x.get('point')=='Made-up fact' for x in intel['strengths'])
    assert not any(x.get('title')=='Fake missing content' for x in intel['content_opportunities'])
    assert len(intel['geo_questions'])==1

def test_new_pdf_content():
    crawled=make_crawl(); rev=analyze_site(BASE,crawled,[])
    report={'website':BASE,'audit_id':'test','completed_at':'2026-10-21','engine_version':'2.0.0',
      'summary':'Bounded verification only.','coverage':{'pages_crawled':3,'urls_discovered':3},
      'scores':rev.scores(),'findings':rev.findings,'pages':crawled['pages'],'roadmap':[],
      'intelligence':{'organization_type':'Government organization','strengths':[],'topic_coverage':[],
       'content_opportunities':[],'keyword_clusters':[],'research_findings':[],'geo_questions':[],'ai_research_status':'not_configured'},
      'limitations':['This is a tested sample.']}
    data=create_pdf(report)
    assert data[:4]==b'%PDF' and len(data)>5000
