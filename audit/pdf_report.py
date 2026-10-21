"""Professional multipage PDF from the same JSON displayed by the frontend."""
from collections import Counter
from html import escape
from urllib.parse import urlparse
from io import BytesIO
from reportlab.platypus import (SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether,PageBreak,HRFlowable)
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4

NAVY=colors.HexColor("#14243b");RED=colors.HexColor("#df4552")
LIGHT=colors.HexColor("#f2f5fa");MUTED=colors.HexColor("#5c6e85")
SEVERITY={"critical":"#a32f42","high":"#b66c24","medium":"#a08a32","low":"#3574ad","info":"#25836a"}


def plain(value):
    return escape(str(value if value is not None else ""))


def create_pdf(result):
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=47,rightMargin=47,topMargin=62,bottomMargin=54,title="AI Ritual SEO & GEO Audit",author="AI Ritual")
    sty=getSampleStyleSheet()
    sty.add(ParagraphStyle(name="CoverLabelCustom",fontName="Helvetica-Bold",fontSize=11,textColor=RED,spaceAfter=18,leading=15))
    sty.add(ParagraphStyle(name="CoverTitleCustom",fontName="Helvetica-Bold",fontSize=29,textColor=NAVY,leading=35,spaceAfter=18))
    sty.add(ParagraphStyle(name="BigSubCustom",fontName="Helvetica",fontSize=12,textColor=MUTED,leading=19,spaceAfter=12))
    sty.add(ParagraphStyle(name="SectionCustom",fontName="Helvetica-Bold",fontSize=18,textColor=NAVY,spaceBefore=21,spaceAfter=13,keepWithNext=True))
    sty.add(ParagraphStyle(name="MiniCustom",fontName="Helvetica-Bold",fontSize=12,textColor=NAVY,spaceBefore=11,spaceAfter=7,keepWithNext=True))
    sty.add(ParagraphStyle(name="BodyCustom",fontName="Helvetica",fontSize=9.4,textColor=NAVY,leading=14,spaceAfter=8,wordWrap="CJK"))
    sty.add(ParagraphStyle(name="TinyCustom",fontName="Helvetica",fontSize=8,textColor=MUTED,leading=11,spaceAfter=5,wordWrap="CJK"))
    sty.add(ParagraphStyle(name="TableCustom",fontName="Helvetica",fontSize=8,textColor=NAVY,leading=11,wordWrap="CJK"))
    sty.add(ParagraphStyle(name="WhiteTableCustom",fontName="Helvetica-Bold",fontSize=8,textColor=colors.white,leading=11))
    story=[]
    def p(v,style="BodyCustom"):return Paragraph(plain(v).replace("\n","<br/>"),sty[style])
    def tlabel(v):return Paragraph(plain(v),sty["TableCustom"])
    def linktext(v):
        """Create a clickable link only for HTTP(S) evidence URLs."""
        address=str(v or "")
        if urlparse(address).scheme not in ("http","https"):
            return plain(address)
        quoted=escape(address,quote=True)
        return f'<link href="{quoted}" color="#bf4255">{plain(address)}</link>'
    def heading(v):story.append(p(v,"SectionCustom"))
    story.extend([Spacer(1,60),p("AI RITUAL  /  INTELLIGENCE REPORT","CoverLabelCustom"),p("SEO & GEO\nWebsite Audit","CoverTitleCustom"),p(result.get("website",""),"BigSubCustom"),Spacer(1,17),HRFlowable(width="100%",thickness=1,color=RED),Spacer(1,18),p("Automated public-data review of website health, content quality, AI-search readiness, and actionable improvements.","BigSubCustom"),Spacer(1,22),p("Audit reference: "+result.get("audit_id","local"),"TinyCustom"),p("Completed: "+result.get("completed_at",""),"TinyCustom"),p("Report contains source-linked findings, scores, limitations, and a phased action plan.","TinyCustom"),PageBreak()])
    heading("Executive summary")
    story.append(p(result.get("summary","No summary provided.")))
    scores=result.get("scores",{})
    def fmt(v):return "Not measured" if v is None else str(round(v))+"%"
    row=[[Paragraph("DIMENSION",sty["WhiteTableCustom"]),Paragraph("SCORE",sty["WhiteTableCustom"])] ]
    for name,key in (("Overall health","overall"),("Technical SEO","technical"),("Content quality","content"),("GEO readiness","geo")):
        row.append([tlabel(name),tlabel(fmt(scores.get(key)))])
    tb=Table(row,colWidths=[340,145],repeatRows=1,hAlign="LEFT")
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,LIGHT]),("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10)]))
    story.extend([tb,Spacer(1,14)])
    cnt=Counter(f.get("severity") for f in result.get("findings",[]));coverage=result.get("coverage",{})
    story.append(p(f"Crawl coverage: {coverage.get('pages_crawled',0)} pages crawled, {coverage.get('urls_discovered',0)} URLs discovered, {coverage.get('pages_failed',0)} inaccessible pages. Issues: {cnt['critical']} critical, {cnt['high']} high, {cnt['medium']} medium, {cnt['low']} low, {cnt['info']} opportunities.","TinyCustom"))
    heading("Issue distribution")
    bycat=Counter(f.get("category","Other") for f in result.get("findings",[]));maximum=max(bycat.values(),default=1)
    bars=[]
    for cat,n in sorted(bycat.items(),key=lambda kv:-kv[1]):
        bars.append([tlabel(cat),tlabel(str(n)),Table([[""]],colWidths=[max(6,160*n/maximum)],rowHeights=[9],style=TableStyle([("BACKGROUND",(0,0),(-1,-1),RED)]))])
    if bars:
        bt=Table(bars,colWidths=[195,30,230],hAlign="LEFT")
        bt.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BOTTOMPADDING",(0,0),(-1,-1),9)]));story.append(bt)
    else:story.append(p("No findings were produced."))
    heading("Detailed findings")
    findings=result.get("findings",[])
    if not findings:story.append(p("No findings generated from available sources."))
    for item in findings:
        title=f"{item.get('id','')}  {item.get('title','')}"
        block=[p(title,"MiniCustom"),p(f"{item.get('severity','').upper()}  ·  {item.get('category','')}  ·  Estimated effort: {item.get('effort','not rated')}","TinyCustom")]
        for label,key in (("Affected URL","url"),("Evidence","evidence"),("Why it matters","why"),("Recommended correction","recommendation")):
            evidence=linktext(item.get(key,"")) if key=="url" else plain(item.get(key,""))
            block.append(Paragraph(f'<b>{plain(label)}:</b> {evidence}',sty["BodyCustom"]))
        block.append(Spacer(1,8))
        # Avoid huge KeepTogether elements that could overflow a page.
        story.extend(block)
        story.append(HRFlowable(width="100%",thickness=.4,color=colors.HexColor("#e2e8ef")))
    heading("Implementation roadmap")
    for group in result.get("roadmap",[]):
        story.append(p(group.get("period",""),"MiniCustom"))
        for task in group.get("tasks",[]):story.append(p("• "+task))
    heading("Page inventory")
    allpages=result.get("pages",[])
    if allpages:
        table=[[Paragraph("URL",sty["WhiteTableCustom"]),Paragraph("HTTP",sty["WhiteTableCustom"]),Paragraph("WORDS",sty["WhiteTableCustom"]),Paragraph("TITLE",sty["WhiteTableCustom"])]]
        for page in allpages:
            url=page.get("url","")
            table.append([Paragraph(linktext(url[:110]),sty["TableCustom"]),tlabel(str(page.get("status",""))),tlabel(str(page.get("word_count",0))),tlabel(str(page.get("title",""))[:110])])
        grid=Table(table,colWidths=[214,42,44,185],repeatRows=1,hAlign="LEFT")
        grid.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,LIGHT]),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]));story.append(grid)
    else:story.append(p("No public HTML pages collected."))
    heading("External business profiles")
    if result.get("external_profiles"):
        for f in result["external_profiles"]:story.append(p(f"{f.get('url','')} — {f.get('access','not tested')}. {f.get('note','')}"))
    else:story.append(p("No supplementary profiles supplied."))
    heading("Methodology and limitations")
    for l in result.get("limitations",[]):story.append(p("• "+l))
    def page(canvas,doc):
        canvas.saveState();w,h=A4
        canvas.setStrokeColor(colors.HexColor("#e3e9f0"));canvas.line(47,h-45,w-47,h-45)
        canvas.setFillColor(RED);canvas.setFont("Helvetica-Bold",9);canvas.drawString(47,h-33,"AI RITUAL  /  SEO & GEO INTELLIGENCE")
        canvas.setStrokeColor(colors.HexColor("#e3e9f0"));canvas.line(47,42,w-47,42)
        canvas.setFont("Helvetica",8);canvas.setFillColor(MUTED);canvas.drawString(47,28,"airitual.com  •  Evidence-based public website audit")
        canvas.drawRightString(w-47,28,f"Page {doc.page}");canvas.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return buf.getvalue()
