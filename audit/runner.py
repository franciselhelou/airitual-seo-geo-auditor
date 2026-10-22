"""GitHub runner consumes jobs from R2. CLI mode supports local PDF testing."""
import argparse
import datetime
import json
import os
import re
from pathlib import Path
import boto3
from .crawl import crawl_site,inspect_external
from .evaluate import analyze_site,pagespeed,make_roadmap,baseline_summary
from .intelligence import research_intelligence
from .pdf_report import create_pdf
from .quality import roadmap as build_roadmap, audit_quality
from .benchmarks import run_benchmarks
from .benchmark_questions import plan_questions
from .scoring import seo_audit_score,geo_citation_score,action_counts


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


class R2:
    def __init__(self):
        account=os.environ["R2_ACCOUNT_ID"]
        self.bucket=os.environ["R2_BUCKET"]
        self.s3=boto3.client("s3",endpoint_url=f"https://{account}.r2.cloudflarestorage.com",aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],region_name="auto")
    def read(self,key):return json.loads(self.s3.get_object(Bucket=self.bucket,Key=key)["Body"].read().decode("utf-8"))
    def put(self,key,data,mime="application/json"):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False,indent=2).encode("utf-8")
        self.s3.put_object(Bucket=self.bucket,Key=key,Body=data,ContentType=mime,CacheControl="no-store")


def execute(job,on_progress=lambda msg:None):
    website=job["website"]
    warnings=[]
    on_progress("Checking crawler permissions and discovering pages")
    max_pages=max(8,min(90,int(os.getenv("AUDIT_MAX_PAGES") or "48")))
    crawled=crawl_site(website,progress=on_progress,max_pages=max_pages)
    warnings.extend(crawled["warnings"])
    external=inspect_external(job.get("extra_urls",[]),progress=on_progress)
    on_progress("Calculating scores and evidence-backed findings")
    review=analyze_site(website,crawled,external,progress=on_progress)
    # Four bounded, publicly accessible PageSpeed checks: homepage plus three
    # distinct representative service pages. Never send a credential to the page.
    candidate_urls=[website]+[p.get('url') for p in crawled['pages']
                               if p.get('status')==200 and p.get('url')!=website
                               and any(t in p.get('url','').lower() for t in
                                       ('permit','service','business','contact','about','parking'))]
    candidate_urls=list(dict.fromkeys(filter(None,candidate_urls)))[:4]
    speeds=[]
    if os.getenv('PAGESPEED_API_KEY'):
        for target in candidate_urls:
            on_progress('Measuring public mobile PageSpeed: '+target[:110])
            data=pagespeed(target,os.getenv('PAGESPEED_API_KEY',''),warnings)
            if data is not None:
                data['tested_url']=target
                speeds.append(data)
    else:
        warnings.append('PageSpeed Insights: not configured')
    speed=speeds[0] if speeds else None
    if speed is not None and speed.get("performance_score") is not None and speed["performance_score"]<50:
        review.finding("Low measured mobile PageSpeed performance","Technical SEO","high",website,f"PageSpeed Insights mobile performance score: {speed['performance_score']}/100.","Slow mobile pages can affect experience and search performance.","Review the PageSpeed recommendations for this tested URL, prioritizing bottlenecks with verified impact.","Medium")
    review.findings.sort(key=lambda f:({"critical":0,"high":1,"medium":2,"low":3,"info":4}.get(f["severity"],5),f["category"]))
    findings=review.findings
    html_pages = [p for p in crawled["pages"] if p.get("status") == 200 and not p.get("error")]
    found = crawled["urls_discovered"]
    coverage = {"pages_crawled": len(html_pages), "pages_attempted": len(crawled["pages"]), "fetch_requests": crawled.get("pages_attempted",len(crawled["pages"])),
                "aliases_skipped":len(crawled.get('alias_records',[])),
                "pages_unique_content": len([p for p in html_pages if not p.get("duplicate_content_of")]),
                "urls_discovered": found, "candidate_sample_percent": round(100 * len(html_pages) / found, 1) if found else None,
                "pages_failed": crawled["pages_failed"], "robots_status": crawled["robots_status"],
                "sitemap_status": crawled["sitemap_status"],
                "crawl_limit_reached": crawled.get("crawl_limit_reached", False),
                "selection_method": crawled.get("selection_method", "bounded public HTML sample")}

    on_progress("Preparing organization-specific SEO/GEO intelligence")
    intelligence=research_intelligence(website,[p for p in crawled["pages"] if p.get("status")==200],review,external,warnings,on_progress,discovered_urls=crawled.get("discovered_urls",[]))
    on_progress('Testing public AI search citations')
    benchmark_questions=plan_questions(website,html_pages,intelligence.get('organization_type',''))
    benchmarks=run_benchmarks(website,benchmark_questions,on_progress)
    intelligence['geo_questions']=benchmark_questions  # Only grounded executable questions are shown.
    on_progress('Calculating auditable SEO and GEO sample scores')
    seo_detail=seo_audit_score(review,crawled['pages'],speeds)
    geo_detail=geo_citation_score(benchmarks)
    for item in intelligence.get("research_findings",[]):
        sources=item.get("sources",[])
        if len(sources)<2:continue
        urls=[x["url"] for x in sources]
        evidence=" | ".join(f"{x['url']}: {x['quote']}" for x in sources)
        review.finding(item["title"],"Factual Consistency","medium",urls[0],evidence,item["why"],item["recommendation"],
                       "Medium","Source-quote validated; conflict not independently confirmed",affected_urls=urls,
                       kind="review",sources=[{"url":x["url"],"label":x["quote"][:155]} for x in sources],owner="Content owner / subject expert")
    review.findings.sort(key=lambda f:({"critical":0,"high":1,"medium":2,"low":3,"info":4}.get(f["severity"],5),f["category"]))
    findings=review.findings
    action_summary=action_counts(findings,intelligence.get('content_opportunities',[]))
    summary=baseline_summary(website,findings,coverage,review.scores())
    summary+=(f"\n\nMeasured sampled SEO audit: {seo_detail['score'] if seo_detail['score'] is not None else 'unavailable'}/100; "
              f"valid API citation benchmark: {geo_detail['score'] if geo_detail['score'] is not None else 'unavailable'}/100 "
              f"({geo_detail['cited']}/{geo_detail['valid_tests']} valid responses cited the domain). "
              f"High-impact confirmed issues: {action_summary['urgent_verified']}; high-priority items to verify: {action_summary['high_priority_to_verify']}.")
    if intelligence.get("executive_analysis"):
        summary+="\n\nAI research interpretation (verify editorial claims): "+intelligence["executive_analysis"]
    pages=[{k:p.get(k) for k in ("url","status","error","title","description","h1","headings","word_count","images","images_missing_alt","canonical","robots","schema_types","duplicate_content_of","requested_url","image_evidence")} for p in crawled["pages"]]
    pages_evaluated=coverage["pages_crawled"]
    limitations=[
      "This is a bounded, public-HTML sample; pages excluded by robots rules, uncrawled subpages, dynamic content, media and authenticated content may be missed.",
      f"Retrieved {pages_evaluated} HTML pages; {coverage['urls_discovered']} URLs were discovered as crawl candidates, not verified indexable HTML pages. Candidate sample: {coverage['candidate_sample_percent']}% (not a site-wide coverage estimate).",
      "The sampled SEO audit score uses weighted observed public checks, with omitted tests disclosed. It is not a full-site Google rank or traffic estimate.",
      "The GEO API citation rate excludes ungrounded questions, short or clarification-only answers and provider failures. It does not measure consumer AI app rankings.",
      "AI citation results, where present, are API-grounded question benchmarks, not consumer ChatGPT, Google AI Mode or Perplexity interface rankings.",
      "Equivalent main-text page aliases are excluded from on-page check denominators; valid SEO canonicals/redirects still require separate verification.",
      "Missing canonical declarations and optional meta descriptions are not automatically critical SEO defects.",
      "Any content improvement hypothesis requires full-site verification and user-demand research; text or title matching cannot prove a missing page.",
      "High or medium priority review observations are not confirmed business-impact defects until verification is completed.",
      "Candidate factual conflicts from AI require editorial verification; quotations are checked against fetched pages but interpretation is not independently fact-checked.",
      "External search snippets, when available, are leads for review, not verified facts or measured search rankings.",
      "The supplied external profiles receive public-access checks only; ownership, ratings, listings and social analytics are not validated without authorized APIs.",
      "Legal, medical, financial and time-sensitive claims require qualified human review. Owner-only analytics are intentionally excluded.",
    ]
    limitations.extend(warnings[:18])
    # The original web frontend still reads scores/findings/roadmap; V2 adds optional intelligence sections.
    result={"audit_id":job.get("audit_id","local"),"status":"complete","website":website,
            "created_at":job.get("created_at",now()),"completed_at":now(),
            "scores":{**review.scores(),"seo":seo_detail['score'],"geo":geo_detail['score']},"tests":review.tests,
            "coverage":coverage,"summary":summary,"findings":findings,"roadmap":build_roadmap(findings,intelligence.get("content_opportunities",[])),
            "pages":pages,"external_profiles":external,"pagespeed":speed,"pagespeed_results":speeds,
            "benchmarks":benchmarks,"intelligence":intelligence,
            "source_inventory": crawled.get('discovered_urls',[])[:400],
            "alias_records":crawled.get('alias_records',[]),
            "quality": {"overall_health_measured": False, "geo_visibility_measured": geo_detail['valid_tests']>0,
                        "ai_research_status": intelligence.get("ai_research_status"),
                        "assessment_scope": "bounded_public_html_sample",
                        "review_items": len([f for f in findings if f.get("kind") != "issue"]),
                        "confirmed_markup_issues": len([f for f in findings if f.get("kind") == "issue"])},
            "limitations":limitations,"engine_version":"5.0.0"}
    result['quality_gate']=audit_quality(result)
    return result


def cli():
    parser=argparse.ArgumentParser(description="AI Ritual SEO & GEO audit")
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit-id",help="UUID job already stored in Cloudflare R2")
    group.add_argument("--url",help="Run a local standalone public website audit")
    parser.add_argument("--extra-url",action="append",default=[],help="Supplementary public URL; repeat option")
    parser.add_argument("--output",default="output",help="Local-mode output folder")
    args=parser.parse_args()
    storage=None;prefix=None
    if args.audit_id:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}",args.audit_id):parser.error("Bad audit_id")
        storage=R2();prefix=f"audits/{args.audit_id}"
        job=storage.read(prefix+"/input.json")
    else:job={"audit_id":"local","website":args.url,"extra_urls":args.extra_url,"created_at":now()}
    def progress(message):
        print(message,flush=True)
        if storage:storage.put(prefix+"/progress.json",{"status":"running","message":message,"updated_at":now()})
    try:
        result=execute(job,on_progress=progress)
        progress("Rendering detailed PDF report")
        pdf=create_pdf(result)
        if storage:
            storage.put(prefix+"/report.pdf",pdf,"application/pdf")
            storage.put(prefix+"/result.json",result)
            print("Audit completed and uploaded to R2.")
        else:
            path=Path(args.output);path.mkdir(parents=True,exist_ok=True)
            (path/"result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
            (path/"report.pdf").write_bytes(pdf)
            print(f"Saved {path/'result.json'} and {path/'report.pdf'}")
    except Exception as exc:
        print(f"AUDIT FAILED: {exc}",flush=True)
        failed={"audit_id":job.get("audit_id","local"),"website":job.get("website",""),"status":"failed","completed_at":now(),"summary":"Audit execution failed. The website's SEO/GEO quality was not evaluated.","error":str(exc)[:350],"scores":{"overall":None,"technical":None,"content":None,"geo":None},"coverage":{},"findings":[],"roadmap":[],"pages":[],"external_profiles":[],"limitations":["The analysis could not finish. Check the GitHub Actions job logs and retry."]}
        if storage:storage.put(prefix+"/result.json",failed)
        else:
            path=Path(args.output);path.mkdir(parents=True,exist_ok=True);(path/"result.json").write_text(json.dumps(failed,indent=2),encoding="utf-8")
        raise SystemExit(1)


if __name__=="__main__":cli()
