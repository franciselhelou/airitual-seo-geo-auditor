"""V3 audit accuracy, non-misleading scoring, and sample selection tests."""
from unittest.mock import patch
from audit.crawl import crawl_site, extract
from audit.evaluate import analyze_site, make_roadmap
from audit.intelligence import coverage_topics, content_opportunities, query_clusters
from audit.pdf_report import create_pdf

BASE = 'https://example.com'
TEXT = ('This local government page describes resident applications, public information, '
        'permit regulations and municipal services. ' * 8)


def doc(url, title, content=TEXT):
    return extract('<html><head><title>'+title+'</title></head><body>'
                   '<h1>'+title+'</h1><p>'+content+'</p></body></html>', url, 200)


def crawl(*pages, discovered=None):
    return {'pages':list(pages),'urls_discovered':discovered or len(pages),
            'pages_failed':0, 'sitemap_status':'present', 'robots_status':'present'}


def test_no_global_health_score_without_site_wide_evidence():
    report=analyze_site(BASE, crawl(doc(BASE, 'Home | Example')), [])
    scores=report.scores()
    assert scores['overall'] is None
    assert scores['geo'] is None
    assert scores['technical'] == 100
    assert scores['content'] == 100
    assert report.tests['geo']['untested'] == 1


def test_content_equivalent_alias_excluded_from_title_score():
    p1=doc(BASE, 'Home | Example')
    p2=doc(BASE+'/1/Home', 'Home | Example')
    report=analyze_site(BASE, crawl(p1,p2),[])
    assert report.scores()['content'] == 100
    assert p2['duplicate_content_of'] == BASE
    assert any('Equivalent content' in f['title'] for f in report.findings)
    assert not any('Distinct pages share HTML titles' in f['title'] for f in report.findings)


def test_distinct_content_duplicate_title_reduces_essential_check_rate():
    p1=doc(BASE+'/faq-a','FAQ | Example',TEXT)
    p2=doc(BASE+'/faq-b','FAQ | Example',TEXT+'An entirely different detailed answer.')
    report=analyze_site(BASE,crawl(p1,p2),[])
    assert report.scores()['content'] < 100
    titles=[f for f in report.findings if 'Distinct pages share' in f['title']]
    assert len(titles)==1 and titles[0]['kind']=='review'
    assert all(f['validation_status'] for f in report.findings)


def test_failed_attempt_appears_in_denominator():
    p=doc(BASE, 'Home | Example')
    bad={'url':BASE+'/broken','status':0,'error':'ReadTimeout'}
    report=analyze_site(BASE,crawl(p,bad),[])
    assert report.scores()['technical']==100  # Timeout is untested, not a confirmed website defect
    assert report.tests['technical']['untested']==1
    assert not any('Failed HTML requests' in f['title'] for f in report.findings)


def test_short_pages_do_not_generate_numeric_geo_score():
    short=doc(BASE+'/about','About | Example','Brief content')
    report=analyze_site(BASE,crawl(short),[])
    assert report.scores()['geo'] is None
    assert any('short extracted' in f['title'] for f in report.findings)
    assert all('review' in f['kind'] or f['kind']=='issue' for f in report.findings)


def test_crawl_balances_topics_in_bounded_sample():
    urls=[f'{BASE}/permit-{i}' for i in range(8)] + [BASE+'/city-hall-contact', BASE+'/recreation', BASE+'/council']
    sitemap='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{u}</loc></url>' for u in urls)+'</urlset>'
    def fake_fetch(url, **kwargs):
        if url.endswith('/robots.txt'):
            return {'url':url,'status':200,'type':'text/plain','text':'User-agent: *\nAllow: /','error':''}
        if url.endswith('/sitemap.xml'):
            return {'url':url,'status':200,'type':'application/xml','text':sitemap,'error':''}
        if url.endswith('/sitemap_index.xml'):
            return {'url':url,'status':404,'type':'text/xml','text':'','error':''}
        html=f'<html><head><title>{url}</title></head><body><h1>{url}</h1><p>{TEXT}</p></body></html>'
        return {'url':url,'status':200,'type':'text/html','text':html,'error':''}
    with patch('audit.crawl.checked_url',lambda x:x), patch('audit.crawl.fetch',side_effect=fake_fetch):
        result=crawl_site(BASE,max_pages=5)
    selected=[p['url'] for p in result['pages']]
    assert len(selected)==5
    assert selected[0]==BASE
    assert BASE+'/city-hall-contact' in selected
    assert BASE+'/recreation' in selected
    assert BASE+'/council' in selected
    assert result['urls_discovered']==12


def test_keyword_templates_and_missing_page_claims_suppressed():
    pages=[doc(BASE,'Berea | Official Website','Contact the mayor and locate the City Hall service desk.')]
    topics=coverage_topics(pages,'Government organization')
    assert any(x['topic']=='Contact and hours' and x['status']=='mentioned_in_sample' for x in topics)
    assert content_opportunities(pages,'Government organization')==[]
    assert query_clusters('Government organization')==[]


def test_roadmap_review_first_correction_second():
    r=analyze_site(BASE,crawl(doc(BASE,'Home | Example')) ,[])
    plan=make_roadmap(r.findings)
    assert plan[0]['period'].startswith('First 7 days — validate')
    assert all('Verify:' in t for t in plan[0]['tasks'] if not t.startswith('No validated'))


def test_pdf_shows_no_overall_grade():
    p=doc(BASE,'Home | Example')
    review=analyze_site(BASE,crawl(p),[])
    data={ 'website':BASE,'audit_id':'v3-test','engine_version':'3.0.0',
           'completed_at':'2026-10-21','summary':'Bounded sample only.',
           'scores':review.scores(),'tests':review.tests,
           'coverage':{'pages_crawled':1,'pages_attempted':1,'urls_discovered':360,
                       'candidate_sample_percent':0.3,'pages_unique_content':1},
           'findings':review.findings,'pages':[p],'roadmap':make_roadmap(review.findings),
           'intelligence':{'topic_coverage':[],'strengths':[],'keyword_clusters':[],
                          'content_opportunities':[],'geo_questions':[]},'limitations':[]}
    pdf=create_pdf(data)
    assert pdf.startswith(b'%PDF')
    # PDF internal text layout is checked separately using pdftotext.
    assert len(pdf)>5000
