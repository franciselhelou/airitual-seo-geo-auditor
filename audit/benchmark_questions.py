"""Make valid, context-rich public-search benchmark questions from actual site evidence.

Never send the LLM's speculative GEO questions straight to paid providers.
Questions are derived from observed source pages, not invented website deficiencies.
"""
import re
from urllib.parse import urlparse

STATES={"ohio":"Ohio","oh":"Ohio","lebanon":"Lebanon","california":"California","new york":"New York","florida":"Florida","texas":"Texas"}
GOV_THEMES=(
    ("permits",("permit","building","inspection","license"),"Which official department handles building permits in {place}, and where are application instructions published?"),
    ("public services",("trash","waste","leaf","recycling","utilities","service"),"Where can residents of {place} find current public-works service information and collection schedules?"),
    ("government",("council","agenda","meeting","mayor","ordinance"),"Where are official city council meetings and agendas published for {place}?"),
    ("parks",("park","recreation","event","facility"),"Where can visitors find official parks and recreation information for {place}?"),
    ("contact",("directory","contact","city hall","office"),"Which official website lists city department contacts and office hours for {place}?"),
    ("planning",("zoning","planning","business","development"),"Where should a property owner find official zoning and planning requirements in {place}?"),
)

def _org(pages,website):
    home=next((p for p in pages if urlparse(p.get('url','')).path in ('','/')),pages[0] if pages else {})
    title=(home.get('title') or '').strip()
    heads=' '.join(home.get('h1') or [])
    sample=' '.join([(p.get('text') or '')[:1700] for p in pages[:8]])
    for val in (title,heads,sample[:300]):
        found=re.search(r'\bCity of\s+([A-Za-z][A-Za-z\s-]{1,40}?)(?=\s*[|,\-–]|\s+Official\b|\s+Ohio\b|\s*$)',val,re.I)
        if found:
            city=found.group(1).strip().title()
            if len(city.split())<=4:return city,True
    title=re.split(r'\s+[|–—-]\s+',title)[0].strip()
    return title[:65] or (urlparse(website).hostname or '').split('.')[0],False

def plan_questions(website,pages,site_type='',limit=4):
    good=[p for p in pages if p.get('status')==200 and not p.get('error')]
    if not good:return []
    name,gov_name=_org(good,website)
    gov=gov_name or str(site_type).startswith('Government')
    if gov:
        combined=' '.join((p.get('title','')+' '+p.get('text','')[:3500]) for p in good[:12]).lower()
        state=next((label for term,label in STATES.items() if re.search(r'\b'+re.escape(term)+r'\b',combined)),None)
        # A municipality with no grounded state/country can be ambiguous; don't
        # waste API calls on prompts that would require location clarification.
        if not state:return []
        place=name+', '+state
        selected=[]
        for topic,keywords,template in GOV_THEMES:
            evidence=next((p for p in good if any(k in (urlparse(p['url']).path+' '+p.get('title','')).lower() for k in keywords)),None)
            if evidence:
                selected.append({'question':template.format(place=place),'intent':topic,
                                 'segment':'local_discovery','context':place,'evidence_url':evidence['url']})
            if len(selected)>=limit:break
        return selected
    # For businesses, only benchmark company-related questions that can be tied
    # to observed pages. Avoid guessing geography or arbitrary competitor names.
    selected=[]
    for p in good:
        title=(p.get('title') or '').strip()
        if title and p.get('word_count',0)>80 and p.get('url') and len(selected)<limit:
            path=urlparse(p['url']).path.lower()
            if any(t in path+' '+title.lower() for t in ('service','product','solution','about','contact','pricing')):
                subject=re.sub(r'\s*[|–—]\s*.*$','',title)[:70]
                q=f'What information does {name} publish about {subject}, and where is its authoritative source?'
                selected.append({'question':q,'intent':'business_topic','segment':'branded',
                                 'context':name,'evidence_url':p['url']})
    return selected
