"""LexiCore Official JDIH Federation.

JDIH and other first-party institutional repositories are authoritative online
verification targets. JDIHN is discovery/directory infrastructure only and is
never counted as a primary legal source. Network reachability is recorded
separately from legal status and professional verification.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import re
import ssl

from version import LEXICORE_VERSION

UA = f"LexiCore/{LEXICORE_VERSION} (+case-scoped official legal retrieval)"
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
    ctx=ssl.create_default_context()
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


def source_health(max_workers: int=8):
    results=[]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs={ex.submit(check_source,s):s for s in OFFICIAL_SOURCES}
        for f in as_completed(futs):
            try: results.append(f.result())
            except Exception as e: results.append({**futs[f],"reachable":False,"error":str(e)[:240]})
    order={s["id"]:i for i,s in enumerate(OFFICIAL_SOURCES)}
    results.sort(key=lambda x:order.get(x["id"],999))
    return results


def search_source(source: dict, query: str, limit: int=8):
    tpl=source.get("search_template")
    search_url=tpl.format(q=quote_plus(query)) if tpl else source["base_url"]
    try:
        status, final_url, content_type, body=_request(search_url,timeout=DEFAULT_TIMEOUT)
        items=[]
        if "html" in content_type.lower(): items=_extract_results(body,final_url,query,limit)
        return {"source_id":source["id"],"source_name":source["name"],"role":source["role"],
                "source_kind":source.get("source_kind"),"authoritative":source.get("authoritative",False),
                "reachable":200 <= status < 400,"http_status":status,"search_url":search_url,
                "final_url":final_url,"results":items,"error":None}
    except Exception as e:
        return {"source_id":source["id"],"source_name":source["name"],"role":source["role"],
                "source_kind":source.get("source_kind"),"authoritative":source.get("authoritative",False),
                "reachable":False,"http_status":None,"search_url":search_url,"final_url":search_url,
                "results":[],"error":str(e)[:240]}


def federated_search(query: str, direct_ids=("bpk","mk","ma","jdih_mk"), per_source_limit: int=6):
    targets=[s for s in OFFICIAL_SOURCES if s["id"] in direct_ids]
    searches=[]
    with ThreadPoolExecutor(max_workers=len(targets) or 1) as ex:
        futs={ex.submit(search_source,s,query,per_source_limit):s for s in targets}
        for f in as_completed(futs):
            try: searches.append(f.result())
            except Exception as e:
                s=futs[f]; searches.append({"source_id":s["id"],"source_name":s["name"],"reachable":False,"results":[],"error":str(e)[:240]})
    order={s["id"]:i for i,s in enumerate(targets)}
    searches.sort(key=lambda x:order.get(x.get("source_id"),999))
    return searches


def verify_queries(queries, include_health=True):
    queries=[re.sub(r"\s+"," ",(q or "")).strip() for q in queries]
    queries=list(dict.fromkeys(q for q in queries if q))[:6]
    bundles=[]
    for q in queries:
        bundles.append({"query":q,"sources":federated_search(q)})
    health=source_health() if include_health else []
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
        },
        "source_status":"VERIFIED_FROM_OFFICIAL_SOURCE" if found else ("OFFICIAL_SOURCES_REACHABLE_NO_MATCH" if reachable_authoritative else "NOT_VERIFIED"),
        "legal_status":"NEEDS_REVIEW",
        "cross_check":"COMPLETE" if status=="FULL_OFFICIAL_SOURCE_ACCESS" else ("PARTIAL" if status=="PARTIAL_OFFICIAL_SOURCE_ACCESS" else "FAILED"),
        "professional_verification":"PENDING",
        "disclaimer":"JDIHN hanya digunakan sebagai directory/discovery dan tidak dihitung sebagai sumber hukum primer. Hasil penelusuran berasal dari JDIH atau repository resmi instansi. Status berlaku, perubahan, pencabutan, hubungan lex specialis/lex posterior, putusan pengujian, serta relevansi terhadap fakta wajib diverifikasi profesional hukum sebelum digunakan.",
    }


def public_source_registry():
    return [{k:v for k,v in s.items() if k!="search_template"} | {"supports_direct_search":bool(s.get("search_template"))} for s in OFFICIAL_SOURCES]
