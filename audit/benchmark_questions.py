"""Evidence-grounded, industry-agnostic questions for public AI discovery benchmarks.

The research model proposes organization-specific *and* competitive queries. Its
proposals must be supported by exact quotations in a fetched document. All
questions go to third-party search providers as normal end-user questions; we
never tell a provider to cite the audited site.
"""
import re
from urllib.parse import urlparse

COUNTRIES = ('Guatemala','Lebanon','United States','United Kingdom','Canada','Mexico','Ohio','California','Texas','Florida','New York','Germany','France','Italy','Brazil','Colombia','India','Australia','UAE','Dubai')
GOV_TASKS = (
    ('permits', ('permit','licensing','application'), 'Where can residents apply for permits or licenses in {market}?'),
    ('recreation', ('park','recreation','facility','event'), 'What parks and recreation programs are available in {market}?'),
    ('waste', ('trash','rubbish','garbage','waste','recycling','leaf'), 'How do residents find waste collection schedules in {market}?'),
    ('government', ('council','agenda','meeting','mayor'), 'How can residents find council meeting agendas in {market}?'),
    ('contact', ('contact','directory','phone','department'), 'Where can residents find government department contacts in {market}?'),
    ('zoning', ('zoning','planning','development'), 'Where can property owners find zoning requirements in {market}?'),
)
COMMERCIAL_TOPICS = (
    ('tshirt', ('t-shirt','tshirt','tee shirt','tee-shirt','shirts','apparel','garments','textiles'), 'Which companies manufacture custom T-shirts in {market}?'),
    ('clothes',('clothing','garment','apparel','textile','fashion'), 'What clothing manufacturers operate in {market}?'),
    ('consulting',('consulting','advisory','consultancy'), 'Which consulting firms serve customers in {market}?'),
    ('software',('software','saas','application development','web development'), 'Which software development companies serve businesses in {market}?'),
    ('cybersecurity',('cybersecurity','managed security','penetration testing'), 'Which cybersecurity service providers operate in {market}?'),
    ('hospitality',('hotel','resort','accommodation','rooms'), 'Which hotels serve travelers in {market}?'),
    ('agriculture',('farm','agriculture','produce','crop'), 'Which agricultural producers or suppliers operate in {market}?'),
)


def _clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _market_from_sources(pages, site_type):
    # The seed website's home title or About page is preferred; avoid choosing a
    # random city/country mentioned in an unrelated footer or quoted article.
    source=next((p for p in pages if urlparse(p.get('url','')).path in ('','/')), pages[0] if pages else {})
    about=next((p for p in pages if '/about' in urlparse(p.get('url','')).path.casefold()), {})
    lead=' '.join((p.get('title','')+' '+' '.join(p.get('h1') or [])+' '+p.get('text','')[:1400]) for p in (source,about))
    city=re.search(r'\bCity of\s+([A-Za-z][A-Za-z\s-]{1,30}?)(?=\s*[|,\-–]|\s+(?:Ohio|OH|Official)\b|\s*$)', lead,re.I)
    if city:
        name=city.group(1).strip(' ,|')
        name=re.sub(r',?\s+(OH|Ohio)$','',name,flags=re.I)
        return (name+', Ohio' if re.search(r'\b(?:Ohio|OH)\b',lead,re.I) else name), _clean(name)
    for country in COUNTRIES:
        if re.search(r'\b'+re.escape(country)+r'\b',lead,re.I):
            name=re.split(r'\s+[|–—-]\s+',source.get('title') or '')[0].strip()
            return country,name
    return '',_clean(re.split(r'\s+[|–—-]\s+',source.get('title') or '')[0])


def _supported(candidate, pages):
    url=candidate.get('evidence_url','')
    quote=_clean(candidate.get('evidence_quote',''))
    page=next((p for p in pages if p.get('url')==url),None)
    if not page or len(quote)<12:return False
    text=_clean(page.get('text',''))
    return quote.casefold() in text.casefold()


def _valid_candidate(candidate, pages, market, name):
    if not isinstance(candidate,dict) or not _supported(candidate,pages):return None
    q=_clean(candidate.get('question',''))
    if not (15 <= len(q) <= 230 and q.endswith('?')):return None
    segment=str(candidate.get('segment','')).lower()
    if segment not in ('branded','discovery'):return None
    if segment=='discovery':
        # Buyer-style discovery questions should name a grounded market, but
        # should NOT give the model the brand name, website, or desired answer.
        if not market or market.casefold() not in q.casefold():return None
        if name and len(name)>3 and name.casefold() in q.casefold():return None
    elif name and name.casefold() not in q.casefold():return None
    if re.search(r'\b(?:cite|quote|mention)\s+(?:the\s+)?(?:website|domain|brand)\b',q,re.I):return None
    return {'question':q,'segment':segment,'intent':_clean(candidate.get('intent',''))[:100],
            'context':market if segment=='discovery' else name,
            'evidence_url':candidate['evidence_url'], 'evidence_quote':candidate['evidence_quote'],
            'method':'source_verified_dynamic_llm'}


def plan_questions(website,pages,site_type='',suggestions=None,limit=8):
    """Source-aware LLM questions with conservative content-based fallback.

    None of the fallbacks claims that the target is 'best'; those answers must
    emerge independently from providers. An unknown market is never guessed.
    """
    good=[p for p in pages if p.get('status')==200 and not p.get('error') and p.get('text')]
    if not good:return []
    market,name=_market_from_sources(good,site_type)
    approved=[];seen=set()
    for suggestion in (suggestions or []):
        q=_valid_candidate(suggestion,good,market,name)
        if q and q['question'].casefold() not in seen:
            seen.add(q['question'].casefold());approved.append(q)
        if len(approved)>=limit:break
    if len(approved)>=limit:return approved[:limit]
    # If model suggestions were rejected, derive *only* tasks directly evidenced
    # by page titles/paths, avoiding speculative cross-industry defaults.
    gov=str(site_type).startswith('Government') or bool(re.search(r'\bCity of\b',name+' '+(good[0].get('title') or ''),re.I))
    topics=GOV_TASKS if gov else COMMERCIAL_TOPICS
    if not market:return approved[:limit]
    for topic,terms,template in topics:
        page=next((p for p in good if any(t in (p.get('title','')+' '+urlparse(p['url']).path+' '+p.get('text','')[:500]).casefold() for t in terms)),None)
        if not page:continue
        q=template.format(market=market)
        if q.casefold() in seen:continue
        # Evidence from actual fetched page. A title isn't necessarily contained
        # in extracted text, so choose a substantive text snippet for provenance.
        quote=_clean(page.get('text',''))[:180]
        if len(quote)<12:continue
        approved.append({'question':q,'intent':topic,'segment':'discovery','context':market,
                         'evidence_url':page['url'],'evidence_quote':quote,'method':'observed_content_fallback'})
        seen.add(q.casefold())
        if len(approved)>=limit:break
    return approved[:limit]
