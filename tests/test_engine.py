from unittest.mock import patch
from audit.crawl import extract,hostname_allowed,crawl_site
from audit.net import checked_url,UnsafeURL
from audit.evaluate import analyze_site
from audit.pdf_report import create_pdf

HTML='''<!doctype html><html><head><title>Sample City | Official Services</title>
<meta name="description" content="Find city services, building permits, contact details and public updates.">
<link rel="canonical" href="https://example.com/" />
<script type="application/ld+json">{"@context":"https://schema.org","@type":"GovernmentOrganization","name":"Sample City"}</script>
</head><body><h1>Welcome to Sample City</h1><h2>City Services</h2><img src="seal.png" alt="City Seal">
<a href="/permits">Building permits</a><p>We publish services, applications and contact details for residents. This page explains how citizens can access information about the municipality and community services.</p></body></html>'''


def fake_fetch(url,**kwargs):
    if url.endswith("/robots.txt"):return {"url":url,"status":200,"text":"User-agent: *\nAllow: /","type":"text/plain","error":""}
    if url.endswith("/sitemap.xml"):return {"url":url,"status":200,"text":"<urlset><url><loc>https://example.com/</loc></url></urlset>","type":"application/xml","error":""}
    if url.endswith("/sitemap_index.xml"):return {"url":url,"status":404,"text":"","type":"text/xml","error":""}
    if url.endswith("/permits"):
        html='''<html><head><title>Apply for a Building Permit | Sample City</title></head><body><h1>Building permits</h1><h2>Application steps</h2><p>Submit your application by visiting the municipal building department in person. Review the required forms and fees.</p></body></html>'''
        return {"url":url,"status":200,"text":html,"type":"text/html","error":""}
    return {"url":url,"status":200,"text":HTML,"type":"text/html","error":""}


def test_extract_jsonld_and_metadata():
    x=extract(HTML,"https://example.com/",200)
    assert x["schema_types"]==["GovernmentOrganization"]
    assert x["images_missing_alt"]==0
    assert len(x["h1"])==1


def test_disallowed_hosts_and_private_ip():
    assert hostname_allowed("https://www.example.com/foo","https://example.com/")
    assert not hostname_allowed("https://other.com/foo","https://example.com/")
    for url in ("http://127.0.0.1/","http://localhost/","file:///etc/passwd","http://a.local/"):
        try:checked_url(url)
        except UnsafeURL:pass
        else:raise AssertionError("Expected UnsafeURL: "+url)


def test_crawl_scores_pdf():
    with patch("audit.crawl.checked_url",lambda x:x),patch("audit.crawl.fetch",side_effect=fake_fetch):
        site=crawl_site("https://example.com/",max_pages=3)
    assert len(site["pages"])==2
    report=analyze_site("https://example.com/",site,[])
    assert report.scores()["overall"] is None
    assert report.scores()["geo"] is None
    assert report.scores()["technical"] == 100
    result={"audit_id":"test","website":"https://example.com/","created_at":"2026-10-21","completed_at":"2026-10-21","scores":report.scores(),"summary":"Tested sample public site.","coverage":{"pages_crawled":2,"urls_discovered":2,"pages_failed":0},"findings":report.findings,"roadmap":[],"pages":site["pages"],"external_profiles":[],"limitations":[]}
    pdf=create_pdf(result)
    assert pdf[:4]==b"%PDF" and len(pdf)>1500
