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
    mini("Decision metrics — public sample only")
    detail=r.get('score_details') or {}
    seo=detail.get('seo') or {};geo=detail.get('geo') or {}
    actions=r.get('action_summary') or {}
    table([["Indicator", "Result", "Interpretation"],
        ["SEO audit score",fmt(seo.get('score')),"Weighted observed SEO checks on sampled pages"],
        ["AI citation benchmark",fmt(geo.get('score')),
         str(geo.get('cited',0))+"/"+str(geo.get('valid_tests',0))+" valid API tests cited the domain"],
        ["Confirmed urgent issues",str(actions.get('urgent_verified',0)),"High-impact, observed defects only"],
        ["High-priority verification",str(actions.get('high_priority_to_verify',0)),"Not yet proven problems"],
        ["Research opportunities",str(actions.get('content_proposals',0)),"Source-quoted hypotheses to validate"]],
        widths=[143,93,page_width-236])
    txt(f"Scope: {seo.get('pages',0)} HTML pages sampled; "
        f"SEO measured weight: {seo.get('weight_covered',0)} of 100. "
        f"AI calls attempted: {geo.get('attempts',0)}; valid citation tests: {geo.get('valid_tests',0)}. "
        "These are transparent audit measures, not verified whole-site rankings or search traffic.")
    if seo.get('breakdown'):
        mini('SEO scoring details')
        table([["Observed check","Pass rate","Sample"]]+[
            [i['check'].replace('_',' ').title(),str(i['result_percent'])+'%',str(i['samples'])]
            for i in seo['breakdown']],widths=[272,105,page_width-377])
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
            if item.get('status')!='completed' or not item.get('valid_answer'):continue
            mini(item.get('provider','')+" — "+item.get('question','')[:100])
            txt('Domain cited: '+('Yes' if item.get('target_cited') else 'No')+'. Answer excerpt: '+item.get('answer','')[:340])
            for cite in item.get('citations',[])[:4]:story.append(link(cite.get('url','')))
    else:txt("No public AI API benchmark results are available for this audit.")
    mini("Source-linked public benchmark prompts")
    questions=intel.get("geo_questions",[])
    if questions:
        for q in questions[:8]:
            li(q.get("question","") if isinstance(q,dict) else str(q))
    else:txt("AI benchmark questions were not generated.")

    head("06  Prioritized content opportunities")
    txt("Recommendations below are hypotheses supported by source excerpts. Check related existing pages before commissioning content.")
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

    head("10  Prioritized 90-day work plan")
    for phase in r.get("roadmap",[]):
        mini(phase.get("period",""))
        for task in phase.get("tasks",[])[:12]:li(task)

    head("11  Audit scope and supporting records")
    txt("The downloadable structured JSON result retains each sampled page, excluded document, provider response, citation and source evidence. Page inventories and optional profiles are not repeated as client-facing report sections.")
    quality=r.get('quality_gate') or {}
    txt('Evidence quality gate: '+str(quality.get('status','not_run'))+'. Public-only bounded crawl; independently verify high-impact corrections.')
    speed_results=r.get('pagespeed_results') or []
    if speed_results:
        mini('Public mobile PageSpeed tests')
        for i in speed_results[:4]:
            txt(f"{i.get('tested_url','')} — mobile performance: {i.get('performance_score','unavailable')}/100")
    for line in r.get('limitations',[])[:3]:txt(line)

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
