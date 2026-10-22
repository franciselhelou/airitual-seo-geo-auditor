"""AI Ritual V2 executive-first, source-linked PDF report; rendered from same JSON as frontend."""
from io import BytesIO
from collections import Counter
from html import escape
from urllib.parse import urlparse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_RIGHT

NAVY=colors.HexColor("#17253b");RED=colors.HexColor("#e4485d");MUTED=colors.HexColor("#53647a")
LIGHT=colors.HexColor("#f0f3f8");PALE=colors.HexColor("#f9fafc");BORDER=colors.HexColor("#dce4ef")


def create_pdf(r):
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=43,rightMargin=43,topMargin=63,bottomMargin=55,
        title="AI Ritual - Research-Oriented SEO and GEO Audit",author="AI Ritual")
    styles=getSampleStyleSheet()
    for name,kw in {
        "BrandV2":dict(fontName="Helvetica-Bold",fontSize=11,leading=16,textColor=RED,spaceAfter=18),
        "CoverV2":dict(fontName="Helvetica-Bold",fontSize=28,leading=36,textColor=NAVY,spaceAfter=14),
        "SubV2":dict(fontName="Helvetica",fontSize=13,leading=19,textColor=MUTED,spaceAfter=14),
        "HeadV2":dict(fontName="Helvetica-Bold",fontSize=16,leading=21,textColor=NAVY,spaceBefore=23,spaceAfter=10,keepWithNext=True),
        "MiniV2":dict(fontName="Helvetica-Bold",fontSize=11,leading=15,textColor=NAVY,spaceBefore=13,spaceAfter=6,keepWithNext=True),
        "BodyV2":dict(fontName="Helvetica",fontSize=9,leading=13.5,textColor=NAVY,spaceAfter=8,wordWrap="CJK"),
        "SmallV2":dict(fontName="Helvetica",fontSize=8,leading=11.5,textColor=MUTED,spaceAfter=6,wordWrap="CJK"),
        "CellV2":dict(fontName="Helvetica",fontSize=7.7,leading=10.2,textColor=NAVY,wordWrap="CJK"),
        "WhiteV2":dict(fontName="Helvetica-Bold",fontSize=8,leading=11,textColor=colors.white),
    }.items():styles.add(ParagraphStyle(name=name,**kw))
    story=[];page_width=A4[0]-86
    def p(s,sty="BodyV2"):
        return Paragraph(escape(str(s if s is not None else "")).replace("\n","<br/>"),styles[sty])
    def head(s):story.append(p(s,"HeadV2"))
    def mini(s):story.append(p(s,"MiniV2"))
    def txt(s):story.append(p(s))
    def li(s):story.append(p("• "+str(s)))
    def cell(s):return p(s,"CellV2")
    def link(url,label=None):
        u=str(url or "");label=str(label or u)
        if urlparse(u).scheme not in ("https","http"):return p(label,"SmallV2")
        html=f'<link href="{escape(u,quote=True)}" color="#c63f54">{escape(label)}</link>'
        return Paragraph(html,styles["SmallV2"])
    def table(rows,widths=None,header=True):
        if not rows:return
        formatted=[]
        for i,row in enumerate(rows):
            formatted.append([Paragraph(escape(str(c)),styles["WhiteV2" if i==0 and header else "CellV2"]) for c in row])
        t=Table(formatted,colWidths=widths,repeatRows=1 if header else 0,hAlign="LEFT",splitByRow=1)
        commands=[("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),8),
          ("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
          ("LINEBELOW",(0,-1),(-1,-1),.5,BORDER)]
        if header:commands.extend([("BACKGROUND",(0,0),(-1,0),NAVY),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,LIGHT])])
        else:commands.append(("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,LIGHT]))
        t.setStyle(TableStyle(commands));story.append(t)
    findings=r.get("findings",[]);intel=r.get("intelligence") or {};scores=r.get("scores") or {}
    coverage=r.get("coverage") or {};bysev=Counter(f.get("severity") for f in findings)
    def fmt(v):return f"{round(v)}%" if isinstance(v,(float,int)) else "Not scored"
    # Cover with generous whitespace
    story.extend([Spacer(1,74),p("AI RITUAL  /  RESEARCH-ORIENTED INTELLIGENCE","BrandV2"),
        p("SEO & GEO\nWebsite Audit","CoverV2"),p(r.get("website", ""),"SubV2"),Spacer(1,8),
        HRFlowable(width="100%",thickness=2,color=RED),Spacer(1,21),
        p("Technical evidence, site-specific opportunities, AI-search readiness, and a prioritized correction plan.","SubV2"),
        Spacer(1,25),p("Report version: "+r.get("engine_version","1.0") ,"SmallV2"),
        p("Audit ID: "+r.get("audit_id","local"),"SmallV2"),
        p("Completed: "+r.get("completed_at","Not recorded"),"SmallV2"),
        p("Scope: bounded public-web audit. Measured AI citations, where available, reflect only the documented API tests.","SmallV2"),PageBreak()])

    head("01  Executive assessment")
    txt(r.get("summary","No executive summary provided."))
    mini("Observed test results and audit coverage")
    tests=r.get("tests") or {}
    def check_rate(dim):
        t=tests.get(dim,{})
        passed=t.get("passed",0);failed=t.get("failed",0)
        return f"{passed}/{passed+failed} scored checks" if passed+failed else "No scored checks"
    table([["Dimension", "Observed result", "What this measures"],
        ["Overall website health", "Not assessed", "No site-wide health grade from sampled public HTML"],
        ["HTML fetch success", fmt(scores.get("technical")), check_rate("technical")+"; attempted sample only"],
        ["On-page essentials",fmt(scores.get("content")), check_rate("content")+"; titles, H1 and distinct titles"],
        ["Broad AI visibility", "Not measured", "API samples are presented separately; consumer rankings unavailable"]],
        widths=[141,91,page_width-232])
    story.append(Spacer(1,10))
    table([["HTML retrieved", "URLs found", "Attempted", "Markup issues", "Review items"],
       [coverage.get("pages_crawled",0),coverage.get("urls_discovered",0),
        coverage.get("pages_attempted",coverage.get("pages_crawled",0)),
        sum(f.get("kind")=="issue" for f in findings),
        sum(f.get("kind")!="issue" for f in findings)]],
        widths=[95,102,95,103,page_width-395])
    txt(f"Discovered URLs are crawl candidates, not a verified indexable-page inventory. "
        f"Candidate retrieval rate: {coverage.get('candidate_sample_percent','unavailable')}%. "
        f"Distinct sampled content pages: {coverage.get('pages_unique_content','unavailable')}. "
        f"HTTP fetches attempted: {coverage.get('fetch_requests','unavailable')}; aliases filtered: {coverage.get('aliases_skipped',0)}. "
        "A 100% observed check rate can still coexist with SEO opportunities not measured by that check.")
    mini("Organization and research context")
    txt("Inferred site type: "+intel.get("organization_type","Not established"))
    txt("AI research: "+intel.get("ai_research_status","not_run")+". Public AI citation benchmark: "+(r.get('benchmarks') or {}).get('status','unavailable')+".")
    if r.get("pagespeed"):
        ps=r["pagespeed"];txt(f"Measured mobile PageSpeed performance: {ps.get('performance_score','unavailable')}/100. URL: {ps.get('source_url','')}.")
    elif not r.get('pagespeed_results'):txt("Mobile PageSpeed: No successful public measurements returned; see diagnostics.")
    mini("Top review and correction priorities")
    if findings:
        for f in findings[:5]:
            classification = "CONFIRMED MARKUP OBSERVATION" if f.get("kind")=="issue" else "REQUIRES REVIEW"
            li(f"{classification}: {f['title']} — {f.get('affected_count',1)} affected URLs; {f.get('severity','review')} triage priority")
    else:txt("No prioritized issues were produced from the accessible sample.")

    head("02  Verified source-backed observations")
    strengths=intel.get("strengths",[])
    if strengths:
        for it in strengths[:7]:
            txt(it.get("point",""))
            if it.get('quote'):txt("Source passage: "+it['quote'][:400])
            story.append(link(it.get("url",""),it.get("url","")))
    else:txt("No individual strengths were established from the current sample.")

    conflicts=intel.get("research_findings",[])
    if conflicts:mini("Information consistency candidates")
    if conflicts:
        for f in conflicts[:8]:
            mini(f.get("title","Information discrepancy candidate"));txt(f.get("observation",""));
            txt("Review: "+f.get("recommendation","Verify authoritative records."))
            for src in f.get("sources",[]):
                txt('Observed quote: '+src.get("quote",""));story.append(link(src.get("url",""),src.get("url","")))
    # Avoid a mostly empty, boilerplate inconsistency section when no evidence exists.

    head("03  Grouped observations and validation status")
    bycat=Counter(f.get("category","Other") for f in findings)
    if bycat:table([["Finding category","Grouped observations"]]+[[name,str(n)] for name,n in bycat.most_common()],widths=[330,page_width-330])
    else:txt("No findings available.")
    # Horizontal impact chart rendered in the PDF itself (not only browser UI).
    if bycat:
        mini("Issue distribution by category")
        max_n=max(bycat.values())
        chart_rows=[]
        for name,count in bycat.most_common():
            width=max(6, 195*count/max_n)
            block=Table([[" "]],colWidths=[width],rowHeights=[9])
            block.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),RED)]))
            chart_rows.append([cell(name),cell(count),block])
        chart=Table(chart_rows,colWidths=[214,34,page_width-248],hAlign="LEFT")
        chart.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story.append(chart)
    txt("Findings are grouped by root cause. Priority denotes review order, not confirmed ranking impact. Optional canonical and meta-description absence are not automatic SEO failures.")

    head("04  Detailed findings and evidence")
    if not findings:txt("No source-linked findings were generated.")
    for f in findings:
        mini(f.get("title","Untitled finding"))
        txt(f"{f.get('category')} | {f.get('severity','review').upper()} triage priority | {f.get('affected_count',1)} URL(s) | Effort: {f.get('effort','Review')}")
        txt("Validation: "+("Observed markup check" if f.get("kind")=="issue" else "Observed signal; impact needs manual verification")+" | Evidence confidence: "+str(f.get("confidence","Unknown")))
        txt("Evidence: "+f.get("evidence","None"))
        txt("Implication: "+f.get("why","Not given"))
        txt("Recommended action: "+f.get("recommendation","Not given"))
        txt("Suggested owner: "+f.get("owner","Site editor"))
        for u in f.get("affected_urls",[])[:4]:story.append(link(u))
        extra=f.get("affected_count",0)-min(4,len(f.get("affected_urls",[])))
        if extra>0:story.append(p(f"{extra} more affected URLs are in the structured JSON report.","SmallV2"))
        story.append(HRFlowable(width="100%",thickness=.4,color=BORDER))

    head("05  GEO and answer-readiness analysis")
    txt("API-grounded citation measurements, when available, refer only to the specific prompts and provider APIs tested. They do not represent consumer app rankings or broad market visibility.")
    benchmark=r.get('benchmarks') or {}
    summaries=benchmark.get('summary') or {}
    if summaries:
        mini("Measured citations by API provider")
        table([["Provider","Tests completed","Domain cited"]]+[
            [provider,str(item.get('tests_completed',0)),
             str(item.get('target_cited',0))+" / "+str(item.get('tests_completed',0)) if item.get('tests_completed') else 'Unavailable']
            for provider,item in summaries.items()],widths=[190,148,page_width-338])
        for item in (benchmark.get('results') or [])[:24]:
            if item.get('status')!='completed':continue
            mini(item.get('provider','')+" — "+item.get('question','')[:100])
            txt('Domain cited: '+('Yes' if item.get('target_cited') else 'No')+'. Answer excerpt: '+item.get('answer','')[:340])
            for cite in item.get('citations',[])[:4]:story.append(link(cite.get('url','')))
    else:txt("No public AI API benchmark results are available for this audit.")
    mini("Selected AI-answer benchmark questions")
    questions=intel.get("geo_questions",[])
    if questions:
        for q in questions[:12]:li(q.get("question","") if isinstance(q,dict) else str(q))
    else:txt("AI benchmark questions were not generated.")

    head("06  Content coverage and proposed additions")
    txt("A bounded crawl cannot establish content is absent across a whole website. Check matching resource links before creating pages.")
    topics=intel.get("topic_coverage",[])
    if topics:
        def tstatus(q):
            return {"sampled":"Title or H1 sampled", "mentioned_in_sample":"Body mentions found", "not_seen_in_sample":"Not seen; site-wide unknown"}.get(q.get("status"),"Unknown")
        table([["Topic cluster","Observed in the bounded sample?"]]+[[q.get("topic",""),tstatus(q)] for q in topics],widths=[260,page_width-260])
    mini("Content opportunities")
    suggestions=intel.get("content_opportunities",[])
    for item in suggestions[:14]:
        mini(item.get("title","Content opportunity"));txt(item.get("why",""));txt("Suggested work: "+item.get("proposed_content",""))
        txt("First verification step: "+item.get('recommended_first_step','Verify existing content.'))
        if item.get('quote'):txt("Source passage: "+item['quote'][:460])
        for u in item.get("supporting_urls",[])[:2]:story.append(link(u))
        for u in item.get('existing_related_urls',[])[:3]:story.append(link(u,"Check existing resource: "+u))
    if not suggestions:txt("No specific content opportunities were generated from available sample evidence.")

    head("07  Search intent and keyword strategy")
    txt("The following are exploratory query themes, NOT measured keywords, search volumes, rankings or SEO traffic projections.")
    clusters = intel.get("keyword_clusters",[])
    if not clusters:
        txt("No source-specific query proposals were generated. Generic keywords are deliberately excluded.")
    for cluster in clusters[:12]:
        mini(cluster.get("intent","Search topic"))
        for q in cluster.get("example_queries",[])[:4]:li(q)

    head("08  Structured data and entity strategy")
    observed=sorted({t for page in r.get("pages",[]) for t in (page.get("schema_types") or [])})
    txt("Detected JSON-LD types in sampled responses: "+(", ".join(observed) if observed else "None detected; rendered markup was not independently checked."))
    txt("Before implementing JSON-LD, validate the current rendered markup and choose an organization type supported by the site's publicly stated identity. No search enhancements are guaranteed.")

    head("09  External presence and source research")
    profiles=r.get("external_profiles",[])
    if profiles:
        for item in profiles:
            txt(f"Submitted profile: {item.get('access','unknown')}. {item.get('note','')}");story.append(link(item.get("url","")))
    else:txt("No optional business-directory or social profile URLs were submitted.")
    mini("Optional web-search observations")
    items=intel.get("external_research",[])
    if items:
        for i in items[:10]:
            txt(i.get("title",""));txt("Search snippet (unverified): "+i.get("snippet",""));story.append(link(i.get("url","")))
    else:txt("External search was not configured or did not return usable results. No competitor/ranking analysis is claimed.")

    head("10  Prioritized 90-day work plan")
    for phase in r.get("roadmap",[]):
        mini(phase.get("period",""))
        for task in phase.get("tasks",[])[:12]:li(task)

    head("11  Public measurement and validation plan")
    speed_results=r.get('pagespeed_results') or []
    if speed_results:
        mini('Public mobile PageSpeed measurements')
        for item in speed_results:
            txt(f"{item.get('tested_url','')} — performance: {item.get('performance_score','unavailable')}/100; metrics: {item.get('metrics',{})}")
    bench=r.get('benchmarks') or {}
    if bench.get('results'):
        txt('Repeat the recorded '+str(bench.get('questions_selected',0))+' public AI questions, with the same providers, on a fixed schedule; compare source citations and answer quality.')
    txt('Track measured public indicators: successful distinct HTML pages, verified fixes and review resolutions, structured markup validation, and any completed mobile PageSpeed measurements.')
    quality=r.get('quality_gate') or {}
    txt('Document quality gate: '+str(quality.get('status','not_run'))+'. '+str(quality.get('checks',{})))

    head("12  Page inventory (sampled)")
    page_rows=[["Final URL (scheme and path)","HTTP","Words","Page title"]]
    for page in r.get("pages",[]):
        page_url=page.get('url','')
        parsed=urlparse(page_url)
        path=f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
        page_rows.append([path[:85],str(page.get("status","")),str(page.get("word_count",0)),str(page.get("title","")[:95])])
    if len(page_rows)>1:table(page_rows,widths=[184,43,50,page_width-277])
    else:txt("No HTML pages collected.")

    head("13  Complete affected-URL register")
    for f in findings:
        urls=f.get("affected_urls",[])
        if not urls:continue
        mini(f.get("id","")+" — "+f.get("title",""))
        for u in urls:story.append(link(u))

    head("14  Methodology, coverage and limitations")
    for line in r.get("limitations",[])[:10]:li(line)
    txt("Method: public HTML, observed source excerpts, measured provider calls and conditional research hypotheses. Private site-owner data is never requested. Confirm editorial or regulatory decisions with responsible organizations.")

    def draw(canvas,doc):
        canvas.saveState();w,h=A4
        canvas.setStrokeColor(BORDER);canvas.line(43,h-45,w-43,h-45)
        canvas.setFillColor(RED);canvas.setFont("Helvetica-Bold",9);canvas.drawString(43,h-32,"AI RITUAL  /  SEO & GEO INTELLIGENCE")
        canvas.setStrokeColor(BORDER);canvas.line(43,42,w-43,42)
        canvas.setFont("Helvetica",8);canvas.setFillColor(MUTED)
        canvas.drawString(43,28,"airitual.com  •  Sample-scoped, evidence-first audit")
        canvas.drawRightString(w-43,28,"Page "+str(doc.page))
        canvas.restoreState()
    doc.build(story,onFirstPage=draw,onLaterPages=draw)
    return buf.getvalue()
