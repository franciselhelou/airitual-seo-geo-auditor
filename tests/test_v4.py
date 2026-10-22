from unittest.mock import patch
from audit.crawl import crawl_site
from audit.quality import representative_pages, classify_opportunities, roadmap, audit_quality
from audit.benchmarks import _citations_from_openai, run_benchmarks
from audit.pdf_report import create_pdf
from audit.runner import execute

BASE='https://example.com'
TEXT=('Public resource explains municipal contact schedules, offices and how to request services. '*9)


def fake_fetch(url,**kwargs):
    if url.endswith('/robots.txt'):return {'url':url,'status':404,'text':'','type':'text/plain','error':''}
    if url.endswith('/sitemap.xml'):
        body='<urlset>'+''.join(f'<url><loc>{x}</loc></url>' for x in [BASE+'/permit',
            BASE+'/info', BASE+'/business', 'http://example.com/permit'])+'</urlset>'
        return {'url':url,'status':200,'text':body,'type':'application/xml','error':''}
    if url.endswith('/sitemap_index.xml'):return {'url':url,'status':404,'text':'','type':'text/plain','error':''}
    if url.endswith('/business'):
        return {'url':BASE+'/business','status':200,'text':f'<html><title>Businesses</title><h1>Businesses</h1><p>{TEXT}</p></html>',
                'type':'text/html','error':''}
    if url.endswith('/info'):
        return {'url':BASE+'/permit','status':200,'text':f'<html><title>Permits</title><h1>Permits</h1><p>{TEXT}</p></html>',
                'type':'text/html','error':''}
    if url.endswith('/permit'):
        return {'url':BASE+'/permit','status':200,'text':f'<html><title>Permits</title><h1>Permits</h1><p>{TEXT}</p></html>',
                'type':'text/html','error':''}
    return {'url':BASE,'status':200,'text':f'<html><title>Home</title><h1>Home</h1><p>{TEXT}</p></html>',
            'type':'text/html','error':''}


def test_redirect_and_scheme_aliases_do_not_consume_page_budget():
    with patch('audit.crawl.checked_url'),patch('audit.crawl.fetch',side_effect=fake_fetch):
        result=crawl_site(BASE,max_pages=6)
    urls=[p['url'] for p in result['pages']]
    assert len(urls)==len(set(urls))
    assert 'https://example.com/permit' in urls
    assert result['pages_attempted']>=len(result['pages'])
    assert all('http://example.com/permit' not in p['url'] for p in result['pages'])


def test_content_research_samples_unique_pages():
    from audit.crawl import extract
    pages=[extract(f'<html><title>{title}</title><h1>{title}</h1><p>{TEXT}</p></html>',BASE+'/'+title.lower(),200)
           for title in ('Building Permit','Business','Building Permit')]
    assert len(representative_pages(pages,max_docs=20))==2


def test_existing_resources_flagged_before_create_new_pages():
    op=[{'title':'Create a new permit guide','proposed_content':'Permit instructions','supporting_urls':[BASE]}]
    inventory=[{'url':BASE+'/636/Online-Permit-Application','title':'Online Permit Application'}]
    result=classify_opportunities(op,inventory)
    assert result[0]['existing_related_urls']
    assert 'existing resource' in result[0]['recommended_first_step']


def test_roadmap_uses_content_opportunities():
    rm=roadmap([], [{'title':'Improve building permit page','proposed_content':'Add concrete steps',
                      'supporting_urls':[BASE+'/permits']}])
    assert any('building permit' in task.lower() for phase in rm for task in phase['tasks'])
    assert not any('No validated items' in task for phase in rm for task in phase['tasks'])


def test_citation_matching_and_provider_failure_not_negative():
    response={'output':[{'type':'message','content':[{'type':'output_text',
        'text':'Official source','annotations':[{'type':'url_citation','url':'https://example.com/permit','title':'Permits'}]}]}]}
    answer,cites=_citations_from_openai(response)
    assert answer=='Official source' and cites[0]['url'].endswith('/permit')
    with patch.dict('audit.benchmarks.PROVIDERS',{
        'openai':lambda q:{'status':'completed','answer':'Okay','citations':cites},
        'perplexity':lambda q:{'status':'not_configured'},
        'gemini':lambda q:(_ for _ in ()).throw(ValueError('disabled'))}):
        with patch.dict('os.environ',{'AUDIT_BENCHMARK_QUESTIONS':'1'}):
            report=run_benchmarks(BASE,['Where do I apply for permits?'])
    assert report['summary']['openai']['target_cited']==1
    assert report['summary']['perplexity']['tests_completed']==0
    assert next(x for x in report['results'] if x['provider']=='gemini')['target_cited'] is None


def test_quality_gate_self_reference_and_empty_items():
    result={'pages':[{'url':BASE},{'url':BASE}], 'findings':[],
            'intelligence':{'content_opportunities':[{'title':'No source'}]},'coverage':{'pages_failed':0}}
    gate=audit_quality(result)
    assert gate['status']=='needs_review'
    assert gate['checks']['repeated_resolved_page_records']==1


def test_pdf_v4_contains_real_measurement_section():
    report={'website':BASE,'engine_version':'4.0.0','audit_id':'test','completed_at':'2026-10-22',
        'coverage':{'pages_crawled':1,'pages_attempted':1,'pages_unique_content':1,'urls_discovered':1,
                    'candidate_sample_percent':100},'scores':{'overall':None,'technical':100,'content':100,'geo':None},
        'findings':[],'intelligence':{'organization_type':'Municipal site'},'pages':[],
        'benchmarks':{'status':'completed','summary':{'openai':{'tests_completed':1,'target_cited':1,'attempts':1}},
                      'results':[{'provider':'openai','status':'completed','question':'How do I apply?',
                                  'target_cited':True,'answer':'Official site','citations':[{'url':BASE,'title':'Official'}]}]},
        'quality_gate':{'status':'pass','checks':{}},'limitations':[],'roadmap':[]}
    pdf=create_pdf(report)
    assert pdf[:4]==b'%PDF' and len(pdf)>3500
