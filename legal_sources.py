"""LexiCore Official JDIH Federation.

JDIH and other first-party institutional repositories are authoritative online
verification targets. JDIHN is discovery/directory infrastructure only and is
never counted as a primary legal source. Network reachability is recorded
separately from legal status and professional verification.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import re
import ssl
import time
import threading

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import certifi
except Exception:  # optional at import time; requirements installs it for production
    certifi = None

from version import LEXICORE_VERSION

UA = f"LexiCore/{LEXICORE_VERSION} (+case-scoped official legal retrieval)"

# v1.3.13.11.1 — small in-process TTL caches for official-source I/O.
# They only cache transport/discovery results; legal status, tempus and case nexus
# are still recomputed by the existing verifier for every analysis.
_CACHE_LOCK = threading.RLock()
_CACHE = {"health": {}, "search": {}, "fetch": {}, "fulltext": {}}
HEALTH_CACHE_TTL = 180
SEARCH_CACHE_TTL = 300
FETCH_CACHE_TTL = 600
FULLTEXT_CACHE_TTL = 600

def _cache_get(bucket: str, key, ttl: int):
    now=time.monotonic()
    with _CACHE_LOCK:
        row=_CACHE.get(bucket,{}).get(key)
        if not row: return None
        ts,value=row
        if now-ts > ttl:
            _CACHE[bucket].pop(key,None); return None
        # Callers never mutate body bytes, but may enrich dicts. Return a shallow copy.
        return dict(value) if isinstance(value,dict) else value

def _cache_put(bucket: str, key, value):
    with _CACHE_LOCK:
        _CACHE.setdefault(bucket,{})[key]=(time.monotonic(), dict(value) if isinstance(value,dict) else value)

DEFAULT_TIMEOUT = 5
MAX_BODY = 1_500_000

# Primary sources are first-party JDIH or official institutional repositories.
# JDIHN is retained only as a directory/discovery helper and is excluded from
# authoritative-source coverage calculations.
OFFICIAL_SOURCES = [
    {
        "id": "jdihn_directory", "name": "JDIHN — Directory Anggota JDIH",
        "base_url": "https://jdihn.go.id/", "role": "directory_only",
        "source_kind": "directory", "authoritative": False,
        "search_template": "https://jdihn.go.id/pencarian?instansi=&jenis=&keyword={q}&nomor=&status=&tahun=",
        "official": True,
    },
    {
        "id": "bpk", "name": "Database Peraturan / JDIH BPK",
        "base_url": "https://peraturan.bpk.go.id/", "role": "regulation_database",
        "source_kind": "jdih", "authoritative": True,
        "search_template": "https://peraturan.bpk.go.id/Search?keywords={q}", "official": True,
    },
    {
        "id": "ma", "name": "JDIH Mahkamah Agung RI",
        "base_url": "https://jdih.mahkamahagung.go.id/", "role": "judicial_regulation",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "mk", "name": "Mahkamah Konstitusi RI — Putusan",
        "base_url": "https://www.mkri.id/perkara/persidangan/putusan", "role": "constitutional_decisions",
        "source_kind": "judicial_repository", "authoritative": True,
        "search_template": "https://www.mkri.id/perkara/persidangan/putusan?search={q}", "official": True,
    },
    {
        "id": "jdih_mk", "name": "JDIH Mahkamah Konstitusi",
        "base_url": "https://jdih.mkri.id/", "role": "constitutional_legal_documents",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "setneg", "name": "JDIH Kementerian Sekretariat Negara",
        "base_url": "https://jdih.setneg.go.id/", "role": "state_secretariat",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "dpr", "name": "JDIH DPR RI",
        "base_url": "https://jdih.dpr.go.id/", "role": "legislative",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "kemenkum", "name": "JDIH Kementerian Hukum",
        "base_url": "https://jdih.kemenkum.go.id/", "role": "legal_ministry",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "ojk", "name": "JDIH / Regulasi Otoritas Jasa Keuangan",
        "base_url": "https://jdih.ojk.go.id/", "role": "financial_services_regulation",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "kemnaker", "name": "JDIH Kementerian Ketenagakerjaan",
        "base_url": "https://jdih.kemnaker.go.id/", "role": "employment_regulation",
        "source_kind": "jdih", "authoritative": True,
        "search_template": "https://jdih.kemnaker.go.id/peraturan?semuajudul={q}", "official": True,
    },
    {
        "id": "kemendagri", "name": "JDIH Kementerian Dalam Negeri",
        "base_url": "https://jdih.kemendagri.go.id/", "role": "regional_government_regulations",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "atr_bpn", "name": "JDIH Kementerian ATR/BPN",
        "base_url": "https://jdih.atrbpn.go.id/", "role": "land_and_spatial_regulation",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "komdigi", "name": "JDIH Kementerian Komunikasi dan Digital",
        "base_url": "https://jdih.komdigi.go.id/", "role": "digital_and_communications_regulation",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "kemenkeu", "name": "JDIH Kementerian Keuangan",
        "base_url": "https://jdih.kemenkeu.go.id/", "role": "state_finance_regulation",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
    {
        "id": "kemenag", "name": "JDIH Kementerian Agama",
        "base_url": "https://jdih.kemenag.go.id/", "role": "religious_affairs_regulation",
        "source_kind": "jdih", "authoritative": True, "search_template": None, "official": True,
    },
]


ALLOWED_OFFICIAL_HOST_SUFFIXES = (
    "jdihn.go.id", "peraturan.bpk.go.id", "bpk.go.id", "mahkamahagung.go.id",
    "mkri.id", "setneg.go.id", "dpr.go.id", "kemenkum.go.id", "kemendagri.go.id",
    "bphn.go.id", "djpp.kemenkum.go.id", "ojk.go.id", "kemnaker.go.id", "go.id",
)

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="a":
            self._href=dict(attrs).get("href"); self._text=[]
    def handle_data(self, data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self._href is not None:
            text=re.sub(r"\s+"," "," ".join(self._text)).strip()
            if self._href: self.links.append((self._href,text))
            self._href=None; self._text=[]


def _request(url: str, timeout: int=DEFAULT_TIMEOUT):
    req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,application/pdf;q=0.8,*/*;q=0.5"})
    ctx=ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()
    with urlopen(req,timeout=timeout,context=ctx) as r:
        body=r.read(MAX_BODY)
        return r.status, r.geturl(), r.headers.get("Content-Type",""), body


def _official_url(url: str) -> bool:
    try:
        host=(urlparse(url).hostname or "").lower()
        return host.endswith(ALLOWED_OFFICIAL_HOST_SUFFIXES)
    except Exception:
        return False


def _text_score(text: str, query: str) -> int:
    t=(text or "").lower(); words=[w for w in re.findall(r"[a-zA-Z0-9]+",query.lower()) if len(w)>2]
    return sum(2 if w in t else 0 for w in words) + (5 if query.lower() in t else 0)


def _extract_results(html: bytes, base_url: str, query: str, limit: int=8):
    try: s=html.decode("utf-8","ignore")
    except Exception: return []
    p=AnchorParser()
    try: p.feed(s)
    except Exception: return []
    out=[]; seen=set()
    for href,text in p.links:
        url=urljoin(base_url,href)
        if not url.startswith("http") or not _official_url(url): continue
        if url in seen: continue
        score=_text_score(text,query)
        # Keep document-looking links even when title is short.
        path=urlparse(url).path.lower()
        documentish=any(k in path for k in ("detail","dokumen","putusan","peraturan","produk-hukum","files","download")) or path.endswith(".pdf")
        if score<=0 and not documentish: continue
        seen.add(url)
        out.append({"title": text[:300] or url, "url": url, "score": score})
    out.sort(key=lambda x:(x["score"],len(x["title"])),reverse=True)
    return out[:limit]


def _connectivity_status(error=None, http_status=None):
    if http_status is not None and 200 <= http_status < 400:
        return "REACHABLE"
    if http_status == 403:
        return "AUTOMATION_BLOCKED_403"
    text=str(error or "").lower()
    if "certificate_verify_failed" in text or "certificate verify failed" in text:
        return "SSL_VALIDATION_ERROR"
    if "getaddrinfo failed" in text or "name or service not known" in text:
        return "DNS_RESOLUTION_ERROR"
    if "timed out" in text or "timeout" in text:
        return "TIMEOUT"
    if http_status is not None:
        return "HTTP_ERROR"
    return "UNREACHABLE"


def check_source(source: dict) -> dict:
    started=datetime.now(timezone.utc)
    try:
        status, final_url, content_type, body=_request(source["base_url"],timeout=4)
        reachable=200 <= status < 400
        return {**source,"reachable":reachable,"connectivity_status":_connectivity_status(http_status=status),
                "http_status":status,"final_url":final_url,"content_type":content_type,
                "checked_at":started.isoformat(),"error":None}
    except HTTPError as e:
        return {**source,"reachable":False,"connectivity_status":_connectivity_status(e,http_status=e.code),
                "http_status":e.code,"final_url":source["base_url"],"content_type":"",
                "checked_at":started.isoformat(),"error":str(e)[:240]}
    except Exception as e:
        return {**source,"reachable":False,"connectivity_status":_connectivity_status(e),
                "http_status":None,"final_url":source["base_url"],"content_type":"",
                "checked_at":started.isoformat(),"error":str(e)[:240]}


def source_health(max_workers: int=4, cache_only: bool=False):
    cache_key=("all", int(max_workers or 8))
    cached=_cache_get("health",cache_key,HEALTH_CACHE_TTL)
    if cached is not None:
        return list(cached.get("results") or [])
    if cache_only:
        return []
    results=[]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs={ex.submit(check_source,s):s for s in OFFICIAL_SOURCES}
        for f in as_completed(futs):
            try: results.append(f.result())
            except Exception as e: results.append({**futs[f],"reachable":False,"error":str(e)[:240]})
    order={s["id"]:i for i,s in enumerate(OFFICIAL_SOURCES)}
    results.sort(key=lambda x:order.get(x["id"],999))
    _cache_put("health",cache_key,{"results":results})
    return results


def search_source(source: dict, query: str, limit: int=8):
    cache_key=(source.get("id"), re.sub(r"\s+"," ",query or "").strip().lower(), int(limit or 8))
    cached=_cache_get("search",cache_key,SEARCH_CACHE_TTL)
    if cached is not None:
        return cached
    tpl=source.get("search_template")
    search_url=tpl.format(q=quote_plus(query)) if tpl else source["base_url"]
    try:
        status, final_url, content_type, body=_request(search_url,timeout=DEFAULT_TIMEOUT)
        items=[]
        if "html" in content_type.lower(): items=_extract_results(body,final_url,query,limit)
        out={"source_id":source["id"],"source_name":source["name"],"role":source["role"],
                "source_kind":source.get("source_kind"),"authoritative":source.get("authoritative",False),
                "reachable":200 <= status < 400,"connectivity_status":_connectivity_status(http_status=status),
                "http_status":status,"search_url":search_url,
                "final_url":final_url,"results":items,"error":None}
        _cache_put("search",cache_key,out)
        return out
    except Exception as e:
        out={"source_id":source["id"],"source_name":source["name"],"role":source["role"],
                "source_kind":source.get("source_kind"),"authoritative":source.get("authoritative",False),
                "reachable":False,"connectivity_status":_connectivity_status(e),"http_status":getattr(e,"code",None),"search_url":search_url,"final_url":search_url,
                "results":[],"error":str(e)[:240]}
        return out



def fetch_official_document(url: str, timeout: int=DEFAULT_TIMEOUT) -> dict:
    """Fetch one document/detail URL without weakening TLS verification.

    The result separates transport success from source authority.  It is used by
    positive-law verification and never treats a successful HTTP response as a
    legal-status conclusion.
    """
    started=datetime.now(timezone.utc)
    cache_key=str(url or "").strip()
    cached=_cache_get("fetch",cache_key,FETCH_CACHE_TTL)
    if cached is not None:
        cached["cache_hit"]=True
        return cached
    if not _official_url(url):
        return {"url":url,"reachable":False,"official_host":False,"connectivity_status":"NON_OFFICIAL_HOST",
                "http_status":None,"final_url":url,"content_type":"","body":b"",
                "checked_at":started.isoformat(),"error":"URL host is outside official-source allowlist"}
    try:
        status,final_url,content_type,body=_request(url,timeout=timeout)
        out={"url":url,"reachable":200 <= status < 400,"official_host":_official_url(final_url),
                "connectivity_status":_connectivity_status(http_status=status),"http_status":status,
                "final_url":final_url,"content_type":content_type,"body":body,
                "checked_at":started.isoformat(),"error":None,"cache_hit":False}
        _cache_put("fetch",cache_key,out)
        return out
    except HTTPError as e:
        out={"url":url,"reachable":False,"official_host":True,"connectivity_status":_connectivity_status(e,http_status=e.code),
                "http_status":e.code,"final_url":url,"content_type":"","body":b"",
                "checked_at":started.isoformat(),"error":str(e)[:240],"cache_hit":False}
        return out
    except Exception as e:
        out={"url":url,"reachable":False,"official_host":True,"connectivity_status":_connectivity_status(e),
                "http_status":None,"final_url":url,"content_type":"","body":b"",
                "checked_at":started.isoformat(),"error":str(e)[:240],"cache_hit":False}
        return out


class FullTextLinkParser(HTMLParser):
    """Collect likely full-text/attachment links without interpreting legal meaning."""
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); t=tag.lower()
        if t == "a":
            self._href=a.get("href"); self._text=[]
        elif t in {"iframe","embed","object"}:
            href=a.get("src") or a.get("data")
            if href: self.links.append((href, a.get("title") or a.get("type") or t))
    def handle_data(self, data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self._href is not None:
            text=re.sub(r"\s+"," "," ".join(self._text)).strip()
            self.links.append((self._href,text)); self._href=None; self._text=[]


def _extract_pdf_text(body: bytes, max_pages: int=400, max_chars: int=2_500_000) -> str:
    if not body or PdfReader is None:
        return ""
    # Avoid expensive parser recovery and noisy "EOF marker not found" messages
    # for truncated/non-PDF responses returned by some official attachment URLs.
    head=bytes(body[:8])
    tail=bytes(body[-4096:])
    if not head.startswith(b"%PDF-") or b"%%EOF" not in tail:
        return ""
    try:
        reader=PdfReader(BytesIO(body), strict=False)
        parts=[]; total=0
        for page in list(reader.pages)[:max_pages]:
            try: text=page.extract_text() or ""
            except Exception: text=""
            if text:
                parts.append(text); total += len(text)
                if total >= max_chars: break
        return re.sub(r"\s+", " ", " ".join(parts))[:max_chars].strip()
    except Exception:
        return ""


def _fulltext_link_score(url: str, label: str, requested_provisions=()) -> int:
    low=(str(url or "")+" "+str(label or "")).lower()
    score=0
    if str(url or "").lower().split("?",1)[0].endswith(".pdf"): score += 40
    for marker,weight in (("download",24),("unduh",24),("lampiran",22),("attachment",22),("dokumen",18),("naskah",18),("fulltext",30),("full text",30),("lihat file",18),("file",10)):
        if marker in low: score += weight
    if any(str(x or "").lower() in low for x in requested_provisions or ()): score += 8
    return score


def resolve_official_fulltext(detail_url: str, detail_body: bytes, detail_content_type: str,
                              requested_provisions=(), timeout: int=DEFAULT_TIMEOUT, max_candidates: int=3) -> dict:
    """Resolve the actual official legal text behind a detail/metadata page.

    Fail-closed: only official-host URLs are followed. The function does not infer
    validity or applicability; it only returns text bytes/text provenance for the
    existing verifier. PDF text is extracted locally with pypdf.
    """
    ctype=(detail_content_type or "").lower()
    requested=[str(x) for x in (requested_provisions or []) if x]
    cache_key=(str(detail_url or ""), tuple(requested), len(detail_body or b""), str(detail_content_type or ""))
    cached=_cache_get("fulltext",cache_key,FULLTEXT_CACHE_TTL)
    if cached is not None:
        cached["cache_hit"]=True
        return cached
    if "pdf" in ctype or str(detail_url or "").lower().split("?",1)[0].endswith(".pdf"):
        text=_extract_pdf_text(detail_body)
        out={
            "resolved": bool(text), "source_url": detail_url, "content_type": detail_content_type,
            "text": text, "resolver_status": "DIRECT_PDF_TEXT" if text else "DIRECT_PDF_TEXT_UNAVAILABLE",
            "attempted_urls": [detail_url], "cache_hit": False,
        }
        _cache_put("fulltext",cache_key,out)
        return out
    if "html" not in ctype:
        out={"resolved":False,"source_url":detail_url,"content_type":detail_content_type,"text":"",
                "resolver_status":"UNSUPPORTED_DETAIL_CONTENT_TYPE","attempted_urls":[detail_url],"cache_hit":False}
        _cache_put("fulltext",cache_key,out)
        return out

    raw=detail_body.decode("utf-8","ignore") if isinstance(detail_body,(bytes,bytearray)) else str(detail_body or "")
    parser=FullTextLinkParser()
    try: parser.feed(raw)
    except Exception: pass
    candidates=[]; seen=set()
    for href,label in parser.links:
        url=urljoin(detail_url,href)
        if not url.startswith("http") or not _official_url(url) or url in seen: continue
        seen.add(url)
        score=_fulltext_link_score(url,label,requested)
        if score <= 0: continue
        candidates.append((score,url,label))
    candidates.sort(key=lambda x:x[0], reverse=True)
    attempted=[detail_url]
    best={"score":-1,"text":"","url":detail_url,"content_type":detail_content_type,"status":"DETAIL_HTML_ONLY"}
    # Include detail-page text as fallback/provenance, but prefer attachments.
    detail_text=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",raw)).strip()
    if detail_text:
        prov_hits=sum(1 for ref in requested if re.search(r"\b"+re.escape(ref)+r"\b", detail_text, re.I))
        best={"score":prov_hits*50,"text":detail_text,"url":detail_url,"content_type":detail_content_type,"status":"DETAIL_HTML_TEXT"}
    for _,url,_label in candidates[:max_candidates]:
        attempted.append(url)
        fetched=fetch_official_document(url,timeout=timeout)
        if not (fetched.get("reachable") and fetched.get("official_host")): continue
        ct=(fetched.get("content_type") or "").lower(); body=fetched.get("body") or b""
        if "pdf" in ct or url.lower().split("?",1)[0].endswith(".pdf"):
            text=_extract_pdf_text(body); status="ATTACHMENT_PDF_TEXT"
        elif "html" in ct:
            try:
                hp=AnchorParser(); # no-op object only to keep parser imports stable
                text=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",body.decode("utf-8","ignore"))).strip()
            except Exception: text=""
            status="ATTACHMENT_HTML_TEXT"
        else:
            text=""; status="ATTACHMENT_UNSUPPORTED"
        if not text: continue
        prov_hits=sum(1 for ref in requested if re.search(r"\b"+re.escape(ref)+r"\b", text, re.I))
        # Prefer a candidate containing the requested provision; otherwise prefer longer legal text.
        score=prov_hits*100000 + min(len(text),90000)
        if score > best["score"]:
            best={"score":score,"text":text,"url":fetched.get("final_url") or url,"content_type":fetched.get("content_type") or "","status":status}
    out={
        "resolved": bool(best.get("text")), "source_url": best.get("url") or detail_url,
        "content_type": best.get("content_type") or detail_content_type, "text": best.get("text") or "",
        "resolver_status": best.get("status") or "FULLTEXT_NOT_RESOLVED", "attempted_urls": attempted,
        "candidate_links_found": len(candidates), "cache_hit": False,
    }
    _cache_put("fulltext",cache_key,out)
    return out

def federated_search_many(queries, direct_ids=("bpk","mk","ma","jdih_mk"), per_source_limit: int=6,
                          max_workers: int=6, time_budget_seconds: float | None=30.0):
    """Bounded multi-query federation without nested thread pools.

    v1.3.13.11.2 regression stabilization: previous code ran one executor per
    query inside another query-level executor. A 10-query case routed to 8
    sources could create ~32 simultaneous TLS/DNS operations on Windows, making
    the local Flask process appear frozen. This dispatcher uses one bounded pool
    for the whole batch and returns explicit timeout diagnostics for unfinished
    jobs instead of blocking the request indefinitely.
    """
    queries=[re.sub(r"\s+"," ",(q or "")).strip() for q in (queries or [])]
    queries=list(dict.fromkeys(q for q in queries if q))
    targets=[src for src in OFFICIAL_SOURCES if src["id"] in direct_ids]
    order={src["id"]:i for i,src in enumerate(targets)}
    output={q:[] for q in queries}
    if not queries or not targets:
        return output
    worker_count=max(1,min(int(max_workers or 6),8,len(queries)*len(targets)))
    ex=ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="lexicore-jdih")
    futures={}
    try:
        for q in queries:
            for src in targets:
                futures[ex.submit(search_source,src,q,per_source_limit)]=(q,src)
        done,pending=wait(set(futures), timeout=time_budget_seconds) if time_budget_seconds else (set(futures),set())
        for fut in done:
            q,src=futures[fut]
            try:
                row=fut.result()
            except Exception as exc:
                row={"source_id":src["id"],"source_name":src["name"],"role":src.get("role"),
                     "source_kind":src.get("source_kind"),"authoritative":src.get("authoritative",False),
                     "reachable":False,"results":[],"error":str(exc)[:240]}
            output[q].append(row)
        for fut in pending:
            q,src=futures[fut]
            fut.cancel()
            output[q].append({"source_id":src["id"],"source_name":src["name"],"role":src.get("role"),
                              "source_kind":src.get("source_kind"),"authoritative":src.get("authoritative",False),
                              "reachable":False,"results":[],"error":"SEARCH_TIME_BUDGET_EXCEEDED",
                              "connectivity_status":"TIME_BUDGET_EXCEEDED"})
    finally:
        # Do not wait for a slow DNS/TLS worker after the request budget elapsed.
        # Running urllib calls still carry their own short socket timeout.
        ex.shutdown(wait=False, cancel_futures=True)
    for q in queries:
        output[q].sort(key=lambda x:order.get(x.get("source_id"),999))
    return output


def federated_search(query: str, direct_ids=("bpk","mk","ma","jdih_mk"), per_source_limit: int=6):
    return federated_search_many([query], direct_ids=direct_ids, per_source_limit=per_source_limit,
                                 max_workers=6, time_budget_seconds=20.0).get(query,[])


def verify_queries(queries, include_health=True, health_cache_only: bool=False):
    queries=[re.sub(r"\s+"," ",(q or "")).strip() for q in queries]
    queries=list(dict.fromkeys(q for q in queries if q))[:6]
    search_map=federated_search_many(queries, max_workers=6, time_budget_seconds=25.0)
    bundles=[{"query":q,"sources":search_map.get(q,[])} for q in queries]
    # Case Analysis can request cached-only health so a document run does not
    # launch another 14 connectivity probes on top of legal discovery. The
    # dedicated /api/legal-sources/health endpoint remains a live health check.
    health=source_health(cache_only=health_cache_only) if include_health else []
    authoritative_health=[s for s in health if s.get("authoritative")]
    directory_health=[s for s in health if not s.get("authoritative")]
    authoritative_searches=[s for b in bundles for s in b["sources"] if s.get("authoritative")]
    reachable_authoritative=sum(1 for s in authoritative_health if s.get("reachable")) if health else sum(1 for s in authoritative_searches if s.get("reachable"))
    total_authoritative=len(authoritative_health) if health else len(authoritative_searches)
    reachable_search_sources=sum(1 for s in authoritative_searches if s.get("reachable"))
    found=sum(len(s.get("results",[])) for s in authoritative_searches)
    if total_authoritative and reachable_authoritative == total_authoritative:
        status="FULL_OFFICIAL_SOURCE_ACCESS"
    elif reachable_authoritative or reachable_search_sources:
        status="PARTIAL_OFFICIAL_SOURCE_ACCESS"
    else:
        status="OFFICIAL_SOURCE_ACCESS_FAILED"
    return {
        "status":status,
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "queries":queries,
        "searches":bundles,
        "source_health":health,
        "summary":{
            "authoritative_sources_reached":reachable_authoritative,
            "authoritative_sources_total":total_authoritative,
            "reachable_search_sources":reachable_search_sources,
            "results_found":found,
            "directory_sources_reached":sum(1 for s in directory_health if s.get("reachable")),
            "jdihn_counted_as_authoritative":False,
            "health_cache_only":bool(health_cache_only),
        },
        "source_status":"VERIFIED_FROM_OFFICIAL_SOURCE" if found else ("OFFICIAL_SOURCES_REACHABLE_NO_MATCH" if reachable_authoritative else "NOT_VERIFIED"),
        "legal_status":"NEEDS_REVIEW",
        "cross_check":"COMPLETE" if status=="FULL_OFFICIAL_SOURCE_ACCESS" else ("PARTIAL" if status=="PARTIAL_OFFICIAL_SOURCE_ACCESS" else "FAILED"),
        "professional_verification":"PENDING",
        "disclaimer":"JDIHN hanya digunakan sebagai directory/discovery dan tidak dihitung sebagai sumber hukum primer. Hasil penelusuran berasal dari JDIH atau repository resmi instansi. Status berlaku, perubahan, pencabutan, hubungan lex specialis/lex posterior, putusan pengujian, serta relevansi terhadap fakta wajib diverifikasi profesional hukum sebelum digunakan.",
    }


def public_source_registry():
    return [{k:v for k,v in s.items() if k!="search_template"} | {"supports_direct_search":bool(s.get("search_template"))} for s in OFFICIAL_SOURCES]
