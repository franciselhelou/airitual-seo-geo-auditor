from unittest.mock import patch
from audit.scoring import seo_audit_score,geo_citation_score,action_counts
from audit.benchmark_questions import plan_questions
from audit.benchmarks import run_benchmarks
from audit.crawl import crawl_site
from audit.evaluate import analyze_site
from audit.pdf_report import create_pdf

URL='https://cityofberea.org/'

def page(url,title,text='City of Berea Ohio municipal residents local government permit applications information',status=200):
    return {'url':url,'title':title,'h1':[title],'description':'','status':status,
            'text':text*4,'word_count':130,'error':'','headings':['Services'],'links':[],
            'robots':'','images':0,'images_missing_alt':0,'schema_types':[]}

def test_berea_benchmark_questions_have_location_and_evidence():
    pages=[page(URL,'City of Berea | Official Website'),page(URL+'149/Building','Building Permits')]
    q=plan_questions(URL,pages,'Government organization',limit=5)
    assert q and all('Berea, Ohio' in x['question'] and x['evidence_url'] for x in q)
    assert not any('ward' in x['question'].lower() for x in q)

def test_without_geographic_context_do_not_send_ambiguous_government_questions():
    pages=[page(URL,'City of Berea | Official Website','City of Berea')]
    assert not plan_questions(URL,pages,'Government organization')

def test_invalid_answers_do_not_reduce_geo_score():
    q={'question':'Where can residents of Berea, Ohio get building permits?',
       'context':'Berea, Ohio','intent':'permit','evidence_url':URL+'permits'}
    with patch.dict('audit.benchmarks.PROVIDERS',{
        'openai':lambda _: {'status':'completed','answer':'I can help, but first tell me the city or county you are asking about.','citations':[]},
        'gemini':lambda _: {'status':'completed','answer':'Berea Ohio publishes information from several city departments. The city provides official information on permits, applications and contact information via municipal service pages.','citations':[{'url':URL+'permits'}]},
        'perplexity':lambda _: {'status':'api_error','target_cited':None}}):
        report=run_benchmarks(URL,[q])
    assert report['summary']['openai']['tests_completed']==0
    assert report['summary']['gemini']['target_cited']==1
    assert report['results'][0]['status']=='invalid_answer'
    assert geo_citation_score(report)['score']==100
    assert geo_citation_score(report)['valid_tests']==1

def test_seo_is_sampled_weighted_not_100_from_html_only():
    pages=[page(URL,'City of Berea'),page(URL+'permits','Building Permits')]
    report=analyze_site(URL,{'pages':pages,'sitemap_status':'present'},[])
    result=seo_audit_score(report,pages,[])
    assert 0<=result['score']<100
    assert 'mobile_performance' in result['omitted']
    assert any(x['check']=='description' for x in result['breakdown'])

def test_high_severity_unverified_findings_not_counted_as_urgent():
    count=action_counts([{'severity':'high','kind':'review'}, {'severity':'medium','kind':'issue'},
                         {'severity':'critical','kind':'issue','id':'A1'}],[])
    assert count['urgent_verified']==1 and count['high_priority_to_verify']==1

def test_pdf_success_resource_not_a_failed_html():
    text='resident zoning office ' * 50
    def fetch(url,**kwargs):
        if url.endswith('robots.txt'):
            return {'status':404,'url':url,'text':'','type':'text/plain','error':''}
        if url.endswith('sitemap.xml') or url.endswith('sitemap_index.xml'):
            return {'status':404,'url':url,'text':'','type':'text/xml','error':''}
        if 'DocumentCenter' in url:
            return {'url':url,'status':200,'type':'application/pdf','text':'','error':'Non-HTML/XML content'}
        return {'url':url,'status':200,'type':'text/html',
                'text':f'<html><title>City of Berea Ohio</title><h1>Berea</h1><p>{text}</p><a href="/DocumentCenter/View/628/Planning-Commission-Review-Fees-PDF?bidId=">Download fee PDF</a></html>','error':''}
    with patch('audit.crawl.checked_url'),patch('audit.crawl.fetch',side_effect=fetch):
        res=crawl_site(URL,max_pages=4)
    assert not any('DocumentCenter' in p['url'] for p in res['pages'])
    assert any(x.get('reason')=='successful_non_html_resource' for x in res['excluded_resources'])
    assert not any('DocumentCenter' in p['url'] for p in analyze_site(URL,res,[]).findings)

def test_pdf_executive_scores_without_page_inventory_section():
    r={'website':URL,'audit_id':'test','completed_at':'2026-10-22','engine_version':'5.0.0',
       'scores':{'seo':57,'geo':25},'score_details':{'seo':{'score':57,'pages':15,'weight_covered':80,'breakdown':[]},
                                                'geo':{'score':25,'cited':1,'valid_tests':4,'attempts':6}},
       'action_summary':{'urgent_verified':1,'high_priority_to_verify':2,'content_proposals':3},
       'findings':[],'intelligence':{},'roadmap':[], 'pages':[], 'coverage':{},'quality_gate':{'status':'pass'},
       'benchmarks':{},'limitations':[]}
    output=create_pdf(r)
    assert output[:4]==b'%PDF' and len(output)>3000
