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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable

from legal_sources import federated_search, federated_search_many, fetch_official_document, resolve_official_fulltext
from services.positive_law_verification import html_to_text, verify_document_candidate, verify_provisions, classify_legal_document_candidate, regulation_identity, evaluate_case_nexus, normalize_provision_ref
from services.case_domain_classifier import classify_case
from database import RegulatoryCorpusManager

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
        "sources": ("atr_bpn", "bpk", "ma"),
        "queries": ("UUPA hak milik pendaftaran tanah", "PP pendaftaran tanah sertipikat hak milik"),
    },
    {
        "id": "religious_court", "label": "Peradilan Agama / Kompetensi Absolut",
        "keywords": {"pengadilan agama":5.0,"peradilan agama":5.0,"kompetensi absolut":5.0,"kewenangan absolut":5.0,"pasal 49":3.0,"uu no. 7 tahun 1989":5.0,"uu nomor 3 tahun 2006":5.0,"waris islam":4.0,"wakaf":4.0},
        "sources": ("kemenag", "bpk", "ma"),
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
    {
        "id": "consumer", "label": "Perlindungan Konsumen",
        "keywords": {"perlindungan konsumen":5.0,"konsumen":2.0,"pelaku usaha":2.0,"klausula baku":5.0,"badan penyelesaian sengketa konsumen":5.0,"bpsk":5.0},
        "sources": ("bpk", "ma"),
        "queries": ("UU Perlindungan Konsumen klausula baku pelaku usaha",),
    },
    {
        "id": "data_privacy", "label": "Pelindungan Data Pribadi / ITE",
        "keywords": {"data pribadi":5.0,"pelindungan data pribadi":5.0,"uu pdp":5.0,"informasi elektronik":4.0,"transaksi elektronik":4.0,"sistem elektronik":3.0},
        "sources": ("komdigi", "bpk", "mk", "ma"),
        "queries": ("UU Pelindungan Data Pribadi data pribadi", "UU ITE informasi elektronik transaksi elektronik"),
    },
    {
        "id": "bankruptcy", "label": "Kepailitan / PKPU",
        "keywords": {"kepailitan":5.0,"pkpu":5.0,"pailit":5.0,"dua kreditur":4.0,"pengadilan niaga":4.0},
        "sources": ("ma", "bpk"),
        "queries": ("UU Kepailitan PKPU dua kreditur jatuh tempo",),
    },
    {
        "id": "arbitration", "label": "Arbitrase / ADR",
        "keywords": {"arbitrase":5.0,"bani":5.0,"klausul arbitrase":5.0,"alternatif penyelesaian sengketa":4.0},
        "sources": ("bpk", "ma"),
        "queries": ("UU Arbitrase alternatif penyelesaian sengketa",),
    },
    {
        "id": "administrative", "label": "Hukum Administrasi / PTUN",
        "keywords": {"ptun":5.0,"keputusan tata usaha negara":5.0,"upaya administratif":5.0,"aaupb":5.0,"pejabat tata usaha negara":4.0},
        "sources": ("bpk", "ma", "kemendagri", "kemenkum"),
        "queries": ("UU PTUN keputusan tata usaha negara upaya administratif", "UU Administrasi Pemerintahan AUPB keputusan tindakan"),
    },
    {
        "id": "public_information", "label": "Keterbukaan Informasi Publik",
        "keywords": {"keterbukaan informasi publik":5.0,"informasi publik":4.0,"badan publik":4.0,"komisi informasi":5.0},
        "sources": ("bpk", "komdigi", "ma"),
        "queries": ("UU Keterbukaan Informasi Publik badan publik sengketa informasi",),
    },
    {
        "id": "investment", "label": "Penanaman Modal / Investasi",
        "keywords": {"penanaman modal":5.0,"investasi":4.0,"bkpm":5.0,"perizinan berusaha":4.0,"investor":3.0},
        "sources": ("bpk", "kemenkum"),
        "queries": ("UU Penanaman Modal perizinan berusaha investor",),
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
    """Return the immutable domain contract produced by Case Posture Classifier."""
    contract=classify_case(text)
    rule_map={r["id"]:r for r in DOMAIN_RULES}
    out=[]
    for d in contract.get('domains',[]):
        rid=d.get('id'); rule=rule_map.get(rid,{})
        out.append({
            'id':rid,'label':d.get('label') or rule.get('label') or rid,
            'confidence':round(float(d.get('confidence',0))/100.0,2),
            'role':d.get('role','SECONDARY'),'signal_score':d.get('score',0),
            'source_ids':list(rule.get('sources',('bpk','ma'))),
            'signals':[],
        })
    return out


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



KNOWN_REGULATION_QUERIES = {
    "land_property": (
        "Undang-Undang Nomor 5 Tahun 1960 Peraturan Dasar Pokok-Pokok Agraria",
        "Peraturan Pemerintah Nomor 24 Tahun 1997 Pendaftaran Tanah",
        "Peraturan Pemerintah Nomor 18 Tahun 2021 Pendaftaran Tanah",
    ),
    "religious_court": (
        "Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama",
        "Undang-Undang Nomor 3 Tahun 2006 Perubahan Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama",
        "Undang-Undang Nomor 50 Tahun 2009 Perubahan Kedua Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama",
    ),
}


def _known_query_domains(query: str, domains: list[dict]) -> list[str]:
    q=_clean(query).lower()
    active={str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"}
    matched=[]
    for domain_id, rows in KNOWN_REGULATION_QUERIES.items():
        if domain_id not in active:
            continue
        if any(q == _clean(x).lower() for x in rows):
            matched.append(domain_id)
    return matched


def build_case_queries(text: str, title: str = "", provision_refs=None, domains=None,
                       qualified_queries=None, legal_issues=None, max_queries: int = 10) -> list[str]:
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
    active_domains=[d for d in domains if d.get("role") != "SUPPORTING_ONLY"]

    # Known-regulation resolution first: exact legal instruments outrank broad
    # discovery so official news/event pages do not consume the verification budget.
    for domain in active_domains[:3]:
        queries.extend(KNOWN_REGULATION_QUERIES.get(domain.get("id"), ())[:3])

    for domain in active_domains[:3]:
        rule = rule_map.get(domain["id"], {})
        queries.extend(rule.get("queries", ())[:2])

    # Banking + corruption benchmark: add cross-domain questions lawyers actually
    # need to resolve, including personal authority and tempus.
    ids = {d["id"] for d in active_domains[:4]}
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
    for d in [x for x in domains if x.get("role") != "SUPPORTING_ONLY"][:4]:
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


def _compact_searches(queries: list[str], domains: list[dict], event_year: int | None, procedural_year: int | None = None, per_source_limit: int = 4) -> dict:
    source_ids = _source_ids_for_domains(domains)
    bundles, flat, seen_urls = [], [], set()
    discovered_count = 0
    # v1.3.13.11.1 — execute independent case queries concurrently.
    # The processing loop below still follows the original query order so ranking,
    # deduplication and report semantics remain deterministic.
    # v1.3.13.11.2 — one bounded federation pool for all query/source jobs.
    # Avoid the previous nested query-pool -> source-pool fan-out that could
    # create dozens of simultaneous TLS requests and freeze the local process.
    search_map=federated_search_many(
        queries, direct_ids=source_ids, per_source_limit=per_source_limit,
        max_workers=6, time_budget_seconds=30.0) if queries else {}
    for query in queries:
        searches = search_map.get(query,[])
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
                known_domains=_known_query_domains(query, domains)
                row["query_origin"] = "KNOWN_REGULATION" if known_domains else "DISCOVERY"
                active_domain_ids=[str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"]
                nexus=evaluate_case_nexus(row, active_domain_ids)
                row["case_nexus_domains"] = list(dict.fromkeys((known_domains or []) + (nexus.get("matched_domains") or [])))
                row["case_nexus_status"] = nexus.get("status") or "CASE_NEXUS_UNCERTAIN"
                row["case_nexus_reason"] = nexus.get("reason")
                row["document_classification"] = classify_legal_document_candidate(row)
                qlow=(query or "").lower()
                anchor_year = procedural_year if procedural_year and any(k in qlow for k in ("kuhap","praperadilan","upaya paksa","acara pidana","hukum acara","pengadilan")) else event_year
                row["temporal_anchor"] = "PROCEDURAL" if anchor_year==procedural_year and procedural_year else "MATERIAL_EVENT"
                row["temporal_status"] = _temporal_screen(row, anchor_year)
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
    legal_document_candidates=[r for r in temporal_not_excluded if (r.get("document_classification") or {}).get("legal_instrument_candidate")]
    rejected_non_legal=[r for r in temporal_not_excluded if not (r.get("document_classification") or {}).get("legal_instrument_candidate")]
    return {
        "bundles": bundles, "results": material[:24], "source_ids": list(source_ids),
        "funnel": {
            "discovered": discovered_count,
            "unique_discovered": len(flat),
            "candidate": len(candidates),
            "materially_relevant": len(material),
            "temporal_not_excluded": len(temporal_not_excluded),
            "authoritative_source_located": len(authoritative_located),
            "legal_document_candidates": len(legal_document_candidates),
            "rejected_non_legal_content": len(rejected_non_legal),
            "positive_law_verified": 0,
            "tempus_verified": 0,
            "verified_applicable": 0,
            "temporal_verified_applicable": 0,
            "provision_requested": 0,
            "provision_verified": 0,
            "provision_documents_verified": 0,
        },
    }



def _attach_requested_provisions(results: list[dict], provision_refs, local_database_matches) -> list[dict]:
    """Attach article-level candidates without inventing Pasal numbers.

    Sources are the case's explicit provision refs and matched local-corpus
    articles whose regulation identity/subject aligns with an official result.
    The official verifier still has to find the exact provision in retrieved
    official text before it can be marked verified.
    """
    explicit=[]
    for raw in provision_refs or []:
        ref=normalize_provision_ref(str(raw))
        if ref and ref not in explicit:
            explicit.append(ref)

    local=[]
    for match in local_database_matches or []:
        if not isinstance(match,dict):
            continue
        reg=match.get('regulation') or {}
        reg_id=regulation_identity(reg.get('nomor') or '')
        subject=_clean(reg.get('tentang') or '').lower()
        refs=[]
        for art in match.get('matched_articles') or []:
            if not isinstance(art,dict):
                continue
            for key in ('qualified_citation','pasal'):
                ref=normalize_provision_ref(art.get(key))
                if ref and ref not in refs:
                    refs.append(ref)
        if refs:
            local.append({'identity':reg_id,'subject':subject,'refs':refs})

    out=[]
    for row in results or []:
        item=dict(row)
        hay=_clean((item.get('title') or '')+' '+(item.get('query') or '')).lower()
        cid=regulation_identity(item.get('query') or '')
        if not cid.get('key'):
            cid=regulation_identity(item.get('title') or '')
        refs=list(explicit)
        for entry in local:
            same_identity=bool(cid.get('key') and entry['identity'].get('key') == cid.get('key'))
            subject=entry.get('subject') or ''
            subject_match=bool(subject and len(subject)>=8 and subject in hay)
            # Common amendment-chain titles can mention the base subject while
            # carrying the amending instrument's own identity. Subject matching
            # permits article verification across that chain, but does not prove it.
            if same_identity or subject_match:
                for ref in entry['refs']:
                    if ref not in refs:
                        refs.append(ref)
        item['requested_provisions']=refs[:8]
        out.append(item)
    return out


def _verify_positive_law_results(results: list[dict], snapshot: dict, max_documents: int = 10) -> list[dict]:
    """Verify only deterministic legal-instrument candidates.

    Official news, event, profile, and unidentified landing pages remain visible
    to diagnostics but do not consume the positive-law verification budget and
    are excluded from the Regulation & Tempus legal-instrument report section.
    """
    enriched=[]
    verified_budget=0
    # Fetch first-level official documents concurrently, but with one small
    # bounded pool. Processing and legal decisions below remain deterministic.
    fetch_map={}
    fetch_candidates=[]
    budget_scan=0
    for row in results:
        classification=row.get('document_classification') or classify_legal_document_candidate(row)
        url=row.get('url') or ''
        if classification.get('legal_instrument_candidate') and budget_scan < max_documents and row.get('authoritative') and url:
            budget_scan += 1
            fetch_candidates.append(url)
    if fetch_candidates:
        with ThreadPoolExecutor(max_workers=min(4,len(fetch_candidates))) as ex:
            futs={ex.submit(fetch_official_document,url,5):url for url in fetch_candidates}
            for fut in as_completed(futs):
                url=futs[fut]
                try: fetch_map[url]=fut.result()
                except Exception as exc:
                    fetch_map[url]={"url":url,"reachable":False,"official_host":True,"body":b"",
                                    "content_type":"","error":str(exc)[:240],"connectivity_status":"FETCH_ERROR"}
    for row in results:
        item=dict(row)
        classification=item.get('document_classification') or classify_legal_document_candidate(item)
        item['document_classification']=classification
        item['positive_law_verification']={
            'official_source_confirmed':bool(item.get('authoritative')),
            'text_retrieved':False,'identity_confirmed':False,
            'legal_status':'UNVERIFIED','tempus_status':'TEMPUS_UNVERIFIED',
            'case_nexus_status':item.get('case_nexus_status') or 'CASE_NEXUS_UNCERTAIN',
            'final_status':'UNVERIFIED','professional_verification':'PENDING',
        }
        if not classification.get('legal_instrument_candidate'):
            item['positive_law_verification'].update({
                'final_status':'REJECTED_NON_LEGAL_CONTENT',
                'diagnostic':classification.get('reason') or 'not a deterministic legal instrument candidate',
            })
            enriched.append(item)
            continue

        url=item.get('url') or ''
        if verified_budget < max_documents and item.get('authoritative') and url:
            verified_budget += 1
            fetched=fetch_map.get(url) or fetch_official_document(url, timeout=5)
            item['document_fetch']={k:v for k,v in fetched.items() if k!='body'}
            if fetched.get('reachable') and fetched.get('official_host'):
                ctype=(fetched.get('content_type') or '').lower()
                body=fetched.get('body') or b''
                if 'html' in ctype:
                    text=html_to_text(body)
                    item['positive_law_verification']=verify_document_candidate(
                        item, source_text=text, snapshot=snapshot)
                    # v1.3.12.4: provision verification may require the linked
                    # official PDF/full text rather than the metadata/detail page.
                    pv=item['positive_law_verification'].get('provision_verification') or {}
                    if (item['positive_law_verification'].get('identity_confirmed') is True
                            and item['positive_law_verification'].get('case_nexus_status') != 'NO_CASE_NEXUS'
                            and item['positive_law_verification'].get('case_nexus_status') == 'CASE_NEXUS_VERIFIED'
                            and int(pv.get('requested_count') or 0) > int(pv.get('verified_count') or 0)):
                        resolved=resolve_official_fulltext(
                            fetched.get('final_url') or url, body, fetched.get('content_type') or '',
                            requested_provisions=item.get('requested_provisions') or [], timeout=5, max_candidates=2)
                        item['fulltext_resolution']={k:v for k,v in resolved.items() if k!='text'}
                        if resolved.get('resolved') and resolved.get('text'):
                            item['positive_law_verification']['provision_verification']=verify_provisions(
                                item.get('requested_provisions') or [], resolved.get('text') or '', resolved.get('source_url'))
                            item['positive_law_verification']['provision_source_url']=resolved.get('source_url')
                            item['positive_law_verification']['provision_source_status']=resolved.get('resolver_status')
                    # Post-fetch identity is the final legal-document gate.
                    if not item['positive_law_verification'].get('identity_confirmed'):
                        if item['positive_law_verification'].get('case_nexus_status') == 'NO_CASE_NEXUS':
                            item['positive_law_verification']['final_status']='VERIFIED_NOT_RELEVANT'
                            item['positive_law_verification']['diagnostic']='official legal content retrieved but rejected by the case-nexus gate; identity mismatch retained as a diagnostic, not as the final semantic state'
                        else:
                            item['positive_law_verification']['final_status']='UNVERIFIED_IDENTITY_MISMATCH'
                            item['positive_law_verification']['diagnostic']='official page retrieved, but regulation identity does not match the requested instrument'
                elif 'pdf' in ctype or str(fetched.get('final_url') or url).lower().split('?',1)[0].endswith('.pdf'):
                    resolved=resolve_official_fulltext(
                        fetched.get('final_url') or url, body, fetched.get('content_type') or '',
                        requested_provisions=item.get('requested_provisions') or [], timeout=5, max_candidates=2)
                    item['fulltext_resolution']={k:v for k,v in resolved.items() if k!='text'}
                    if resolved.get('resolved') and resolved.get('text'):
                        item['positive_law_verification']=verify_document_candidate(
                            item, source_text=resolved.get('text') or '', snapshot=snapshot)
                        pv=item['positive_law_verification'].get('provision_verification') or {}
                        if pv.get('verified_count'):
                            item['positive_law_verification']['provision_source_url']=resolved.get('source_url')
                            item['positive_law_verification']['provision_source_status']=resolved.get('resolver_status')
                    else:
                        item['positive_law_verification'].update({
                            'text_retrieved':bool(body),'legal_status':'STATUS_UNCERTAIN',
                            'tempus_status':'TEMPUS_UNVERIFIED','final_status':'STATUS_UNCERTAIN',
                            'diagnostic':'official PDF retrieved but text extraction failed',
                        })
                else:
                    item['positive_law_verification'].update({
                        'text_retrieved':bool(body),
                        'legal_status':'STATUS_UNCERTAIN',
                        'tempus_status':'TEMPUS_UNVERIFIED',
                        'final_status':'STATUS_UNCERTAIN',
                        'diagnostic':'official document retrieved but content type is unsupported for deterministic full-text verification',
                    })
            else:
                item['positive_law_verification'].update({
                    'transport_status':fetched.get('connectivity_status'),
                    'diagnostic':fetched.get('error') or 'official document fetch failed',
                })
        enriched.append(item)
    return enriched



def _summarize_positive_law_verification(results: list[dict]) -> dict:
    status_verified=0
    tempus_verified=0
    verified_applicable=0
    provision_requested=0
    provision_verified=0
    provision_documents_verified=0
    for r in results or []:
        if not isinstance(r,dict):
            continue
        v=r.get("positive_law_verification") or {}
        if not v.get("identity_confirmed"):
            continue
        if v.get("legal_status") in {"IN_FORCE","AMENDED_IN_FORCE","REVOKED"}:
            status_verified += 1
        if v.get("tempus_status") in {"TEMPUS_VERIFIED","NOT_YET_EFFECTIVE","REVOKED_AT_TEMPUS"}:
            tempus_verified += 1
        if v.get("final_status") == "VERIFIED_APPLICABLE":
            verified_applicable += 1
        pv=v.get("provision_verification") or {}
        provision_requested += int(pv.get("requested_count") or 0)
        provision_verified += int(pv.get("verified_count") or 0)
        if pv.get("status") in {"PROVISION_VERIFIED","PROVISION_PARTIALLY_VERIFIED"} and int(pv.get("verified_count") or 0) > 0:
            provision_documents_verified += 1
    return {
        "positive_law_verified": status_verified,
        "tempus_verified": tempus_verified,
        "verified_applicable": verified_applicable,
        "temporal_verified_applicable": verified_applicable,
        "provision_requested": provision_requested,
        "provision_verified": provision_verified,
        "provision_documents_verified": provision_documents_verified,
    }


def filter_regulatory_matches_for_domains(matches: list[dict], domains: list[dict]) -> list[dict]:
    """Hard-prune local seed matches that do not belong to active case domains."""
    active={d.get('id') for d in (domains or []) if isinstance(d,dict) and d.get('role') != 'SUPPORTING_ONLY'}
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
        'data_privacy': ('data pribadi','pelindungan data pribadi','ite','informasi elektronik','transaksi elektronik'),
        'bankruptcy': ('kepailitan','pkpu','pailit','pengadilan niaga'),
        'arbitration': ('arbitrase','bani','alternatif penyelesaian sengketa'),
        'consumer': ('perlindungan konsumen','klausula baku','pelaku usaha'),
        'administrative': ('ptun','tata usaha negara','administrasi pemerintahan','aaupb','upaya administratif'),
        'public_information': ('keterbukaan informasi publik','informasi publik','komisi informasi'),
        'investment': ('penanaman modal','investasi','bkpm','perizinan berusaha'),
    }
    allowed=tuple(k for domain in active for k in vocab.get(domain,()))
    exclusive={
        'financial_services':('pojk','seojk','perbankan','bank perkreditan rakyat','bank perekonomian rakyat','bpr'),
        'corruption':('tipikor','pemberantasan tindak pidana korupsi'),
        'criminal':('kuhp','kuhap','kitab undang-undang hukum pidana','acara pidana'),
        'employment':('ketenagakerjaan','pkwt','pemutusan hubungan kerja','hubungan industrial'),
        'land_property':('uupa','pendaftaran tanah','hak tanggungan','pertanahan','agraria'),
        'religious_court':('peradilan agama','pengadilan agama'),
        'bankruptcy':('kepailitan','pkpu'),
        'arbitration':('arbitrase','bani'),
        'data_privacy':('pelindungan data pribadi','informasi dan transaksi elektronik'),
        'administrative':('peradilan tata usaha negara','administrasi pemerintahan'),
        'public_information':('keterbukaan informasi publik',),
        'investment':('penanaman modal',),
    }
    out=[]
    for row in matches or []:
        if not isinstance(row,dict): continue
        reg=row.get('regulation') or {}
        tags=' '.join(reg.get('domain_tags') or []).lower()
        hay=' '.join(str(reg.get(k) or '') for k in ('id','nomor','tentang','qualified_citation')).lower()+' '+tags
        hay += ' ' + ' '.join(str(a.get('pasal') or a.get('topic') or '') for a in (row.get('matched_articles') or []) if isinstance(a,dict)).lower()
        blocked=False
        for required,markers in exclusive.items():
            if required not in active and any(m in hay for m in markers):
                blocked=True; break
        if blocked: continue
        if allowed and any(k in hay for k in allowed):
            out.append(row)
    return out[:8]



def _database_matches_for_domains(text: str, domains: list[dict], limit: int = 10) -> list[dict]:
    """Retrieve the persisted SQLite corpus, constrained by the immutable domain contract."""
    rule_map={r['id']:r for r in DOMAIN_RULES}
    active=[d for d in (domains or []) if isinstance(d,dict) and d.get('role') != 'SUPPORTING_ONLY']
    merged={}
    for d in active[:4]:
        queries=list(rule_map.get(d.get('id'),{}).get('queries',()))[:2]
        if not queries: queries=[d.get('label') or d.get('id')]
        for q in queries:
            try:
                db_rows=RegulatoryCorpusManager.search(q,limit=max(limit,12))
            except Exception:
                # Direct unit use may occur before Flask startup initialized schema.
                # App startup normally creates/syncs the persistent corpus; fall back
                # to legacy seed matches rather than failing the Case Analysis.
                return []
            for reg in db_rows:
                rid=reg.get('id')
                if not rid: continue
                # Article relevance is computed only inside the already domain-gated regulation.
                terms=[t for t in re.findall(r'[\w-]+',(q or '').lower(),flags=re.UNICODE) if len(t)>2]
                arts=[]
                for a in reg.get('articles',[]) or []:
                    if not isinstance(a,dict): continue
                    hay=' '.join(str(a.get(k) or '') for k in ('pasal','topic','content')).lower()+' '+' '.join(a.get('keywords',[]) or []).lower()
                    score=sum(1 for t in terms if t in hay)
                    if score: arts.append((score,a))
                arts=[a for _,a in sorted(arts,key=lambda x:x[0],reverse=True)[:4]]
                row={'regulation':reg,'matched_articles':arts,'score':max(1,len(arts)*3),'source':'SQLITE_REGULATORY_CORPUS',
                     'verification_status':'LOCAL_DATABASE_MATCH — OFFICIAL SOURCE VERIFICATION REQUIRED','professional_verification':'PENDING'}
                if rid not in merged or row['score']>merged[rid]['score']: merged[rid]=row
    rows=filter_regulatory_matches_for_domains(list(merged.values()),active)
    return rows[:limit]


def retrieve_for_case_dynamic(*, text: str, title: str, provision_refs=None, qualified_queries=None,
                              local_seed_matches=None, legal_issues=None, online: bool = True,
                              retrieval_mode: str | None = None, domain_classification: dict | None = None) -> dict:
    mode_requested=(retrieval_mode or ('hybrid' if online else 'offline')).strip().lower()
    if mode_requested not in ('offline','online','hybrid'):
        mode_requested='hybrid'
    online = mode_requested in ('online','hybrid')
    if domain_classification:
        rule_map={r['id']:r for r in DOMAIN_RULES}
        domains=[]
        for d in domain_classification.get('domains',[]) or []:
            rid=d.get('id'); rule=rule_map.get(rid,{})
            domains.append({'id':rid,'label':d.get('label') or rule.get('label') or rid,'confidence':round(float(d.get('confidence',0))/100.0,2),'role':d.get('role','SECONDARY'),'signal_score':d.get('score',0),'source_ids':list(rule.get('sources',('bpk','ma'))),'signals':[]})
    else:
        domains = detect_domains(text)
    local_database_matches = _database_matches_for_domains(text, domains, limit=10) if mode_requested in ('offline','hybrid') else []
    event_year = detect_material_year(text)
    event_date = detect_material_date(text)
    date_candidates = detect_case_dates(text)
    procedural_dates=sorted([x.get('date') for x in date_candidates if x.get('role')=='procedural_or_filing' and x.get('date')])
    procedural_date = procedural_dates[0] if procedural_dates else None
    procedural_year = int(procedural_date[:4]) if procedural_date else None
    queries = build_case_queries(text, title, provision_refs, domains, qualified_queries, legal_issues)
    legacy_seed = filter_regulatory_matches_for_domains(list(local_seed_matches or []), domains)[:4]
    local_seed_matches = local_database_matches or legacy_seed
    official = {"bundles": [], "results": [], "source_ids": _source_ids_for_domains(domains),
                "funnel": {"discovered":0,"unique_discovered":0,"candidate":0,"materially_relevant":0,"temporal_not_excluded":0,"authoritative_source_located":0,"legal_document_candidates":0,"rejected_non_legal_content":0,"positive_law_verified":0,"tempus_verified":0,"verified_applicable":0,"temporal_verified_applicable":0,"provision_requested":0,"provision_verified":0,"provision_documents_verified":0}}
    error = None
    if online:
        try:
            official = _compact_searches(queries, domains, event_year, procedural_year)
        except Exception as exc:
            error = str(exc)[:300]

    results = official.get("results", [])
    results = _attach_requested_provisions(results, provision_refs, local_database_matches)
    verification_snapshot = {
        "event_year_candidate": event_year,
        "event_date_candidate": event_date,
        "procedural_date_candidate": procedural_date,
    }
    if online and results:
        results = _verify_positive_law_results(results, verification_snapshot, max_documents=10)
        official["results"] = results
        funnel = official.get("funnel") or {}
        funnel.update(_summarize_positive_law_verification(results))
    mode = {"offline":"LOCAL_DATABASE_ONLY","online":"OFFICIAL_ONLINE_ONLY","hybrid":"HYBRID_LOCAL_OFFICIAL"}.get(mode_requested,"HYBRID_LOCAL_OFFICIAL")
    if online and not results:
        mode = mode + "_NO_MATERIAL_ONLINE_MATCH"
    payload = {
        "mode": mode, "retrieval_mode": mode_requested, "domains": domains, "queries": queries,
        "event_year_candidate": event_year, "event_date_candidate": event_date, "procedural_date_candidate": procedural_date, "date_candidates": date_candidates,
        "official_results": results, "search_bundles": official.get("bundles", []),
        "official_source_ids": list(official.get("source_ids", [])),
        "retrieval_funnel": official.get("funnel", {}),
        "local_seed_matches": local_seed_matches, "local_database_results": local_database_matches,
        "official_results_count": len(results), "local_seed_count": len(local_seed_matches), "local_database_count": len(local_database_matches),
        "fetched_at": datetime.now(timezone.utc).isoformat(), "professional_verification": "PENDING",
        "cache_policy": "CASE_SCOPED_METADATA_ONLY", "error": error,
        "temporal_disclaimer": "Filter tempus ini adalah screening awal. Berlaku/tidak berlakunya norma wajib diverifikasi pada naskah resmi dan ketentuan peralihan.",
    }
    material = json.dumps({k: payload[k] for k in ("domains", "queries", "event_year_candidate", "event_date_candidate", "official_results", "retrieval_funnel")}, ensure_ascii=False, sort_keys=True)
    payload["content_hash"] = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return payload
