"""V2 evidence-first assessment. Group template issues and never score optional signals as failures."""
from collections import Counter, defaultdict
from urllib.parse import urlparse
import os
import requests

SEVERITY_ORDER = {"critical":0,"high":1,"medium":2,"low":3,"info":4}

class Review:
    def __init__(self):
        self.findings=[]
        self.tests={k:{"passed":0,"failed":0,"untested":0} for k in ("technical","content","geo")}
    def test(self, dimension, ok):
        self.tests[dimension]["untested" if ok is None else "passed" if ok else "failed"]+=1
    def finding(self,title,category,severity,url,evidence,why,recommendation,effort="Medium",confidence="High",affected_urls=None,kind="issue",sources=None,owner="Website administrator"):
        urls=list(dict.fromkeys(affected_urls or ([url] if url else [])))
        self.findings.append({"id":f"AR-{len(self.findings)+1:04d}","title":title,"category":category,"severity":severity,
          "url":url or (urls[0] if urls else ""),"affected_urls":urls,"affected_count":len(urls),"evidence":str(evidence)[:1400],
          "why":why,"recommendation":recommendation,"effort":effort,"confidence":confidence,"kind":kind,
          "sources":sources or ([{"url":u,"label":"Observed page"} for u in urls[:5]]),"owner":owner})
    def scores(self):
        scores={}
        for dim in self.tests:
            t=self.tests[dim];n=t["passed"]+t["failed"]
            scores[dim]=round(100*t["passed"]/n) if n else None
        weighted=[(scores[k],w) for k,w in (("technical",.45),("content",.35),("geo",.2)) if scores[k] is not None]
        scores["overall"]=round(sum(s*w for s,w in weighted)/sum(w for _,w in weighted)) if weighted else None
        return scores

def analyze_site(website,crawl,external,progress=lambda s:None):
    r=Review();pages=crawl.get("pages",[]);valid=[p for p in pages if p.get("status")==200 and not p.get("error")]
    if not valid:
        r.finding("No public HTML pages could be evaluated","Technical SEO","high",website,"No accessible HTML pages were collected.",
          "The crawler cannot assess search health without accessible pages.","Confirm site availability, robots rules and crawler access before rerunning.","Medium","High")
        return r
    buckets=defaultdict(list)
    for p in valid:
        url=p["url"];progress("Evaluating "+(urlparse(url).path or "/"))
        # Score only clear, meaningful pass/fail rules; avoid opt-in meta descriptions, canonical tags or headings count.
        r.test("technical","noindex" not in p.get("robots",""))
        r.test("technical",p.get("status")==200)
        r.test("content",bool(p.get("title","")))
        r.test("content",bool(p.get("h1",[])))
        if p.get("word_count",0)>=100 and (p.get("h1") or p.get("headings")):
            r.test("geo",True)
        elif p.get("word_count",0)<100:
            # Potential index page, intentional directory, or extraction limitation: untested rather than failure
            r.test("geo",None);buckets["thin"].append(p)
        else:r.test("geo",False);buckets["structure"].append(p)
        if not p.get("title"):buckets["title"].append(p)
        if not p.get("description"):buckets["description"].append(p)
        if not p.get("h1"):buckets["h1"].append(p)
        if len(p.get("h1",[]))>1:buckets["multi_h1"].append(p)
        if not p.get("canonical"):buckets["canonical_optional"].append(p)
        if p.get("images",0) and p.get("images_missing_alt",0):buckets["images"].append(p)
        if "noindex" in p.get("robots",""):buckets["noindex"].append(p)
    for p in pages:
        if p.get("status",0)>=400 or p.get("error"):buckets["http"].append(p)
    if buckets["http"]:
        ps=buckets["http"];r.finding("Crawled URLs failed to return usable HTML","Technical SEO","high",ps[0]["url"],
          f"{len(ps)} URL(s) failed; examples: "+", ".join(f"{p['url']} (HTTP {p.get('status')})" for p in ps[:4]),
          "Broken or inaccessible linked pages can affect navigation and discovery.","Repair confirmed broken pages or redirect them to genuinely related working destinations; verify before bulk changes.","Medium",affected_urls=[p["url"] for p in ps])
    if buckets["noindex"]:
        ps=buckets["noindex"];r.finding("Noindex directives need confirmation","Technical SEO","medium",ps[0]["url"],
          f"{len(ps)} examined pages carried noindex directives.","Intended exclusions are legitimate; accidental exclusions hide important content.",
          "Confirm indexing intent for each affected page; remove noindex only from pages intended for public search.","Low",affected_urls=[p["url"] for p in ps],confidence="High")
    if buckets["title"]:
        ps=buckets["title"];r.finding("HTML title missing on pages","Content & On-page","high",ps[0]["url"],
          f"{len(ps)} scanned pages have an empty HTML title.","Titles are core descriptive signals for visitors and search systems.",
          "Write distinct descriptive titles reflecting each page's purpose and the organization.","Low",affected_urls=[p["url"] for p in ps])
    if buckets["description"]:
        ps=buckets["description"];r.finding("Missing meta descriptions on sampled pages","Content & On-page","medium",ps[0]["url"],
          f"{len(ps)} of {len(valid)} examined pages have no HTML meta description.","Descriptions may help shape snippets, although Google can generate its own.",
          "Prioritize high-value service and conversion pages; write useful descriptions specific to the page rather than blindly rewriting archives.","Low",affected_urls=[p["url"] for p in ps],confidence="High")
    if buckets["h1"]:
        ps=buckets["h1"];r.finding("Pages without a primary H1","Content & On-page","medium",ps[0]["url"],
          f"{len(ps)} scanned pages have no H1 heading.","A clear heading makes the main topic easier to understand and navigate.",
          "Use a meaningful heading for the main page subject; avoid adding repeated decorative H1 tags.","Low",affected_urls=[p["url"] for p in ps])
    if buckets["multi_h1"]:
        ps=buckets["multi_h1"];r.finding("Review pages with multiple H1 headings","Content & On-page","low",ps[0]["url"],
          f"{len(ps)} pages include multiple H1 headings. This is not itself a search penalty.","An unclear document outline can harm readability.",
          "Review hierarchy manually and change headings only where the page's structure is confusing.","Low",confidence="Medium",affected_urls=[p["url"] for p in ps],kind="review")
    if buckets["images"]:
        ps=buckets["images"];total=sum(p.get("images_missing_alt",0) for p in ps)
        r.finding("Review images with missing or empty alt descriptions","Accessibility & Content","medium",ps[0]["url"],
          f"{total} images across {len(ps)} sampled pages have no nonempty alt text.","Informational images require meaningful descriptions; decorative images can intentionally use empty alt text.",
          "Identify informative images first and write descriptive alt text; leave decorative images intentionally empty.","Medium",confidence="Medium",affected_urls=[p["url"] for p in ps],kind="review")
    if buckets["thin"]:
        ps=buckets["thin"]
        r.finding("Important landing pages may lack extractable answers","GEO Readiness","medium",ps[0]["url"],
          f"{len(ps)} HTML pages exposed fewer than 100 extracted text words; examples: "+", ".join(f"{p.get('title','Untitled')} ({p.get('word_count')} words)" for p in ps[:4]),
          "Index or navigational pages may intentionally be short, but substantive pages should provide answers in HTML.",
          "Manually review these pages for purpose and any content hidden in JavaScript, images or attached files. Expand only pages that should answer visitor questions.","Medium",confidence="Medium",affected_urls=[p["url"] for p in ps],kind="review")
    if buckets["structure"]:
        ps=buckets["structure"];r.finding("Substantive pages need clearer section headings","GEO Readiness","low",ps[0]["url"],
          f"{len(ps)} substantial pages had no extracted H1/H2/H3 headings.","Readable headings improve navigation and answer extraction.",
          "Introduce descriptive sections where the present layout genuinely obscures important information.","Low",confidence="Medium",affected_urls=[p["url"] for p in ps])
    titles=defaultdict(list)
    for p in valid:
        if p.get("title"):titles[p["title"].strip().casefold()].append(p)
    dup=[group for group in titles.values() if len(group)>1]
    if dup:
        affected=[p["url"] for group in dup for p in group]
        r.finding("Duplicate page titles require URL intent review","Content & On-page","medium",affected[0],
          f"{len(dup)} repeated title group(s) across {len(affected)} pages; first group: "+", ".join(dup[0][i]["url"] for i in range(min(3,len(dup[0])))),
          "Equivalent home or archive URLs may legitimately share a title, but important distinct pages should not.",
          "Check redirects and page equivalence first; set canonical or 301 redirect for truly duplicated URLs, unique titles for different pages.","Medium",affected_urls=affected)
    # Canonical absence itself is neither a failed check nor a repetitive finding.
    home=next((p for p in valid if urlparse(p["url"]).path in ("", "/")),valid[0])
    schema=set(home.get("schema_types",[]))
    if not schema:
        is_government=any(w in (home.get("title","")+" "+home.get("text","")[:1300]).lower() for w in ("city of ","municipal", "city council", "city hall", "government"))
        recommended="GovernmentOrganization or GovernmentOffice as applicable" if is_government else "an appropriate Organization subtype (LocalBusiness only when it truly fits)"
        r.finding("Organization identity JSON-LD was not detected","Structured Data","low",home["url"],
          "No valid JSON-LD @type found in the retrieved homepage HTML.","Correct structured identity clarifies the organization and its official web presence.",
          f"Validate rendered output and consider {recommended}, with verified organization name, URL and relevant identity links.","Medium","Medium",kind="review")
    if crawl.get("sitemap_status")!="present":
        r.finding("XML sitemap requires verification","Technical SEO","low",website,
          "A sitemap was not discovered at the two default paths inspected; alternate paths may exist.","Sitemaps help discovery but are optional, and the limited test does not establish absence.",
          "Inspect robots.txt for the declared sitemap, check the known CMS sitemap endpoint, and verify canonical entries before treating this as a defect.","Low","Medium",kind="review")
    if external:
        unavailable=[x for x in external if x.get("access")!="accessible"]
        if unavailable:r.finding("Supplied profiles could not all be verified","External Presence","info",unavailable[0]["url"],
          f"{len(unavailable)} of {len(external)} supplied links were unavailable to public HTTP inspection.",
          "Platform restrictions are not evidence of missing or incorrect profiles.","Confirm inaccessible listings manually or through approved owner-authorized APIs.","Low",kind="review",affected_urls=[x["url"] for x in unavailable])
    r.findings.sort(key=lambda x:(SEVERITY_ORDER.get(x["severity"],5),x["title"]))
    return r

def pagespeed(website,api_key,warnings):
    if not api_key:
        warnings.append("PageSpeed Insights was not measured; optional PAGESPEED_API_KEY is not configured.")
        return None
    try:
        res=requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed",params={"url":website,"strategy":"mobile","category":"PERFORMANCE","key":api_key},timeout=35)
        res.raise_for_status();obj=res.json();lh=obj.get("lighthouseResult",{})
        score=lh.get("categories",{}).get("performance",{}).get("score")
        audits=lh.get("audits",{})
        return {"strategy":"mobile","performance_score":round(score*100) if score is not None else None,
                "source":"Google PageSpeed Insights", "source_url":"https://pagespeed.web.dev/analysis?url="+requests.utils.quote(website,safe=""),
                "metrics":{k:audits.get(k,{}).get("displayValue") for k in ("largest-contentful-paint","interaction-to-next-paint","cumulative-layout-shift") if audits.get(k)}}
    except Exception as exc:
        warnings.append("PageSpeed Insights request failed: "+str(exc)[:140]);return None

def make_roadmap(findings):
    ordered=sorted((f for f in findings if f.get("kind")!="opportunity"),key=lambda f:(SEVERITY_ORDER.get(f.get("severity"),4),-f.get("affected_count",1)))
    groups=[("First 7 days — verify urgent issues",[f for f in ordered if f["severity"] in ("critical","high")]),
            ("Days 8–30 — improve important pages",[f for f in ordered if f["severity"]=="medium"]),
            ("Days 31–90 — refinements and reassessment",[f for f in ordered if f["severity"] in ("low","info")])]
    roadmap=[]
    for label,items in groups:
        tasks=[f"{f['title']} ({f.get('affected_count',1)} affected URL(s)) — {f['recommendation']}" for f in items[:8]]
        if not tasks:tasks=["Verify the highest-traffic pages using Search Console and address validated opportunities; no confirmed urgent defect was detected in the sample."]
        roadmap.append({"period":label,"tasks":tasks})
    return roadmap

def baseline_summary(website,findings,crawl,scores):
    counts=Counter(f["severity"] for f in findings)
    measured=crawl.get("pages_crawled",0);found=crawl.get("urls_discovered",0)
    if not measured:return f"No accessible public HTML pages were collected for {website}. Search health cannot be scored. Review crawl restrictions and retry."
    group="; ".join(f["title"] for f in findings[:3]) or "No major detected technical issues"
    return (f"This bounded audit examined {measured} HTML pages from {found} discovered URLs for {website}. "
            f"It identified {len(findings)} grouped observations ({counts['critical']} critical, {counts['high']} high, "
            f"{counts['medium']} medium). Leading review areas: {group}. "
            "Results describe sampled pages, not measured Google rankings or observed AI citation performance. "
            "Some observations require editorial verification before implementation.")
