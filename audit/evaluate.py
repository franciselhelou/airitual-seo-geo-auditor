"""Bounded-audit scoring and evidence classification.

Scores are *rates of explicit, observed checks*, never global site-health or
measured GEO visibility. Observations requiring intent/content review are not
silently converted into confirmed SEO defects.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from urllib.parse import urlparse
import requests

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class Review:
    def __init__(self):
        self.findings = []
        self.tests = {k: {"passed": 0, "failed": 0, "untested": 0, "checks": {}}
                      for k in ("technical", "content", "geo")}

    def test(self, dimension, ok, check="unspecified"):
        state = "untested" if ok is None else "passed" if ok else "failed"
        self.tests[dimension][state] += 1
        check_data = self.tests[dimension]["checks"].setdefault(check, {"passed": 0, "failed": 0, "untested": 0})
        check_data[state] += 1

    def finding(self, title, category, severity, url, evidence, why, recommendation,
                effort="Medium", confidence="High", affected_urls=None, kind="review",
                sources=None, owner="Website administrator", validation_status=None):
        urls = list(dict.fromkeys(affected_urls or ([url] if url else [])))
        validation_status = validation_status or (
            "verified_observation_impact_needs_review" if kind == "review" else "observed_html_check"
        )
        self.findings.append({
            "id": f"AR-{len(self.findings)+1:04d}", "title": title, "category": category,
            "severity": severity, "url": url or (urls[0] if urls else ""),
            "affected_urls": urls, "affected_count": len(urls), "evidence": str(evidence)[:1400],
            "why": why, "recommendation": recommendation, "effort": effort,
            "confidence": confidence, "kind": kind, "validation_status": validation_status,
            "sources": sources or [{"url": u, "label": "Observed page"} for u in urls[:5]],
            "owner": owner,
        })

    def scores(self):
        scores = {}
        for dim, totals in self.tests.items():
            n = totals["passed"] + totals["failed"]
            scores[dim] = round(100 * totals["passed"] / n) if n else None
        # A bounded crawl and suggested GEO questions do not constitute a measured
        # global SEO/GEO health result. No composite score is calculated.
        scores["overall"] = None
        return scores


def _fingerprint(page):
    text = " ".join(str(page.get("text") or "").casefold().split())
    if len(text) < 100:
        return None  # Insufficient extracted text to establish equivalence.
    return sha256((str(page.get("title", "")).casefold().strip() + "\n" + text).encode("utf-8")).hexdigest()


def analyze_site(website, crawl, external, progress=lambda s: None):
    r = Review()
    pages = crawl.get("pages", [])
    valid = [p for p in pages if p.get("status") == 200 and not p.get("error")]
    if not valid:
        r.finding("No public HTML pages could be evaluated", "Crawl availability", "high", website,
                  "No accessible HTML pages were collected.",
                  "This audit cannot determine SEO health when the crawler cannot access HTML.",
                  "Check site availability, crawler access and robots rules before retrying.",
                  validation_status="audit_incomplete")
        return r

    buckets = defaultdict(list)
    fingerprint_primary = {}
    unique = []
    for p in valid:
        fingerprint = _fingerprint(p)
        if fingerprint and fingerprint in fingerprint_primary:
            primary=fingerprint_primary[fingerprint]
            if p['url'].rstrip('/') != primary['url'].rstrip('/'):
                p["duplicate_content_of"] = primary["url"]
                buckets["exact_alias"].append(p)
        else:
            unique.append(p)
            if fingerprint:
                fingerprint_primary[fingerprint] = p

    for p in pages:
        # Check HTTP availability across the *attempted* sample, including failures.
        # Do not infer status of discovered-but-unrequested URLs.
        r.test("technical", p.get("status") == 200 and not p.get("error"), "html_fetch_200")
        if p.get("status", 0) >= 400 or p.get("error"):
            buckets["http"].append(p)

    # Distinct content is evaluated once to prevent aliases artificially
    # inflating scores (e.g. / vs /1/Home).
    for p in unique:
        url = p["url"]
        progress("Evaluating " + (urlparse(url).path or "/"))
        r.test("content", bool(str(p.get("title", "")).strip()), "html_title_present")
        r.test("content", bool(p.get("h1", [])), "primary_heading_present")
        # GEO requires actual answer quality and citation testing; all current
        # text-length/structure observations are review prompts, NOT pass/fail.
        r.test("geo", None, "actual_ai_answer_visibility_not_tested")
        if not p.get("title"): buckets["title"].append(p)
        if not p.get("description"): buckets["description"].append(p)
        if not p.get("h1"): buckets["h1"].append(p)
        if len(p.get("h1", [])) > 1: buckets["multi_h1"].append(p)
        if p.get("images", 0) and p.get("images_missing_alt", 0): buckets["images"].append(p)
        if "noindex" in p.get("robots", ""): buckets["noindex"].append(p)
        if p.get("word_count", 0) < 100: buckets["thin"].append(p)
        elif not (p.get("h1") or p.get("headings")): buckets["structure"].append(p)

    # Compare repeated titles only after removing content-identical aliases.
    titles = defaultdict(list)
    for p in unique:
        if p.get("title"):
            titles[p["title"].strip().casefold()].append(p)
    distinct_duplicates = [g for g in titles.values() if len(g) > 1]
    duplicate_urls = {p["url"] for group in distinct_duplicates for p in group}
    for p in unique:
        if p.get("title"):
            r.test("content", p["url"] not in duplicate_urls, "unique_title_for_distinct_content")
        else:
            r.test("content", None, "unique_title_for_distinct_content")

    if buckets["http"]:
        ps = buckets["http"]
        r.finding("Failed HTML requests in the attempted sample", "Technical SEO", "high", ps[0]["url"],
                  f"{len(ps)} attempted URL(s) failed; examples: " +
                  ", ".join(f"{p['url']} (HTTP {p.get('status', 'unknown')})" for p in ps[:4]),
                  "A failed fetch may be a broken page, temporary server issue, or crawler restriction.",
                  "Retry affected links from a normal browser and check server logs before recommending removal or redirects.",
                  "Medium", affected_urls=[p["url"] for p in ps], kind="review")
    if buckets["noindex"]:
        ps = buckets["noindex"]
        r.finding("Review indexing intent of noindex pages", "Technical SEO", "medium", ps[0]["url"],
                  f"{len(ps)} sampled page(s) declared a noindex directive.",
                  "Noindex may be deliberate; only unintended exclusions require correction.",
                  "Confirm which pages should be indexed before altering directives.",
                  "Low", affected_urls=[p["url"] for p in ps])
    if buckets["title"]:
        ps = buckets["title"]
        r.finding("HTML title absent on sampled pages", "Content & On-page", "medium", ps[0]["url"],
                  f"{len(ps)} sampled distinct page(s) have no HTML title.",
                  "A descriptive page title helps explain a page's purpose.",
                  "Add appropriate, distinct titles to pages meant to be found.",
                  "Low", affected_urls=[p["url"] for p in ps], kind="issue")
    if buckets["description"]:
        ps = buckets["description"]
        r.finding("Review missing meta descriptions", "Content & On-page", "low", ps[0]["url"],
                  f"{len(ps)} of {len(unique)} distinct sampled pages have no meta description.",
                  "Search providers may generate snippets independently; absence is not automatically an SEO defect.",
                  "Prioritize important user-task pages for helpful, page-specific descriptions.",
                  "Low", affected_urls=[p["url"] for p in ps])
    if buckets["h1"]:
        ps = buckets["h1"]
        r.finding("Primary H1 heading absent", "Content & On-page", "medium", ps[0]["url"],
                  f"{len(ps)} distinct sampled pages have no H1 element.",
                  "A useful visual/document outline improves comprehension.",
                  "Check rendered page structure before adding headings.",
                  "Low", affected_urls=[p["url"] for p in ps], kind="issue")
    if buckets["multi_h1"]:
        ps = buckets["multi_h1"]
        r.finding("Review multiple H1 headings", "Content & On-page", "low", ps[0]["url"],
                  f"{len(ps)} sampled pages have more than one H1; not itself a search penalty.",
                  "This requires an actual hierarchy/readability assessment.",
                  "Change the hierarchy only when it is confusing in the rendered page.",
                  "Low", confidence="Medium", affected_urls=[p["url"] for p in ps])
    if buckets["images"]:
        ps = buckets["images"]
        r.finding("Determine which images need descriptive alt text", "Accessibility & Content", "medium", ps[0]["url"],
                  f"{sum(p.get('images_missing_alt', 0) for p in ps)} image(s) without nonempty alt text across {len(ps)} pages.",
                  "Decorative imagery may correctly use alt='' and needs visual/context review.",
                  "Audit informative images individually; leave intentionally decorative images with empty alt text.",
                  "Medium", confidence="Medium", affected_urls=[p["url"] for p in ps])
    if buckets["thin"]:
        ps = buckets["thin"]
        r.finding("Review short extracted pages for answer usefulness", "Content review / GEO", "low", ps[0]["url"],
                  f"{len(ps)} distinct sampled HTML pages contain fewer than 100 extracted words; this is a review threshold, not a content-quality score.",
                  "Directories, navigation and JavaScript-driven pages may legitimately appear short.",
                  "Inspect page type, rendered content, files, and user intent before changing text.",
                  "Medium", confidence="Medium", affected_urls=[p["url"] for p in ps])
    if buckets["structure"]:
        ps = buckets["structure"]
        r.finding("Review text-heavy pages without structured headings", "Content review / GEO", "low", ps[0]["url"],
                  f"{len(ps)} substantive pages lack extracted H1/H2/H3 headings.",
                  "Answer retrieval may benefit from appropriate section structure.",
                  "Check the rendered layout, then add useful sections if appropriate.",
                  "Low", confidence="Medium", affected_urls=[p["url"] for p in ps])
    if distinct_duplicates:
        affected = [p["url"] for group in distinct_duplicates for p in group]
        r.finding("Distinct pages share HTML titles", "Content & On-page", "medium", affected[0],
                  f"{len(distinct_duplicates)} duplicated-title group(s) across {len(affected)} pages with different extracted content.",
                  "Different pages may compete for the same intent; exact content aliases are excluded from this observation.",
                  "Review page intent and set descriptive, distinguishable titles if pages serve different purposes.",
                  "Medium", confidence="Medium", affected_urls=affected)
    if buckets["exact_alias"]:
        ps = [p for p in buckets["exact_alias"] if p['url']!=p.get('duplicate_content_of')]
        if not ps:ps=[]
        r.finding("Equivalent content accessible at multiple URLs", "Canonicalization review", "low", ps[0]["url"],
                  f"{len(ps)} sampled URL(s) have the same normalized extracted main text as another sampled URL; "
                  f"example {ps[0]['url']} vs {ps[0]['duplicate_content_of']}.",
                  "Equivalent URLs may already be correctly canonicalized or redirected.",
                  "Verify final redirects and rel=canonical before recommending any URL changes.",
                  "Low", confidence="Medium", affected_urls=[p["url"] for p in ps])

    home = next((p for p in valid if urlparse(p["url"]).path in ("", "/")), valid[0])
    if not home.get("schema_types"):
        r.finding("Organization JSON-LD not detected in fetched homepage HTML", "Structured Data", "low", home["url"],
                  "No JSON-LD @type was detected in the fetched HTML response.",
                  "Structured data can clarify identity but is optional and may be inserted by JavaScript.",
                  "Check rendered output and schema validity, then consider an appropriate organization type.",
                  "Medium", "Medium")
    if crawl.get("sitemap_status") != "present":
        r.finding("XML sitemap location was not confirmed", "Technical SEO", "low", website,
                  "No usable XML sitemap was found at the selected default locations.",
                  "Sitemaps are optional, and other locations may exist.",
                  "Check the site's robots.txt Sitemap declarations and CMS-specific endpoints.",
                  "Low", "Medium")
    if external:
        unavailable = [x for x in external if x.get("access") != "accessible"]
        if unavailable:
            r.finding("Public checks could not verify all supplied profiles", "External Presence", "info", unavailable[0]["url"],
                      f"{len(unavailable)} of {len(external)} supplied links were unavailable to public inspection.",
                      "An inaccessible profile is not proof of missing business information.",
                      "Check restricted profiles manually or with authorized APIs.",
                      "Low", affected_urls=[x["url"] for x in unavailable])
    r.findings.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 5), x["title"]))
    return r


def pagespeed(website, api_key, warnings):
    if not api_key:
        warnings.append("PageSpeed Insights was not measured; optional PAGESPEED_API_KEY is not configured.")
        return None
    try:
        res = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                           params={"url": website, "strategy": "mobile", "category": "PERFORMANCE", "key": api_key}, timeout=35)
        res.raise_for_status()
        obj = res.json()
        lh = obj.get("lighthouseResult", {})
        score = lh.get("categories", {}).get("performance", {}).get("score")
        audits = lh.get("audits", {})
        return {"strategy": "mobile", "performance_score": round(score * 100) if score is not None else None,
                "source": "Google PageSpeed Insights",
                "source_url": "https://pagespeed.web.dev/analysis?url=" + requests.utils.quote(website, safe=""),
                "metrics": {k: audits.get(k, {}).get("displayValue") for k in
                            ("largest-contentful-paint", "interaction-to-next-paint", "cumulative-layout-shift") if audits.get(k)}}
    except Exception as exc:
        warnings.append("PageSpeed Insights request failed: " + str(exc)[:140])
        return None


def make_roadmap(findings):
    # Unverified observations are actions to *validate*, not instructions to make a change.
    confirmed = [f for f in findings if f.get("kind") == "issue"]
    reviews = [f for f in findings if f.get("kind") != "issue"]
    high = [f for f in confirmed if f.get("severity") in ("critical", "high", "medium")]
    ordered_reviews = sorted(reviews, key=lambda f: (SEVERITY_ORDER.get(f.get("severity"), 4), -f.get("affected_count", 1)))
    stages = [
        ("First 7 days — validate observed risks", ordered_reviews[:6]),
        ("Days 8–30 — correct confirmed issues", high),
        ("Days 31–90 — optional enhancements and recheck",
         [f for f in confirmed if f not in high] + ordered_reviews[6:]),
    ]
    result = []
    for label, items in stages:
        tasks = []
        for f in items[:8]:
            action = "Verify: " if f.get("kind") != "issue" else "Correct: "
            tasks.append(f"{action}{f['title']} ({f.get('affected_count', 0)} URLs). {f['recommendation']}")
        if not tasks:
            tasks = ["No validated items in this stage. Recheck priority using site owner input and verified search data."]
        result.append({"period": label, "tasks": tasks})
    return result


def baseline_summary(website, findings, crawl, scores):
    measured = crawl.get("pages_crawled", 0)
    discovered = crawl.get("urls_discovered", 0)
    if not measured:
        return f"No public HTML pages were evaluated for {website}. No site-quality score is available. Review crawler access."
    observed = sum(f.get("kind") == "issue" for f in findings)
    pending = len(findings) - observed
    return (f"A bounded audit retrieved {measured} HTML pages from {discovered} discovered candidate URLs for {website}. "
            f"It produced {observed} directly observed markup issues and {pending} items for review. "
            "The page-check percentages below describe only the specified checks on the sampled URLs; "
            "they do not measure comprehensive SEO health or GEO/AI visibility. "
            "An overall site-health percentage is intentionally withheld until broader validation is available.")
