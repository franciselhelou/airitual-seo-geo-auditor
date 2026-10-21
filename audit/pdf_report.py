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
        p("SEO & GEO<br/>Website Audit","CoverV2"),p(r.get("website", ""),"SubV2"),Spacer(1,8),
        HRFlowable(width="100%",thickness=2,color=RED),Spacer(1,21),
        p("Technical evidence, site-specific opportunities, AI-search readiness, and a prioritized correction plan.","SubV2"),
        Spacer(1,25),p("Report version: "+r.get("engine_version","1.0") ,"SmallV2"),
        p("Audit ID: "+r.get("audit_id","local"),"SmallV2"),
        p("Completed: "+r.get("completed_at","Not recorded"),"SmallV2"),
        p("Scope: bounded publicly accessible sample; not a verified search-ranking or AI-citation study.","SmallV2"),PageBreak()])

    head("01  Executive assessment")
    txt(r.get("summary","No executive summary provided."))
    mini("Scores and sample coverage")
    table([["Dimension","Sample score","Interpretation"],
       ["Overall website health",fmt(scores.get("overall")),"Weighted sample checks; not a ranking metric"],
       ["Technical SEO",fmt(scores.get("technical")),"Measured accessibility and indexability signals"],
       ["On-page content",fmt(scores.get("content")),"Core page-title coverage, sampled"],
       ["GEO readiness",fmt(scores.get("geo")),"HTML answer-readiness heuristic; NOT actual AI visibility"]],
       widths=[148,83,page_width-231])
    story.append(Spacer(1,10))
    table([["Crawled","Discovered","Critical","High","Medium","Low / Review"],
       [coverage.get("pages_crawled",0),coverage.get("urls_discovered",0),bysev["critical"],bysev["high"],bysev["medium"],bysev["low"]+bysev["info"]]],
       widths=[82,82,77,65,75,page_width-381])
    mini("Organization and research context")
    txt("Inferred site type: "+intel.get("organization_type","Not established"))
    txt("AI research: "+intel.get("ai_research_status","not_run")+". Observed AI-search mentions/citations: NOT TESTED.")
    if r.get("pagespeed"):
        ps=r["pagespeed"];txt(f"Measured mobile PageSpeed performance: {ps.get('performance_score','unavailable')}/100. URL: {ps.get('source_url','')}.")
    else:txt("Mobile PageSpeed: Not measured or API unavailable.")
    mini("Top corrective priorities")
    if findings:
        for f in findings[:5]:li(f"{f['title']} — {f.get('affected_count',1)} affected URLs; {f.get('severity','review')} priority")
    else:txt("No prioritized issues were produced from the accessible sample.")

    head("02  Verified source-backed observations")
    strengths=intel.get("strengths",[])
    if strengths:
        for it in strengths[:7]:
            txt(it.get("point",""));story.append(link(it.get("url",""),it.get("url","")))
    else:txt("No individual strengths were established from the current sample.")
    mini("Information consistency candidates")
    conflicts=intel.get("research_findings",[])
    if conflicts:
        for f in conflicts[:8]:
            mini(f.get("title","Information discrepancy candidate"));txt(f.get("observation",""));
            txt("Review: "+f.get("recommendation","Verify authoritative records."))
            for src in f.get("sources",[]):
                txt('Observed quote: '+src.get("quote",""));story.append(link(src.get("url",""),src.get("url","")))
    else:txt("No source-quote-validated cross-page conflicts were generated. This does not establish that the site contains no contradictions.")

    head("03  SEO health and grouped technical findings")
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
    txt("Findings are grouped by root cause. Affected page counts show how widespread an observation is; optional canonical-tag absence is not treated as an automatic SEO failure.")

    head("04  Detailed findings and evidence")
    if not findings:txt("No source-linked findings were generated.")
    for f in findings:
        mini(f.get("title","Untitled finding"))
        txt(f"{f.get('category')}  |  {f.get('severity','review').upper()}  |  {f.get('affected_count',1)} affected URL(s)  |  Effort: {f.get('effort','Review')}  |  Confidence: {f.get('confidence','Unknown')}")
        txt("Evidence: "+f.get("evidence","None"))
        txt("Implication: "+f.get("why","Not given"))
        txt("Recommended action: "+f.get("recommendation","Not given"))
        txt("Suggested owner: "+f.get("owner","Site editor"))
        for u in f.get("affected_urls",[])[:4]:story.append(link(u))
        extra=f.get("affected_count",0)-min(4,len(f.get("affected_urls",[])))
        if extra>0:story.append(p(f"{extra} more affected URLs are in the structured JSON report.","SmallV2"))
        story.append(HRFlowable(width="100%",thickness=.4,color=BORDER))

    head("05  GEO and answer-readiness analysis")
    txt("GEO readiness here means sampled extractable answers, structure and identity information. It does not measure ChatGPT, Google AI Mode or Perplexity inclusion, citations, ranking or share of voice.")
    mini("Suggested real-world AI-answer tests (not executed)")
    questions=intel.get("geo_questions",[])
    if questions:
        for q in questions[:12]:li(q.get("question","") if isinstance(q,dict) else str(q))
    else:txt("AI benchmark questions were not generated.")

    head("06  Content coverage and proposed additions")
    txt("Not seen in sampled pages is NOT the same as missing from the website. Validate the existing URL inventory before commissioning new pages.")
    topics=intel.get("topic_coverage",[])
    if topics:table([["Topic cluster","Observed in sampled titles?"]]+[[q.get("topic",""),"Yes" if q.get("status")=="sampled" else "Not seen — review"] for q in topics],widths=[285,page_width-285])
    mini("Content opportunities")
    suggestions=intel.get("content_opportunities",[])
    for item in suggestions[:14]:
        mini(item.get("title","Content opportunity"));txt(item.get("why",""));txt("Suggested work: "+item.get("proposed_content",""))
        txt("Validation: "+item.get("status","Review"))
        for u in item.get("supporting_urls",[])[:2]:story.append(link(u))
    if not suggestions:txt("No specific content opportunities were generated from available sample evidence.")

    head("07  Search intent and keyword strategy")
    txt("The following are exploratory query themes, NOT measured keywords, search volumes, rankings or SEO traffic projections.")
    for cluster in intel.get("keyword_clusters",[])[:12]:
        mini(cluster.get("intent","Search topic"))
        for q in cluster.get("example_queries",[])[:4]:li(q)

    head("08  Structured data and entity strategy")
    observed=sorted({t for page in r.get("pages",[]) for t in (page.get("schema_types") or [])})
    txt("Detected JSON-LD types in sampled responses: "+(", ".join(observed) if observed else "None detected; rendered markup was not independently checked."))
    txt("Use a type that fits the organization. Government sites should assess GovernmentOrganization and relevant GovernmentOffice types; businesses should use appropriate Organization and genuine LocalBusiness subtypes only when applicable. Validate against visible facts and current search-provider policies.")

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

    head("11  KPI and verification plan")
    for v in ["Google Search Console: indexed pages, queries, organic clicks and impressions (requires authorized access).",
              "Site checks: resolved high-priority issues, content reviews completed, broken URL count and crawl coverage.",
              "GEO: run the same documented prompts across selected AI services and record actual citations, answers, date and model; not tested here.",
              "Governance: authoritative source identified for each time-sensitive fact, editorial owner and review date.",
              "PageSpeed: compare mobile LCP, INP, CLS after changes when valid measured data is available."]:
        li(v)

    head("12  Page inventory (sampled)")
    page_rows=[["URL / path","HTTP","Words","Page title"]]
    for page in r.get("pages",[]):
        path=urlparse(page.get("url","")).path or "/"
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
    for line in r.get("limitations",[]):li(line)
    txt("Method: robots-aware bounded public HTTP crawl, selected deterministic tests, optional PageSpeed, optional licensed search observations, and optional quotation-validated LLM research. Site-specific claims require manual confirmation for consequential decisions.")

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
