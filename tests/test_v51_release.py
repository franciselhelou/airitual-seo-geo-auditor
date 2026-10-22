"""V5.1: literal JSON/PDF parity, provider attribution, dynamic buyer-intent prompts."""
from io import BytesIO
from unittest.mock import patch
import requests
from pypdf import PdfReader

from audit.benchmark_questions import plan_questions
from audit.benchmarks import _citations_from_perplexity, run_benchmarks, _http_error
from audit.scoring import geo_citation_score, seo_audit_score
from audit.pdf_report import create_pdf
from audit.quality import audit_quality
from audit.evaluate import analyze_site

SITE='https://cityofberea.org/'
def page(url,title,body):
    return {'url':url,'title':title,'h1':[title],'description':'Page instructions','status':200,'error':'',
            'text':body*3,'word_count':160,'images':0,'images_missing_alt':0,'headings':[],
            'links':[],'robots':'','schema_types':[]}


def test_dynamic_city_queries_and_no_duplicated_state():
    pages=[page(SITE,'City of Berea | Ohio','City of Berea, Ohio gives residents information about parks and permit applications. '),
           page(SITE+'149/Building','Permits','Building permits and application instructions for residents of Berea Ohio. '),
           page(SITE+'parks','Parks','Parks and recreation are located in Berea Ohio. ')]
    results=plan_questions(SITE,pages,'Government organization')
    assert results and any('permit' in x['question'].lower() for x in results)
    assert all('Berea, Ohio' in x['question'] and 'OH, Ohio' not in x['question'] for x in results)


def test_guatemala_apparel_discovery_and_quoted_llm_prompt():
    home=page('https://camisas.example/','Textil Maya | Custom Apparel','We manufacture custom T-shirts and shirts in Guatemala for wholesale clothing buyers. ')
    proposal={'question':'Which companies manufacture custom T-shirts in Guatemala?',
      'segment':'discovery','intent':'wholesale sourcing','evidence_url':home['url'],
      'evidence_quote':'We manufacture custom T-shirts and shirts in Guatemala for wholesale clothing buyers.'}
    q=plan_questions(home['url'],[home],'Organization / business',suggestions=[proposal])
    assert q and q[0]['segment']=='discovery' and 'Textil Maya' not in q[0]['question']
    assert q[0]['method']=='source_verified_dynamic_llm'
    assert not plan_questions(home['url'],[home],suggestions=[dict(proposal,evidence_quote='Not on this website')])[0].get('method')=='source_verified_dynamic_llm'


def test_perplexity_agent_search_result_items_authoritative():
    response={'status':'completed','output':[
      {'type':'search_results','results':[{'url':SITE+'permit','title':'Berea Permits'},{'url':'https://other.example'}]},
      {'type':'message','content':[{'type':'output_text','text':'The permits are on Berea official website.[1]','annotations':[]}]}]}
    answer,citations,verified=_citations_from_perplexity(response)
    assert verified and answer.startswith('The permits')
    assert citations[0]['url'].endswith('/permit') and len(citations)==2


def test_provider_errors_exposed_without_credentials():
    response=requests.Response();response.status_code=400;response._content=b'{"error":{"type":"invalid_request","code":"BAD_MODEL","message":"Unknown model"}}'
    e=requests.HTTPError('failed',response=response)
    with patch.dict('audit.benchmarks.PROVIDERS',{'gemini':lambda q:(_ for _ in ()).throw(e)},clear=True):
        qs=[{'question':'Where are permits published for Berea, Ohio?','context':'Berea, Ohio','evidence_url':SITE+'permit'}]
        res=run_benchmarks(SITE,qs)
    assert res['results'][0]['status']=='api_error' and res['results'][0]['http_status']==400
    assert res['results'][0]['error_code']=='BAD_MODEL'


def test_no_source_metadata_is_not_a_negative_citation():
    answers={'answer':'Berea Ohio has public permit instructions and departments. Visit municipal office pages for application steps, hours and helpful information.', 'status':'completed','citations':[],'citation_metadata_valid':False}
    with patch.dict('audit.benchmarks.PROVIDERS',{'perplexity':lambda _:answers},clear=True):
        q={'question':'Where do I apply for permits in Berea, Ohio?','context':'Berea, Ohio','evidence_url':SITE}
        report=run_benchmarks(SITE,[q])
    assert report['results'][0]['status']=='unverifiable_sources'
    assert geo_citation_score(report)['valid_tests']==0
    assert geo_citation_score(report)['score'] is None


def sample_result():
    return {'website':SITE,'audit_id':'sample','completed_at':'2026-10-22','engine_version':'5.1.0',
            'scores':{'seo':67,'geo':50},'score_details':{
                'seo':{'score':67,'pages':48,'weight_covered':100,'breakdown':[{'check':'mobile_performance','category':'Page experience','result_percent':32,'samples':3,'weight':40}],
                        'weight_policy':'Technical availability 15%; search presentation 45%; mobile page experience 40%.'},
                'geo':{'score':50,'cited':2,'valid_tests':4,'attempts':6}},
            'coverage':{'pages_crawled':48,'pages_failed':0},'action_summary':{'urgent_verified':0,'high_priority_to_verify':2,'content_proposals':1},
            'intelligence':{'content_opportunities':[{'title':'Business resources','quote':'some quote','supporting_urls':[SITE]}]},
            'pages':[],'findings':[],'roadmap':[], 'benchmarks':{}, 'quality_gate':{'status':'pass'},
            'publication_status':'client_ready','limitations':[]}


def test_pdf_numbers_equal_structured_json_values():
    report=sample_result()
    pdf=create_pdf(report)
    text='\n'.join(p.extract_text() or '' for p in PdfReader(BytesIO(pdf)).pages)
    for value in ('67%', '50%', '2/4','48 HTML pages sampled','High-priority verification','2'):
        assert value in text, value
    assert 'Prioritized 90-day work plan' in text
    assert 'Audit scope and supporting records' in text
    assert 'Not scored' not in text


def test_quality_gate_blocks_inconsistent_score_or_citation():
    report=sample_result()
    report['scores']['seo']=55
    assert audit_quality(report)['status']=='needs_review'
    assert audit_quality(report)['checks']['score_or_count_mismatch']>0
