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
    speed=pagespeed(website,os.getenv("PAGESPEED_API_KEY",""),warnings)
    if speed is not None and speed.get("performance_score") is not None and speed["performance_score"]<50:
        review.finding("Low measured mobile PageSpeed performance","Technical SEO","high",website,f"PageSpeed Insights mobile performance score: {speed['performance_score']}/100.","Slow mobile pages can affect experience and search performance.","Review the PageSpeed recommendations for this tested URL, prioritizing bottlenecks with verified impact.","Medium")
    review.findings.sort(key=lambda f:({"critical":0,"high":1,"medium":2,"low":3,"info":4}.get(f["severity"],5),f["category"]))
    findings=review.findings
    coverage={"pages_crawled":len([p for p in crawled["pages"] if p["status"]==200]),"urls_discovered":crawled["urls_discovered"],"pages_failed":crawled["pages_failed"],"robots_status":crawled["robots_status"],"sitemap_status":crawled["sitemap_status"]}
    on_progress("Preparing organization-specific SEO/GEO intelligence")
    intelligence=research_intelligence(website,[p for p in crawled["pages"] if p.get("status")==200],review,external,warnings,on_progress)
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
    summary=baseline_summary(website,findings,coverage,review.scores())
    if intelligence.get("executive_analysis"):
        summary+="\n\nAI research interpretation (verify editorial claims): "+intelligence["executive_analysis"]
    pages=[{k:p.get(k) for k in ("url","status","title","description","h1","headings","word_count","images","images_missing_alt","canonical","robots","schema_types")} for p in crawled["pages"]]
    pages_evaluated=coverage["pages_crawled"]
    limitations=[
      "This is a bounded, public-HTML sample; pages excluded by robots rules, uncrawled subpages, dynamic content, media and authenticated content may be missed.",
      f"Analyzed {pages_evaluated} HTML pages out of {coverage['urls_discovered']} discovered URLs. This is not a comprehensive site-wide crawl.",
      "Technical, content and GEO-readiness scores use disclosed sampled checks. GEO readiness is not measured AI visibility, and observed ChatGPT/Google AI/Perplexity citations were NOT tested.",
      "Missing canonical declarations and optional meta descriptions are not automatically critical SEO defects.",
      "Content gap suggestions mean NOT OBSERVED IN THE SAMPLE, not confirmed absent from the entire website.",
      "Candidate factual conflicts from AI require editorial verification; quotations are checked against fetched pages but interpretation is not independently fact-checked.",
      "External search snippets, when available, are leads for review, not verified facts or measured search rankings.",
      "The supplied external profiles receive public-access checks only; ownership, ratings, listings and social analytics are not validated without authorized APIs.",
      "Legal, medical, financial and time-sensitive claims require qualified human review. Search traffic, backlinks and conversions require separate authorized data sources.",
    ]
    limitations.extend(warnings[:18])
    # The original web frontend still reads scores/findings/roadmap; V2 adds optional intelligence sections.
    return {"audit_id":job.get("audit_id","local"),"status":"complete","website":website,
            "created_at":job.get("created_at",now()),"completed_at":now(),"scores":review.scores(),"tests":review.tests,
            "coverage":coverage,"summary":summary,"findings":findings,"roadmap":make_roadmap(findings),
            "pages":pages,"external_profiles":external,"pagespeed":speed,"intelligence":intelligence,
            "limitations":limitations,"engine_version":"2.0.0"}


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
