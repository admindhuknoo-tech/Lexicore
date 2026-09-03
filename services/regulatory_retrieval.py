"""Dynamic, case-scoped regulatory retrieval for LexiCore.

v1.3.5.2 precision rules:
- regulation follows the case, not a giant local corpus;
- strong legal entities outrank generic vocabulary;
- query generation is issue/domain driven and rejects orphan articles;
- discovery results are funneled: discovered -> candidate -> materially relevant
  -> temporal screen -> authoritative source located;
- temporal screening never claims final applicability without professional review.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Iterable

from legal_sources import federated_search

DOMAIN_RULES = [
    {
        "id": "financial_services", "label": "Perbankan / Jasa Keuangan",
        "keywords": {"bpr":5.0,"bank":2.0,"kredit":1.5,"debitur":1.5,"ojk":5.0,"pojk":5.0,"seojk":5.0,"slik":4.0,"bmpk":5.0,"agunan":2.0,"fidusia":2.0,"perkreditan":3.0,"komite kredit":4.0,"prinsip kehati-hatian":4.0},
        "sources": ("ojk", "bpk"),
        "queries": (
            "BPR tata kelola Direksi persetujuan kredit",
            "POJK BPR manajemen risiko kredit",
            "BPR prinsip kehati-hatian analisis kredit",
            "BPR batas maksimum pemberian kredit BMPK",
        ),
    },
    {
        "id": "employment", "label": "Ketenagakerjaan",
        "keywords": {"phk":5.0,"pemutusan hubungan kerja":5.0,"pesangon":4.0,"pkwt":5.0,"pkwtt":5.0,"pekerja":1.0,"buruh":2.0,"ketenagakerjaan":4.0,"upah":2.0,"outsourcing":3.0},
        "sources": ("kemnaker", "bpk"),
        "queries": ("UU Ketenagakerjaan PHK pesangon", "PP 35 Tahun 2021 PKWT PHK"),
    },
    {
        "id": "corruption", "label": "Tindak Pidana Korupsi",
        "keywords": {"korupsi":5.0,"tipikor":5.0,"kerugian negara":4.0,"memperkaya":3.0,"penyalahgunaan kewenangan":5.0,"gratifikasi":4.0,"suap":4.0,"pasal 603":5.0},
        "sources": ("bpk", "kemenkum", "mk", "ma"),
        "queries": ("UU Tipikor penyalahgunaan kewenangan kerugian negara", "KUHP tindak pidana korupsi Pasal 603"),
    },
    {
        "id": "criminal", "label": "Pidana / Acara Pidana",
        "keywords": {"tersangka":4.0,"terdakwa":4.0,"penyidikan":4.0,"penuntutan":4.0,"bap":4.0,"pidana":2.0,"kuhp":5.0,"kuhap":5.0,"praperadilan":5.0},
        "sources": ("bpk", "kemenkum", "mk", "ma"),
        "queries": ("KUHAP hak tersangka penyidikan", "KUHP asas legalitas tempus delicti"),
    },
    {
        "id": "civil_contract", "label": "Perdata / Perikatan",
        "keywords": {"perjanjian":0.7,"kontrak":1.5,"wanprestasi":5.0,"utang":0.8,"piutang":1.0,"ganti rugi":1.0,"kuhperdata":5.0,"perikatan":3.0},
        "sources": ("bpk", "ma"),
        "queries": ("KUHPerdata perjanjian wanprestasi",),
    },
    {
        "id": "corporate", "label": "Perseroan / Korporasi",
        "keywords": {"perseroan":5.0,"direksi":1.5,"komisaris":2.0,"pemegang saham":3.0,"pt ":3.0,"perusahaan":0.5,"business judgment":5.0},
        "sources": ("bpk", "ma"),
        "queries": ("Undang-Undang Perseroan Terbatas tanggung jawab Direksi",),
    },
    {
        "id": "land_property", "label": "Pertanahan / Properti",
        "keywords": {"sertifikat":4.0,"sertipikat":4.0,"shm":5.0,"hgb":5.0,"hak milik":4.0,"bpn":5.0,"kantor pertanahan":5.0,"pendaftaran tanah":5.0,"surat ukur":4.0,"data fisik":3.0,"data yuridis":3.0,"uupa":5.0,"agraria":4.0},
        "sources": ("bpk", "ma"),
        "queries": ("UUPA hak milik pendaftaran tanah", "PP pendaftaran tanah sertipikat hak milik"),
    },
    {
        "id": "religious_court", "label": "Peradilan Agama / Kompetensi Absolut",
        "keywords": {"pengadilan agama":5.0,"peradilan agama":5.0,"kompetensi absolut":5.0,"kewenangan absolut":5.0,"pasal 49":3.0,"uu no. 7 tahun 1989":5.0,"uu nomor 3 tahun 2006":5.0,"waris islam":4.0,"wakaf":4.0},
        "sources": ("bpk", "ma"),
        "queries": ("UU Peradilan Agama Pasal 49 kewenangan absolut", "Peradilan Agama kompetensi absolut sengketa waris wakaf"),
    },
    {
        "id": "civil_procedure", "label": "Hukum Acara Perdata",
        "keywords": {"gugatan":2.0,"tergugat":1.5,"penggugat":1.5,"eksepsi":4.0,"obscuur libel":5.0,"plurium litis consortium":5.0,"rekonvensi":4.0,"kompetensi absolut":4.0,"kewenangan absolut":4.0,"rv":3.0,"h.i.r":4.0,"hir":3.0},
        "sources": ("ma", "bpk"),
        "queries": ("hukum acara perdata eksepsi obscuur libel plurium litis consortium", "kompetensi absolut pengadilan gugatan perdata"),
    },
    {
        "id": "constitutional", "label": "Konstitusi / Pengujian Norma",
        "keywords": {"uud 1945":5.0,"konstitusi":4.0,"mahkamah konstitusi":5.0,"uji materi":5.0,"pengujian undang-undang":5.0},
        "sources": ("mk", "jdih_mk", "setneg"),
        "queries": ("UUD 1945 kepastian hukum",),
    },
    {
        "id": "regional_government", "label": "Pemerintahan Daerah / BUMD",
        "keywords": {"perda":3.0,"walikota":3.0,"bupati":3.0,"gubernur":3.0,"pemda":3.0,"pemerintah daerah":3.0,"bumd":5.0,"perumda":5.0},
        "sources": ("kemendagri", "bpk"),
        "queries": ("BUMD Perumda tata kelola Direksi",),
    },
]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _dedupe(values: Iterable[str], limit: int = 12) -> list[str]:
    out, seen = [], set()
    for value in values:
        v = _clean(value); key = v.lower()
        if not v or key in seen:
            continue
        seen.add(key); out.append(v)
        if len(out) >= limit:
            break
    return out


def _count_signal(low: str, signal: str) -> int:
    if signal.endswith(" "):
        return low.count(signal)
    return len(re.findall(r"(?<!\w)" + re.escape(signal) + r"(?!\w)", low, flags=re.I))


def detect_domains(text: str) -> list[dict]:
    low = (text or "").lower()
    found = []
    for rule in DOMAIN_RULES:
        signals, raw = [], 0.0
        for k, weight in rule["keywords"].items():
            count = _count_signal(low, k)
            if count:
                signals.append(k.strip())
                raw += weight * min(count, 6)
        if not signals:
            continue
        # Saturating score. Strong legal entities (BPR/OJK/POJK/Tipikor) quickly
        # outrank generic words such as perjanjian/utang/perusahaan.
        confidence = min(0.99, 0.25 + raw / 20.0)
        found.append({
            "id": rule["id"], "label": rule["label"], "confidence": round(confidence, 2),
            "signals": signals[:10], "signal_score": round(raw, 2), "source_ids": list(rule["sources"]),
        })

    # Context suppression: in a heavily regulated banking case, generic civil /
    # corporate vocabulary must not become the principal regulatory route.
    scores = {x["id"]: x for x in found}
    fin = scores.get("financial_services")
    if fin and fin["confidence"] >= 0.65:
        for sid in ("civil_contract", "corporate"):
            if sid in scores:
                scores[sid]["confidence"] = round(scores[sid]["confidence"] * 0.55, 2)
    found = list(scores.values())
    found.sort(key=lambda x: (x["confidence"], x.get("signal_score", 0)), reverse=True)
    if not found:
        return []
    # Hard relevance gate: a weak incidental domain must not route official-source
    # retrieval merely because one generic word occurred in a long pleading/BAP.
    top = found[0]["confidence"]
    threshold = max(0.45, round(top * 0.58, 2))
    gated = [d for d in found if d["confidence"] >= threshold or d.get("signal_score", 0) >= 12]
    return gated[:4]


def detect_material_year(text: str) -> int | None:
    """Best-effort event year for an initial tempus screen, never final law.

    Uses frequency plus material-context weighting instead of the earliest year;
    this avoids mistaking biography/employment history or old statute years for
    the tempus of the alleged act in long BAP documents.
    """
    raw = text or ""
    matches = list(re.finditer(r"\b(19\d{2}|20\d{2})\b", raw))
    if not matches:
        return None
    material_terms = ("kredit","pencairan","perbuatan","kejadian","transaksi","fasilitas","persetujuan","putusan","phk","kontrak","perjanjian","tempus")
    procedural_terms = ("surat perintah penyidikan","penetapan tersangka","berita acara pemeriksaan","pemeriksaan tersangka")
    scores = {}
    counts = {}
    now_year = datetime.now().year
    for m in matches:
        y = int(m.group(1))
        if y < 1945 or y > now_year:
            continue
        counts[y] = counts.get(y, 0) + 1
        window = raw[max(0,m.start()-140):m.end()+140].lower()
        score = 1.0
        score += 4.0 * sum(1 for t in material_terms if t in window)
        score -= 1.5 * sum(1 for t in procedural_terms if t in window)
        # statute citation years are useful context but weak evidence of tempus
        if re.search(r"(?:uu|undang-undang|pojk|seojk|peraturan)[^\n]{0,50}tahun\s*$", window[:140], re.I):
            score -= 2.0
        scores[y] = scores.get(y, 0.0) + score
    if not scores:
        return None
    # Frequency matters strongly in full documents; weighted context breaks ties.
    return max(scores, key=lambda y: (scores[y] + counts.get(y,0)*0.75, counts.get(y,0), y))



def _normalize_ocr_date_spacing(text: str) -> str:
    """Join OCR-split day digits only when immediately followed by an Indonesian month.
    Example: '2 6 Februari 2026' -> '26 Februari 2026'.
    """
    months = r'Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember'
    def repl(m):
        day = int(m.group(1) + m.group(2))
        return f"{day} {m.group(3)} {m.group(4)}" if 1 <= day <= 31 else m.group(0)
    return re.sub(rf'(?<!\d)([0-3])\s+([0-9])\s+({months})\s+(20\d{{2}})(?!\d)', repl, text or '', flags=re.I)


def detect_case_dates(text: str) -> list[dict]:
    raw = _normalize_ocr_date_spacing(text or '')
    months={'januari':1,'februari':2,'maret':3,'april':4,'mei':5,'juni':6,'juli':7,'agustus':8,'september':9,'oktober':10,'november':11,'desember':12}
    matches=[]
    for m in re.finditer(r'(?<!\d)(\d{1,2})\s*([A-Za-z]+)\s*(20\d{2})(?!\d)', raw, re.I):
        mon=months.get(m.group(2).lower())
        if mon: matches.append((m,int(m.group(1)),mon,int(m.group(3))))
    for m in re.finditer(r'(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](20\d{2})(?!\d)', raw):
        matches.append((m,int(m.group(1)),int(m.group(2)),int(m.group(3))))
    out=[]
    for m,d,mo,y in matches:
        if not (1<=d<=31 and 1<=mo<=12): continue
        before=raw[max(0,m.start()-160):m.start()].lower()
        near_before=raw[max(0,m.start()-90):m.start()].lower()
        near_after=raw[m.end():m.end()+45].lower()
        around=raw[max(0,m.start()-220):m.end()+180].lower()
        role='unknown'; score=0
        # Date role is determined from the immediate grammatical context. A statute
        # mentioned later in the same paragraph must not reclassify a transaction date.
        regulation_near = any(k in near_before for k in ('pojk','seojk','undang-undang','peraturan','uu no.','uu nomor')) or any(k in near_after for k in ('mulai berlaku','berlaku sejak','diundangkan'))
        if regulation_near:
            role='regulation_date'; score -= 20
        elif any(k in near_before for k in ('perjanjian kredit','transaksi','pencairan','persetujuan kredit','jual beli','akta jual beli','kejadian','perbuatan')):
            role='material_event'; score += 18
        elif any(k in near_before for k in ('gugatan','permohonan','surat gugatan','sidang','skpt','surat keterangan pendaftaran tanah','meminta')):
            role='procedural_or_filing'; score += 5
        elif any(k in near_before for k in ('surat ukur','pengumuman data fisik','data yuridis','sertifikat','sertipikat','diterbitkan')):
            role='historical_record'; score += 7
        if any(k in around for k in ('berita acara pemeriksaan','penetapan tersangka','surat perintah penyidikan')):
            if role == 'unknown': role='procedural_or_filing'
            score -= 4
        out.append({'date':f'{y:04d}-{mo:02d}-{d:02d}','role':role,'score':score,'context':_clean(around)[:260]})
    # dedupe date/role and sort strongest first
    seen=set(); unique=[]
    for item in sorted(out,key=lambda x:(x['score'],x['date']),reverse=True):
        key=(item['date'],item['role'])
        if key not in seen: seen.add(key); unique.append(item)
    return unique[:20]


def detect_material_date(text: str) -> str | None:
    """Return only a defensible material-event date, never a filing date by default."""
    candidates=detect_case_dates(text)
    material=[x for x in candidates if x['role']=='material_event' and x['score'] >= 10]
    return material[0]['date'] if material else None

def _qualified_ref(ref: str) -> bool:
    ref = _clean(ref)
    if not ref or re.fullmatch(r"Pasal\s+\d+[A-Za-z]?", ref, re.I):
        return False
    return any(k in ref.lower() for k in ("uu ", "undang-undang", "pojk", "seojk", "peraturan", "kuhp", "kuhap", "kuhperdata", "perma", "sema"))


def build_case_queries(text: str, title: str = "", provision_refs=None, domains=None,
                       qualified_queries=None, legal_issues=None, max_queries: int = 8) -> list[str]:
    provision_refs = provision_refs or []
    domains = domains or detect_domains(text)
    legal_issues = legal_issues or []
    queries: list[str] = []

    # 1) Exact regulation-qualified references from the case are strongest.
    queries.extend([_clean(str(r)) for r in provision_refs if _qualified_ref(str(r))])
    for q in qualified_queries or []:
        if _qualified_ref(str(q)):
            queries.append(_clean(str(q)))

    # 2) Domain/issue-driven routes before generic discovery phrases.
    rule_map = {r["id"]: r for r in DOMAIN_RULES}
    for domain in domains[:3]:
        rule = rule_map.get(domain["id"], {})
        queries.extend(rule.get("queries", ())[:2])

    # Banking + corruption benchmark: add cross-domain questions lawyers actually
    # need to resolve, including personal authority and tempus.
    ids = {d["id"] for d in domains[:4]}
    event_year = detect_material_year(text)
    if event_year and ("criminal" in ids or "corruption" in ids):
        queries.append(f"tempus delicti {event_year} asas legalitas ketentuan pidana")
    if "financial_services" in ids:
        if "regional_government" in ids:
            queries.append("Perumda BPR kewenangan Direksi persetujuan kredit tata kelola")
        if "corruption" in ids:
            queries.append("BPR kredit penyalahgunaan kewenangan kerugian negara Tipikor")

    # 3) Legal issues from deterministic/AI issue spotting, but only compact and
    # materially worded; do not let long free text dominate the query budget.
    for issue in legal_issues[:5]:
        if isinstance(issue, dict):
            issue = issue.get("issue") or issue.get("title") or issue.get("statement") or ""
        issue = _clean(str(issue))
        if 8 <= len(issue) <= 160:
            queries.append(issue)

    # 4) Existing qualified discovery queries are supplemental. Filter generic
    # domain labels that caused v1.3.5.1 to over-route to BW/corporate law.
    for q in qualified_queries or []:
        q = _clean(str(q))
        ql = q.lower()
        if not q or _qualified_ref(q) or re.fullmatch(r"Pasal\s+\d+[A-Za-z]?", q, re.I):
            continue
        if ql.startswith(("perdata & perikatan", "perusahaan & komersial")) and "financial_services" in ids:
            continue
        queries.append(q)

    title = _clean(title)
    if title and title.lower() != "case analysis" and len(title) <= 180:
        queries.append(title)
    if not queries:
        tokens = re.findall(r"\b[\w-]{4,}\b", (text or "")[:1800], flags=re.UNICODE)
        queries.append(" ".join(tokens[:10]))
    return _dedupe(queries, max_queries)


def _source_ids_for_domains(domains: list[dict]) -> tuple[str, ...]:
    ids = []
    for d in domains[:4]:
        ids.extend(d.get("source_ids", []))
    if not ids:
        ids = ["bpk", "kemenkum", "ma", "mk"]
    return tuple(_dedupe(ids, 8))


def _terms(value: str) -> set[str]:
    stop = {"yang","dan","atau","dengan","dalam","untuk","tahun","tentang","pasal","undang","peraturan","hukum","pada","bagi","dari","no"}
    return {t for t in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if t not in stop}


def _result_relevance(row: dict, domains: list[dict]) -> float:
    hay = _terms((row.get("title") or "") + " " + (row.get("query") or ""))
    if not hay:
        return 0.0
    domain_terms = set()
    strong_terms = set()
    rule_map = {r["id"]: r for r in DOMAIN_RULES}
    for d in domains[:3]:
        for k, weight in rule_map.get(d["id"], {}).get("keywords", {}).items():
            ts = _terms(k)
            domain_terms |= ts
            if weight >= 3:
                strong_terms |= ts
    overlap = len(hay & domain_terms)
    strong = len(hay & strong_terms)
    query_terms = _terms(row.get("query") or "")
    q_overlap = len(hay & query_terms)
    score = 0.08 * overlap + 0.16 * strong + 0.035 * q_overlap
    if row.get("authoritative"):
        score += 0.08
    return round(min(score, 1.0), 3)


def _temporal_screen(row: dict, event_year: int | None) -> str:
    if not event_year:
        return "TEMPUS_UNKNOWN"
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", row.get("title") or "")]
    if years and min(years) > event_year:
        return "POST_EVENT_REFERENCE"
    if years:
        return "NOT_EXCLUDED_BY_YEAR"
    return "TEMPUS_REQUIRES_VERIFICATION"


def _compact_searches(queries: list[str], domains: list[dict], event_year: int | None, per_source_limit: int = 4) -> dict:
    source_ids = _source_ids_for_domains(domains)
    bundles, flat, seen_urls = [], [], set()
    discovered_count = 0
    for query in queries:
        searches = federated_search(query, direct_ids=source_ids, per_source_limit=per_source_limit)
        compact_sources = []
        for src in searches:
            results = []
            for item in src.get("results", []):
                discovered_count += 1
                url = item.get("url") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                row = {
                    "title": _clean(item.get("title", ""))[:360], "url": url,
                    "source_id": src.get("source_id"), "source_name": src.get("source_name"),
                    "authoritative": bool(src.get("authoritative")), "query": query,
                    "source_score": item.get("score", 0),
                }
                row["relevance_score"] = _result_relevance(row, domains)
                row["temporal_status"] = _temporal_screen(row, event_year)
                results.append(row); flat.append(row)
            compact_sources.append({
                "source_id": src.get("source_id"), "source_name": src.get("source_name"),
                "authoritative": bool(src.get("authoritative")), "reachable": bool(src.get("reachable")),
                "http_status": src.get("http_status"), "results": results,
            })
        bundles.append({"query": query, "sources": compact_sources})

    flat.sort(key=lambda r: (r.get("relevance_score", 0), bool(r.get("authoritative"))), reverse=True)
    candidates = [r for r in flat if r.get("relevance_score", 0) >= 0.20]
    material = [r for r in candidates if r.get("relevance_score", 0) >= 0.38]
    temporal_not_excluded = [r for r in material if r.get("temporal_status") != "POST_EVENT_REFERENCE"]
    authoritative_located = [r for r in temporal_not_excluded if r.get("authoritative")]
    return {
        "bundles": bundles, "results": material[:24], "source_ids": list(source_ids),
        "funnel": {
            "discovered": discovered_count,
            "unique_discovered": len(flat),
            "candidate": len(candidates),
            "materially_relevant": len(material),
            "temporal_not_excluded": len(temporal_not_excluded),
            "authoritative_source_located": len(authoritative_located),
            "temporal_verified_applicable": 0,
        },
    }


def filter_regulatory_matches_for_domains(matches: list[dict], domains: list[dict]) -> list[dict]:
    """Hard-prune local seed matches that do not belong to active case domains."""
    active={d.get('id') for d in (domains or []) if isinstance(d,dict)}
    if not active:
        return []
    vocab={
        'financial_services': ('bank','bpr','pojk','seojk','kredit','ojk'),
        'corruption': ('tipikor','korupsi','603','penyalahgunaan kewenangan'),
        'criminal': ('kuhp','kuhap','pidana','praperadilan','tersangka'),
        'civil_contract': ('kuhperdata','kitab undang-undang hukum perdata','hukum perdata','burgerlijk','bw','perikatan','perjanjian','wanprestasi','1365'),
        'employment': ('ketenagakerjaan','pkwt','phk','pesangon','pp 35'),
        'corporate': ('perseroan','direksi','komisaris','uu no. 40 tahun 2007'),
        'land_property': ('uupa','agraria','pertanahan','pendaftaran tanah','sertipikat','sertifikat','bpn'),
        'religious_court': ('peradilan agama','pengadilan agama','uu no. 7 tahun 1989','uu nomor 3 tahun 2006','pasal 49'),
        'civil_procedure': ('hir','rbg','rv','acara perdata','obscuur','plurium','kompetensi absolut'),
        'regional_government': ('bumd','perumda','pemerintah daerah'),
        'constitutional': ('uud 1945','konstitusi','mahkamah konstitusi'),
    }
    allowed=tuple(k for domain in active for k in vocab.get(domain,()))
    out=[]
    for row in matches or []:
        if not isinstance(row,dict): continue
        reg=row.get('regulation') or {}
        hay=' '.join(str(reg.get(k) or '') for k in ('id','nomor','tentang','qualified_citation')).lower()
        hay += ' ' + ' '.join(str(a.get('pasal') or a.get('topic') or '') for a in (row.get('matched_articles') or []) if isinstance(a,dict)).lower()
        if allowed and any(k in hay for k in allowed):
            out.append(row)
    return out[:8]


def retrieve_for_case_dynamic(*, text: str, title: str, provision_refs=None, qualified_queries=None,
                              local_seed_matches=None, legal_issues=None, online: bool = True) -> dict:
    domains = detect_domains(text)
    event_year = detect_material_year(text)
    event_date = detect_material_date(text)
    date_candidates = detect_case_dates(text)
    queries = build_case_queries(text, title, provision_refs, domains, qualified_queries, legal_issues)
    local_seed_matches = filter_regulatory_matches_for_domains(list(local_seed_matches or []), domains)[:4]
    official = {"bundles": [], "results": [], "source_ids": _source_ids_for_domains(domains),
                "funnel": {"discovered":0,"unique_discovered":0,"candidate":0,"materially_relevant":0,"temporal_not_excluded":0,"authoritative_source_located":0,"temporal_verified_applicable":0}}
    error = None
    if online:
        try:
            official = _compact_searches(queries, domains, event_year)
        except Exception as exc:
            error = str(exc)[:300]

    results = official.get("results", [])
    mode = "DYNAMIC_CASE_SCOPED" if online else "LOCAL_SEED_FALLBACK"
    if online and not results:
        mode = "DYNAMIC_CASE_SCOPED_NO_MATERIAL_MATCH"
    payload = {
        "mode": mode, "domains": domains, "queries": queries,
        "event_year_candidate": event_year, "event_date_candidate": event_date, "date_candidates": date_candidates,
        "official_results": results, "search_bundles": official.get("bundles", []),
        "official_source_ids": list(official.get("source_ids", [])),
        "retrieval_funnel": official.get("funnel", {}),
        "local_seed_matches": local_seed_matches,
        "official_results_count": len(results), "local_seed_count": len(local_seed_matches),
        "fetched_at": datetime.now(timezone.utc).isoformat(), "professional_verification": "PENDING",
        "cache_policy": "CASE_SCOPED_METADATA_ONLY", "error": error,
        "temporal_disclaimer": "Filter tempus ini adalah screening awal. Berlaku/tidak berlakunya norma wajib diverifikasi pada naskah resmi dan ketentuan peralihan.",
    }
    material = json.dumps({k: payload[k] for k in ("domains", "queries", "event_year_candidate", "event_date_candidate", "official_results", "retrieval_funnel")}, ensure_ascii=False, sort_keys=True)
    payload["content_hash"] = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return payload
