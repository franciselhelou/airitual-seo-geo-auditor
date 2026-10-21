"""Respectful HTML crawl with bounded scope and plain-text extraction."""
import json
import re
from collections import deque
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree
from bs4 import BeautifulSoup
from .net import fetch, checked_url, UnsafeURL, AGENT

MAX_PAGES = 32
MAX_DISCOVERED = 240
MAX_EXTERNAL = 8


def norm(url):
    u=urlparse(urldefrag(url)[0]); return u._replace(query="", fragment="").geturl().rstrip("/") or u.geturl()


def hostname_allowed(target, base):
    a=urlparse(target); b=urlparse(base)
    ah=(a.hostname or "").lower().removeprefix("www.")
    bh=(b.hostname or "").lower().removeprefix("www.")
    return a.scheme in ("https", "http") and ah==bh and a.port in (None,80,443)


def extract(html, url, status):
    soup=BeautifulSoup(html,"lxml")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    desc=soup.find("meta",attrs={"name":re.compile("^description$",re.I)})
    desc=desc.get("content","").strip() if desc else ""
    robots=soup.find("meta",attrs={"name":re.compile("^robots$",re.I)})
    robots=robots.get("content","").lower() if robots else ""
    can=soup.find("link",attrs={"rel":lambda x:x and "canonical" in x})
    canonical=urljoin(url,can.get("href","")) if can else ""
    headings=[h.get_text(" ",strip=True)[:180] for h in soup.find_all("h1")]
    h2=[h.get_text(" ",strip=True)[:180] for h in soup.find_all(["h2","h3"])][:30]
    images=soup.find_all("img")
    no_alt=sum(1 for i in images if not i.get("alt","").strip())
    links=[]
    for a in soup.find_all("a",href=True):
        h=a["href"].strip()
        if not h or h.startswith(("#","mailto:","tel:","javascript:")):
            continue
        target=norm(urljoin(url,h))
        if urlparse(target).scheme in ("http","https"):
            links.append(target)
    types=[]; same_as=[]
    for s in soup.find_all("script",type="application/ld+json"):
        try:
            obj=json.loads(s.get_text()); objs=obj if isinstance(obj,list) else [obj]
            while objs:
                item=objs.pop()
                if isinstance(item,list):objs.extend(item);continue
                if isinstance(item,dict):
                    if "@graph" in item:objs.append(item["@graph"])
                    typ=item.get("@type")
                    if isinstance(typ,list):types.extend([str(v) for v in typ])
                    elif typ:types.append(str(typ))
                    refs=item.get("sameAs",[])
                    same_as.extend(refs if isinstance(refs,list) else [refs])
        except (ValueError,TypeError):pass
    for el in soup(["script","style","noscript","nav","footer","header","svg"]):el.decompose()
    text=" ".join(soup.stripped_strings)
    words=re.findall(r"\b[\w'-]+\b",text)
    return {"url":url,"status":status,"title":title[:190],"description":desc[:500],"h1":headings,"headings":h2,"word_count":len(words),"images":len(images),"images_missing_alt":no_alt,"canonical":canonical,"robots":robots,"schema_types":sorted(set(types)),"same_as":[str(s) for s in same_as][:20],"links":list(dict.fromkeys(links))[:400],"text":text[:18000]}


def get_robots(root, warnings):
    url=urljoin(root,"/robots.txt")
    try:
        r=fetch(url,max_bytes=200_000)
        if r["status"]==404:return None,"missing"
        if r["status"] in (401,403):warnings.append("The website denies access to robots.txt; crawling was conservatively stopped.");return None,"restricted"
        if r["status"]!=200: warnings.append(f"Could not verify robots.txt (HTTP {r['status']}); crawling was conservatively stopped.");return None,"restricted"
        parser=RobotFileParser();parser.parse(r["text"].splitlines());return parser,"present"
    except (UnsafeURL, Exception) as exc:
        warnings.append(f"robots.txt request failed: {str(exc)[:100]}; crawling was conservatively stopped.")
        return None,"restricted"


def discover_sitemap(root,allowed,warnings):
    for path in ("/sitemap.xml","/sitemap_index.xml"):
        try:
            response=fetch(urljoin(root,path),max_bytes=650_000)
            if response["status"]!=200 or "xml" not in response["type"]:continue
            xml=ElementTree.fromstring(response["text"])
            urls=[]
            for node in xml.iter():
                if node.tag.lower().endswith("loc") and node.text:
                    u=norm(node.text.strip())
                    if allowed(u) and not u.lower().endswith((".pdf",".xml",".png",".jpg")):urls.append(u)
            return list(dict.fromkeys(urls))[:120],"present"
        except (Exception,) as e:
            warnings.append("Sitemap parsing skipped for a candidate: "+str(e)[:100])
    return [],"not_found_or_unavailable"


def crawl_site(website,progress=lambda x:None,max_pages=MAX_PAGES):
    warnings=[];checked_url(website)
    root=website
    rp,robots_status=get_robots(root,warnings)
    if robots_status=="restricted":
        return {"pages":[],"warnings":warnings,"urls_discovered":0,"pages_failed":0,"robots_status":robots_status,"sitemap_status":"not_checked"}
    def allowed(url):return hostname_allowed(url,root) and (rp is None or rp.can_fetch(AGENT,url))
    if not allowed(root):
        warnings.append("The site's robots.txt disallows the submitted homepage for the audit crawler.")
        return {"pages":[],"warnings":warnings,"urls_discovered":1,"pages_failed":0,"robots_status":"disallowed","sitemap_status":"not_checked"}
    sitemap_urls,sitemap_status=discover_sitemap(root,allowed,warnings)
    queue=deque([norm(root)]+sitemap_urls[:70]); discovered=set(queue); processed=set();pages=[];failed=0
    while queue and len(pages)<max_pages:
        url=queue.popleft()
        if url in processed:continue
        processed.add(url)
        if not allowed(url):continue
        if re.search(r"\.(?:pdf|docx?|xlsx?|png|jpg|jpeg|gif|svg|zip)(?:$|\?)",url,re.I):continue
        progress(f"Crawling page {len(pages)+1}/{max_pages}: {urlparse(url).path or '/'}")
        try:
            response=fetch(url)
            target=response["url"]
            if not hostname_allowed(target,root):
                warnings.append(f"Redirected outside submitted site: {url}");failed+=1;continue
            if response["status"]>=400 or response["error"] or "html" not in response["type"]:
                failed+=1
                pages.append({"url":url,"status":response["status"],"error":response["error"] or f"HTTP {response['status']}","title":"","description":"","h1":[],"headings":[],"word_count":0,"images":0,"images_missing_alt":0,"canonical":"","robots":"","schema_types":[],"same_as":[],"links":[],"text":""})
                continue
            page=extract(response["text"],target,response["status"])
            if "noindex" in page["robots"]:warnings.append(f"Meta noindex on {target}")
            pages.append(page)
            for link in page["links"]:
                if len(discovered)>=MAX_DISCOVERED:break
                if link not in discovered and allowed(link):
                    discovered.add(link);queue.append(link)
        except Exception as exc:
            failed+=1;warnings.append(f"Unable to crawl {url}: {str(exc)[:135]}")
    return {"pages":pages,"warnings":warnings[:40],"urls_discovered":len(discovered),"pages_failed":failed,"robots_status":robots_status,"sitemap_status":sitemap_status}


def inspect_external(urls,progress=lambda x:None):
    output=[]
    for i,url in enumerate(urls[:MAX_EXTERNAL]):
        progress(f"Checking external profile {i+1}/{len(urls)}")
        record={"url":url,"access":"unavailable","note":"Could not verify this profile; no information was assumed."}
        try:
            res=fetch(url,max_bytes=250_000,timeout=(5,8))
            record["access"]="accessible" if res["status"]==200 else f"HTTP {res['status']}"
            record["note"]="Public response inspected; a successful response does not verify business ownership." if res["status"]==200 else "Profile content was not accessible for reliable analysis."
        except Exception as exc:
            record["note"]="Could not access public profile: "+str(exc)[:110]
        output.append(record)
    return output
