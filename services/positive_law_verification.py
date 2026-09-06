"""Conservative positive-law and tempus verification for LexiCore v1.3.12.

The verifier is deliberately fail-closed:
- a located link is not treated as proof that a norm is in force;
- source authority, document retrieval, legal status and tempus are separate states;
- VERIFIED_APPLICABLE is emitted only when the official document page itself
  supplies enough metadata to establish status/effective date and the case has
  a defensible temporal anchor.

No AI is used here.  The parser only records explicit source text/metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
import re
import unicodedata
from typing import Iterable


MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        if data and data.strip(): self.parts.append(data.strip())


def html_to_text(body: bytes | str) -> str:
    if isinstance(body, bytes):
        raw=body.decode("utf-8", "ignore")
    else:
        raw=str(body or "")
    p=_TextParser()
    try: p.feed(raw)
    except Exception: return re.sub(r"\s+", " ", unescape(raw)).strip()
    return re.sub(r"\s+", " ", unescape(" ".join(p.parts))).strip()


def parse_id_date(value: str | None) -> date | None:
    s=re.sub(r"\s+", " ", str(value or "")).strip()
    if not s: return None
    m=re.search(r"(?<!\d)(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(19\d{2}|20\d{2})(?!\d)", s, re.I)
    if m:
        try: return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError: return None
    m=re.search(r"(?<!\d)(19\d{2}|20\d{2})-(\d{2})-(\d{2})(?!\d)", s)
    if m:
        try: return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError: return None
    return None


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _first_date_after(text: str, labels: Iterable[str]) -> date | None:
    for label in labels:
        m=re.search(re.escape(label)+r".{0,90}", text, re.I)
        if m:
            parsed=parse_id_date(m.group(0))
            if parsed: return parsed
    return None


def _normalize_legal_identity_text(text: str | None) -> str:
    """Normalize layout noise without changing legal numbers/years.

    Official PDFs commonly split headings across lines, use Unicode dash variants,
    soft hyphens, or zero-width characters.  Identity matching may normalize
    typography/layout, but must never repair a number or year.
    """
    s=unicodedata.normalize("NFKC", str(text or ""))
    s=s.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    s=re.sub(r"[‐‑‒–—−]", "-", s)
    s=re.sub(r"\bUNDANG\s*-?\s*UNDANG\b", "UNDANG-UNDANG", s, flags=re.I)
    s=re.sub(r"\bREPUBL[K]?\s+INDONESIA\b", "REPUBLIK INDONESIA", s, flags=re.I)
    s=re.sub(r"\s+", " ", s).strip()
    return s


def _reg_identity(text: str) -> dict:
    """Extract only explicit regulation number/year identity from source text."""
    s=_normalize_legal_identity_text(text)
    patterns=(
        ("UU", r"(?:Undang-Undang|Undang undang|UU)(?:\s*\(UU\))?[\s:,-]+(?:(?:Republik|Republk)(?:\s+Indonesia)?[\s:,-]+)?(?:Nomor|No\.?)[\s:.-]*(\d+[A-Za-z]?)[\s,;:-]+Tahun[\s:.-]+(\d{4})"),
        ("PP", r"(?:Peraturan Pemerintah|PP)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("PERMA", r"(?:Peraturan Mahkamah Agung|PERMA)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("SEMA", r"(?:Surat Edaran Mahkamah Agung|SEMA)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("PERPRES", r"(?:Peraturan Presiden|PERPRES)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("POJK", r"(?:Peraturan Otoritas Jasa Keuangan|POJK)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+)(?:/POJK\.\d+)?/(20\d{2})"),
        ("POJK", r"(?:Peraturan Otoritas Jasa Keuangan|POJK)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+)\s+Tahun\s+(20\d{2})"),
        ("SEOJK", r"(?:Surat Edaran Otoritas Jasa Keuangan|SEOJK)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+)(?:/SEOJK\.\d+)?/(20\d{2})"),
        ("SEOJK", r"(?:Surat Edaran Otoritas Jasa Keuangan|SEOJK)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+)\s+Tahun\s+(20\d{2})"),
    )
    for kind,pat in patterns:
        m=re.search(pat,s,re.I)
        if m: return {"type":kind,"number":m.group(1),"year":int(m.group(2)),"key":f"{kind}:{m.group(1)}:{m.group(2)}"}
    return {"type":None,"number":None,"year":None,"key":None}




NON_LEGAL_TITLE_MARKERS = (
    "kunjungan kerja", "sosialisasi", "focus group discussion", "fgd", "berita",
    "siaran pers", "press release", "pengumuman", "kegiatan", "galeri", "agenda",
    "akan menambahkan koleksi", "bersama komisi", "profil", "artikel",
)


def regulation_identity(value: str | None) -> dict:
    """Public wrapper used by retrieval to resolve exact legal instruments."""
    return _reg_identity(str(value or ""))


def classify_legal_document_candidate(candidate: dict) -> dict:
    """Pre-fetch legal-document gate.

    Official-site content is not automatically a legal instrument.  A candidate
    is admitted only when its title carries a regulation identity, or the query
    itself is an exact regulation-qualified query.  Obvious news/event content
    is rejected even when hosted by an authoritative institution.
    """
    title=re.sub(r"\s+", " ", str(candidate.get("title") or "")).strip()
    query=re.sub(r"\s+", " ", str(candidate.get("query") or "")).strip()
    low=title.lower()
    title_identity=_reg_identity(title)
    query_identity=_reg_identity(query)
    non_legal_marker=next((m for m in NON_LEGAL_TITLE_MARKERS if m in low), None)

    if non_legal_marker and not title_identity.get("key"):
        return {
            "document_class":"NON_LEGAL_CONTENT",
            "legal_instrument_candidate":False,
            "reason":f"official content is news/event/publication ({non_legal_marker})",
            "expected_identity":query_identity,
        }
    if title_identity.get("key"):
        return {
            "document_class":"LEGAL_INSTRUMENT",
            "legal_instrument_candidate":True,
            "reason":"regulation identity present in result title",
            "expected_identity":title_identity,
        }
    if query_identity.get("key"):
        return {
            "document_class":"LEGAL_INSTRUMENT_CANDIDATE",
            "legal_instrument_candidate":True,
            "reason":"exact regulation identity present in retrieval query",
            "expected_identity":query_identity,
        }
    return {
        "document_class":"UNIDENTIFIED_OFFICIAL_CONTENT",
        "legal_instrument_candidate":False,
        "reason":"no deterministic legal-instrument identity in title/query",
        "expected_identity":query_identity,
    }




DOMAIN_NEXUS_MARKERS = {
    "financial_services": ("bpr", "bank", "kredit", "debitur", "ojk", "pojk", "seojk", "perkreditan", "agunan", "fidusia", "bmpk"),
    "corruption": ("tipikor", "korupsi", "pemberantasan tindak pidana korupsi", "kerugian negara", "penyalahgunaan kewenangan", "memperkaya"),
    "criminal": ("pidana", "kuhp", "kuhap", "tersangka", "terdakwa", "penyidikan", "penuntutan", "praperadilan"),
    "regional_government": ("pemerintah daerah", "pemda", "bumd", "perumda", "walikota", "bupati", "gubernur"),
    "land_property": ("agraria", "pertanahan", "pendaftaran tanah", "sertipikat", "sertifikat", "hak milik", "uupa", "bpn"),
    "religious_court": ("peradilan agama", "pengadilan agama", "kompetensi absolut", "kewenangan absolut", "waris", "wakaf"),
    "civil_procedure": ("acara perdata", "eksepsi", "obscuur", "plurium", "gugatan", "hir", "rbg", "rv", "perma", "sema"),
    "civil_contract": ("kuhperdata", "burgerlijk", "perikatan", "perjanjian", "wanprestasi", "perbuatan melawan hukum", "1365"),
    "employment": ("ketenagakerjaan", "pkwt", "pkwtt", "phk", "pemutusan hubungan kerja", "pesangon", "upah"),
    "corporate": ("perseroan", "direksi", "komisaris", "pemegang saham", "business judgment"),
    "administrative": ("ptun", "tata usaha negara", "administrasi pemerintahan", "aaupb", "upaya administratif"),
    "public_information": ("keterbukaan informasi publik", "informasi publik", "komisi informasi", "badan publik"),
    "investment": ("penanaman modal", "investasi", "bkpm", "perizinan berusaha"),
    "data_privacy": ("data pribadi", "pelindungan data pribadi", "informasi elektronik", "transaksi elektronik"),
    "consumer": ("perlindungan konsumen", "konsumen", "pelaku usaha", "klausula baku"),
    "bankruptcy": ("kepailitan", "pkpu", "pailit", "pengadilan niaga"),
    "arbitration": ("arbitrase", "bani", "alternatif penyelesaian sengketa"),
}

def evaluate_case_nexus(candidate: dict, active_domain_ids: Iterable[str] = ()) -> dict:
    """Conservative case-nexus gate.

    A search hit is never relevant merely because it came back from a query.
    Exact known-regulation queries require identity consistency. Discovery hits
    need subject-matter overlap with an active case domain and remain UNCERTAIN
    unless the overlap is strong.
    """
    active={str(x) for x in (active_domain_ids or ()) if x}
    title=re.sub(r"\s+", " ", str(candidate.get("title") or "")).strip()
    query=re.sub(r"\s+", " ", str(candidate.get("query") or "")).strip()
    low=(title+" "+query).lower()
    qid=_reg_identity(query)
    tid=_reg_identity(title)

    if qid.get("key"):
        if tid.get("key") and tid.get("key") != qid.get("key"):
            # Amendment titles often mention the base statute rather than their
            # own number. Keep those for post-fetch identity verification, but
            # never pre-verify the case nexus from the search hit alone.
            if "perubahan" in title.lower():
                # Allow an amendment/referencing title only when the base
                # regulation explicitly mentioned by that title is also part
                # of the exact query text (e.g. UU 50/2009 changing UU 7/1989).
                base_no=str(tid.get("number") or "")
                base_year=str(tid.get("year") or "")
                referenced=bool(base_no and base_year and re.search(r"(?:Nomor|No\.?)\s*"+re.escape(base_no)+r"\s+Tahun\s+"+re.escape(base_year), query, re.I))
                if referenced:
                    hinted=[d for d in active if any(m in low for m in DOMAIN_NEXUS_MARKERS.get(d,()))]
                    return {"status":"CASE_NEXUS_UNCERTAIN", "reason":"amendment/referencing title requires official-document identity verification", "matched_domains":sorted(hinted)}
            return {"status":"NO_CASE_NEXUS", "reason":"official search result identity differs from exact requested regulation", "matched_domains":[]}
        hinted=[d for d in active if any(m in low for m in DOMAIN_NEXUS_MARKERS.get(d,()))]
        return {"status":"CASE_NEXUS_UNCERTAIN", "reason":"exact regulation candidate requires post-fetch identity confirmation before nexus is verified", "matched_domains":sorted(hinted)}

    matched=[]
    for d in active:
        markers=DOMAIN_NEXUS_MARKERS.get(d,())
        hits=sum(1 for m in markers if m in low)
        if hits >= 2:
            matched.append(d)
    if matched:
        return {"status":"CASE_NEXUS_UNCERTAIN", "reason":"subject overlap found; exact predicate/legal-issue nexus still requires verification", "matched_domains":sorted(matched)}
    return {"status":"NO_CASE_NEXUS", "reason":"no material subject overlap with active case domains", "matched_domains":[]}

def _identity_from_key(value: str | None) -> dict:
    """Parse an already canonical TYPE:number:year key without inference."""
    s=str(value or "").strip()
    m=re.fullmatch(r"(UU|PP|PERMA|SEMA|PERPRES|POJK|SEOJK):([0-9]+[A-Za-z]?):(19\d{2}|20\d{2})", s, re.I)
    if not m:
        return {"type":None,"number":None,"year":None,"key":None}
    kind=m.group(1).upper(); number=m.group(2); year=int(m.group(3))
    return {"type":kind,"number":number,"year":year,"key":f"{kind}:{number}:{year}"}


def _expected_reg_identity(candidate: dict) -> tuple[dict, str]:
    """Resolve the requested instrument identity with auditable provenance.

    A case-bound instrument key is preferred because it was produced before web
    retrieval.  Otherwise exact query identity outranks result-title identity.
    No number/year repair is ever performed here.
    """
    binding=candidate.get('provision_binding_provenance') or {}
    bound=_identity_from_key(binding.get('instrument_key'))
    if bound.get('key'):
        return bound, 'CASE_BOUND_INSTRUMENT_KEY'
    query=_reg_identity(candidate.get("query") or "")
    if query.get('key'):
        return query, 'QUERY_IDENTITY'
    title=_reg_identity(candidate.get("title") or "")
    if title.get('key'):
        return title, 'TITLE_IDENTITY'
    classified=((candidate.get('document_classification') or {}).get('expected_identity') or {})
    if classified.get('key'):
        return classified, 'CLASSIFICATION_IDENTITY'
    return {"type":None,"number":None,"year":None,"key":None}, 'NO_EXPECTED_IDENTITY'


def _source_identity_candidates(source_text: str) -> list[dict]:
    """Extract canonical identities from noisy official text in source order.

    The first parser remains the strict regulation parser.  The additional scan
    tolerates official heading layout such as `UNDANG-UNDANG REPUBLIK INDONESIA
    NOMOR 31 TAHUN 1999` after PDF text extraction.  It does not infer or repair
    any legal number/year.
    """
    s=_normalize_legal_identity_text(source_text)
    out=[]; seen=set()
    first=_reg_identity(s)
    if first.get('key'):
        seen.add(first['key']); out.append(first)
    patterns=(
        ('UU', r"\bUNDANG-UNDANG(?:\s+REPUBLIK\s+INDONESIA)?\s+(?:NOMOR|NO\.?)\s*([0-9]+[A-Za-z]?)\s+TAHUN\s+(19\d{2}|20\d{2})\b"),
        ('PP', r"\bPERATURAN\s+PEMERINTAH(?:\s+REPUBLIK\s+INDONESIA)?\s+(?:NOMOR|NO\.?)\s*([0-9]+[A-Za-z]?)\s+TAHUN\s+(19\d{2}|20\d{2})\b"),
        ('PERPRES', r"\bPERATURAN\s+PRESIDEN(?:\s+REPUBLIK\s+INDONESIA)?\s+(?:NOMOR|NO\.?)\s*([0-9]+[A-Za-z]?)\s+TAHUN\s+(19\d{2}|20\d{2})\b"),
        ('PERMA', r"\bPERATURAN\s+MAHKAMAH\s+AGUNG(?:\s+REPUBLIK\s+INDONESIA)?\s+(?:NOMOR|NO\.?)\s*([0-9]+[A-Za-z]?)\s+TAHUN\s+(19\d{2}|20\d{2})\b"),
        ('SEMA', r"\bSURAT\s+EDARAN\s+MAHKAMAH\s+AGUNG(?:\s+REPUBLIK\s+INDONESIA)?\s+(?:NOMOR|NO\.?)\s*([0-9]+[A-Za-z]?)\s+TAHUN\s+(19\d{2}|20\d{2})\b"),
        ('POJK', r"\b(?:PERATURAN\s+OTORITAS\s+JASA\s+KEUANGAN|POJK)(?:\s+REPUBLIK\s+INDONESIA)?\s+(?:NOMOR|NO\.?)\s*([0-9]+)(?:/POJK\.[0-9]+)?(?:/|\s+TAHUN\s+)(20\d{2})\b"),
        ('SEOJK', r"\b(?:SURAT\s+EDARAN\s+OTORITAS\s+JASA\s+KEUANGAN|SEOJK)(?:\s+REPUBLIK\s+INDONESIA)?\s+(?:NOMOR|NO\.?)\s*([0-9]+)(?:/SEOJK\.[0-9]+)?(?:/|\s+TAHUN\s+)(20\d{2})\b"),
    )
    for kind,pat in patterns:
        for m in re.finditer(pat,s,re.I):
            number=m.group(1); year=int(m.group(2)); key=f"{kind}:{number}:{year}"
            if key not in seen:
                seen.add(key); out.append({"type":kind,"number":number,"year":year,"key":key})
    return out


def _identity_matches(candidate: dict, source_text: str) -> tuple[bool, dict]:
    expected,expected_from=_expected_reg_identity(candidate)
    candidates=_source_identity_candidates(source_text)
    actual=candidates[0] if candidates else {"type":None,"number":None,"year":None,"key":None}
    matched=next((x for x in candidates if expected.get('key') and x.get('key') == expected.get('key')), None)
    ok=bool(matched)
    diagnostic=dict(matched or actual)
    diagnostic.update({
        'expected_key':expected.get('key'),
        'expected_identity':expected,
        'expected_identity_source':expected_from,
        'actual_identity_candidates':[x.get('key') for x in candidates[:8] if x.get('key')],
        'match_reason':'CANONICAL_TYPE_NUMBER_YEAR_MATCH' if ok else ('EXPECTED_IDENTITY_MISSING' if not expected.get('key') else 'OFFICIAL_TEXT_IDENTITY_MISMATCH'),
    })
    return ok, diagnostic


PROVISION_RE = re.compile(
    r"\bPasal\s+(\d+[A-Za-z]?)(?:\s+ayat\s*\(([^)]+)\))?(?:\s+huruf\s+([a-z]))?",
    re.I,
)


def normalize_provision_ref(value: str | None) -> str | None:
    """Normalize an explicit article-level reference without inventing one."""
    text=re.sub(r"\s+", " ", str(value or "")).strip()
    m=PROVISION_RE.search(text)
    if not m:
        return None
    out=f"Pasal {m.group(1)}"
    if m.group(2):
        out += f" ayat ({m.group(2).strip()})"
    if m.group(3):
        out += f" huruf {m.group(3).lower()}"
    return out


def extract_provision_refs(text: str | None) -> list[str]:
    """Return explicit Pasal/ayat/huruf references present in text."""
    out=[]
    seen=set()
    for m in PROVISION_RE.finditer(str(text or "")):
        raw=m.group(0)
        ref=normalize_provision_ref(raw)
        if ref and ref.lower() not in seen:
            seen.add(ref.lower()); out.append(ref)
    return out


def _provision_pattern(ref: str) -> re.Pattern | None:
    norm=normalize_provision_ref(ref)
    if not norm:
        return None
    m=PROVISION_RE.search(norm)
    number=re.escape(m.group(1))
    pat=rf"\bPasal\s+{number}\b"
    if m.group(2):
        pat += rf"(?:\s+ayat\s*\(\s*{re.escape(m.group(2).strip())}\s*\))"
    if m.group(3):
        pat += rf"(?:\s+huruf\s+{re.escape(m.group(3))})"
    return re.compile(pat, re.I)


def locate_provisions(requested_provisions: Iterable[str], source_text: str, source_url: str | None = None) -> dict:
    """Locate requested article references in retrieved official text.

    TEXT_LOCATED is evidentiary telemetry only.  It does not prove instrument
    identity, case nexus, legal status, tempus, or applicability.
    """
    requested=[]
    seen=set()
    for raw in requested_provisions or []:
        ref=normalize_provision_ref(raw)
        if ref and ref.lower() not in seen:
            seen.add(ref.lower()); requested.append(ref)
    if not requested:
        return {
            "status":"PROVISION_TEXT_NOT_REQUESTED", "requested":[], "located":[],
            "not_located":[], "citations":[], "located_count":0, "requested_count":0,
        }
    located=[]; missing=[]; citations=[]
    text=str(source_text or "")
    for ref in requested:
        pat=_provision_pattern(ref)
        m=pat.search(text) if pat else None
        if not m:
            missing.append(ref); continue
        located.append(ref)
        start=max(0,m.start()-90); end=min(len(text),m.end()+140)
        excerpt=re.sub(r"\s+", " ", text[start:end]).strip()
        citations.append({
            "provision":ref,
            "status":"LOCATED_IN_OFFICIAL_TEXT",
            "source_url":source_url,
            "matched_text":m.group(0),
            "source_excerpt":excerpt[:260],
        })
    if len(located)==len(requested):
        status="PROVISION_TEXT_LOCATED"
    elif located:
        status="PROVISION_TEXT_PARTIALLY_LOCATED"
    else:
        status="PROVISION_TEXT_NOT_FOUND"
    return {
        "status":status, "requested":requested, "located":located,
        "not_located":missing, "citations":citations,
        "located_count":len(located), "requested_count":len(requested),
    }


def verify_provisions(requested_provisions: Iterable[str], source_text: str, source_url: str | None = None) -> dict:
    """Fail-closed article-level verification against retrieved official text.

    This verifies only that an explicitly requested Pasal/ayat/huruf reference is
    present in the official text retrieved for the already identity-confirmed
    instrument.  It does not infer article meaning or applicability.
    """
    requested=[]
    seen=set()
    for raw in requested_provisions or []:
        ref=normalize_provision_ref(raw)
        if ref and ref.lower() not in seen:
            seen.add(ref.lower()); requested.append(ref)
    if not requested:
        return {
            "status":"PROVISION_NOT_REQUESTED", "requested":[], "verified":[],
            "unverified":[], "citations":[], "verified_count":0, "requested_count":0,
        }
    verified=[]; missing=[]; citations=[]
    text=str(source_text or "")
    for ref in requested:
        pat=_provision_pattern(ref)
        m=pat.search(text) if pat else None
        if not m:
            missing.append(ref); continue
        verified.append(ref)
        start=max(0,m.start()-90); end=min(len(text),m.end()+140)
        excerpt=re.sub(r"\s+", " ", text[start:end]).strip()
        citations.append({
            "provision":ref,
            "status":"VERIFIED_IN_OFFICIAL_TEXT",
            "source_url":source_url,
            "matched_text":m.group(0),
            "source_excerpt":excerpt[:260],
        })
    if len(verified)==len(requested):
        status="PROVISION_VERIFIED"
    elif verified:
        status="PROVISION_PARTIALLY_VERIFIED"
    else:
        status="PROVISION_UNVERIFIED"
    return {
        "status":status, "requested":requested, "verified":verified,
        "unverified":missing, "citations":citations,
        "verified_count":len(verified), "requested_count":len(requested),
    }


def _dates_near_relationship(text: str, marker_pattern: str) -> list[str]:
    """Extract explicit dates close to a legal-status relationship marker."""
    out=[]
    for m in re.finditer(marker_pattern, text or "", re.I):
        window=(text or "")[m.start():m.start()+260]
        d=parse_id_date(window)
        if d and d.isoformat() not in out:
            out.append(d.isoformat())
    return out


def _relationship_years(text: str, marker_pattern: str) -> list[int]:
    out=[]
    for m in re.finditer(marker_pattern, text or "", re.I):
        window=(text or "")[m.start():m.start()+260]
        for y in re.findall(r"\b(19\d{2}|20\d{2})\b", window):
            yi=int(y)
            if yi not in out:
                out.append(yi)
    return out


def extract_status_metadata(source_text: str) -> dict:
    """Extract explicit legal lifecycle metadata from an official source.

    The parser separates current instrument status from status at the case
    tempus. It never assumes that a later regulation repeals or amends the
    requested instrument merely because its year is newer.
    """
    text=re.sub(r"\s+", " ", source_text or "").strip()
    low=text.lower()
    effective=_first_date_after(text, (
        "Tanggal Berlaku", "Tanggal mulai berlaku", "Berlaku mulai",
        "mulai berlaku pada tanggal", "mulai berlaku sejak",
        "berlaku pada tanggal", "berlaku sejak",
    ))
    promulgation=_first_date_after(text, (
        "Tanggal Pengundangan", "Tanggal Diundangkan",
        "Diundangkan pada tanggal", "diundangkan tanggal"))
    enactment=_first_date_after(text, (
        "Tanggal Penetapan", "Ditetapkan pada tanggal", "ditetapkan tanggal"))
    if effective is None and promulgation and re.search(
            r"\b(?:mulai\s+)?berlaku\s+(?:pada|sejak)\s+tanggal\s+diundangkan\b", low, re.I):
        effective=promulgation

    repeal_marker=r"\b(?:dicabut dengan|dinyatakan tidak berlaku|tidak berlaku lagi|status(?: peraturan)?\s*:?\s*tidak berlaku)\b"
    amendment_marker=r"\b(?:diubah dengan|telah diubah(?: dengan)?)\b"
    amends_other=bool(re.search(r"\bperubahan(?:\s+kedua|\s+ketiga)?\s+atas\b", low, re.I))
    revoked=bool(re.search(repeal_marker, low, re.I))
    amended=bool(re.search(amendment_marker, low, re.I))
    transitional=bool(re.search(r"\bketentuan peralihan\b", low, re.I))
    explicit_in_force=bool(effective) or bool(re.search(r"\bberlaku mulai\b|\bmulai berlaku\b|\bstatus(?: peraturan)?\s*:?\s*berlaku\b", low, re.I))

    repeal_dates=_dates_near_relationship(text,repeal_marker)
    amendment_dates=_dates_near_relationship(text,amendment_marker)
    repeal_years=_relationship_years(text,repeal_marker)
    amendment_years=_relationship_years(text,amendment_marker)

    status="STATUS_UNCERTAIN"
    if revoked:
        status="REVOKED"
    elif explicit_in_force and amended:
        status="AMENDED_IN_FORCE"
    elif explicit_in_force:
        status="IN_FORCE"

    return {
        "legal_status": status,
        "effective_date": _iso(effective),
        "promulgation_date": _iso(promulgation),
        "enactment_date": _iso(enactment),
        "repeal_date": repeal_dates[0] if repeal_dates else None,
        "repeal_dates": repeal_dates,
        "amendment_dates": amendment_dates,
        "repeal_years": repeal_years,
        "amendment_years": amendment_years,
        "amended": amended,
        "amends_other_instrument": amends_other,
        "revoked": revoked,
        "transitional_rule_found": transitional,
        "explicit_in_force_marker": explicit_in_force,
    }

def choose_temporal_anchor(candidate: dict, snapshot: dict) -> tuple[str | None, str]:
    hay=((candidate.get("title") or "")+" "+(candidate.get("query") or "")).lower()
    procedural=any(k in hay for k in (
        "hukum acara", "acara perdata", "peradilan agama", "pengadilan agama",
        "kuhap", "praperadilan", "perma", "sema", "kompetensi absolut",
        "obscuur", "plurium",
    ))
    if procedural and snapshot.get("procedural_date_candidate"):
        return str(snapshot.get("procedural_date_candidate")), "PROCEDURAL_DATE"
    if snapshot.get("event_date_candidate"):
        return str(snapshot.get("event_date_candidate")), "SUBSTANTIVE_DATE"
    if snapshot.get("event_year_candidate"):
        return str(snapshot.get("event_year_candidate")), "YEAR_SCREENING_CANDIDATE"
    # Never use a procedural/hearing date to verify a substantive criminal or
    # civil norm. If the material-event date/year is absent, tempus must stay
    # unresolved rather than being promoted from the process date.
    return None, "UNKNOWN_DATE"


def verify_tempus(*, effective_date: str | None, anchor_value: str | None,
                  revoked: bool, transitional_rule_found: bool,
                  repeal_date: str | None = None, repeal_years: Iterable[int] = ()) -> dict:
    """Resolve status of the instrument at the relevant case date.

    Current repeal does not erase historical applicability. A revoked
    instrument may still have been in force at the material event, but only
    when an explicit repeal date allows that conclusion.
    """
    if not anchor_value:
        return {"status":"TEMPUS_UNVERIFIED","applicable":None,"status_at_tempus":"UNKNOWN","reason":"case temporal anchor not established"}
    eff=parse_id_date(effective_date)
    if not eff:
        return {"status":"TEMPUS_UNVERIFIED","applicable":None,"status_at_tempus":"UNKNOWN","reason":"effective date not verified from official source"}
    rep=parse_id_date(repeal_date)
    rep_years=sorted({int(y) for y in (repeal_years or []) if str(y).isdigit()})
    rep_year=rep.year if rep else (rep_years[0] if rep_years else None)

    anchor=parse_id_date(anchor_value)
    if not anchor and re.fullmatch(r"\d{4}", str(anchor_value)):
        year=int(anchor_value)
        if eff.year > year:
            return {"status":"NOT_YET_EFFECTIVE","applicable":False,"status_at_tempus":"NOT_YET_EFFECTIVE","reason":"regulation effective year is after case anchor year"}
        if revoked and rep_year:
            if rep_year < year:
                return {"status":"REVOKED_AT_TEMPUS","applicable":False,"status_at_tempus":"REVOKED","reason":"verified repeal year predates case anchor year"}
            if rep_year == year:
                return {"status":"TEMPUS_REQUIRES_EXACT_DATE","applicable":None,"status_at_tempus":"UNKNOWN","reason":"repeal and case anchor occur in the same year; exact date required"}
            return {"status":"TEMPUS_VERIFIED","applicable":True,"status_at_tempus":"IN_FORCE_BEFORE_REPEAL","reason":"instrument was effective and repeal occurred after case anchor year"}
        if revoked and not rep_year:
            return {"status":"REPEAL_DATE_REQUIRED","applicable":None,"status_at_tempus":"UNKNOWN","reason":"current source records repeal but no explicit repeal date/year was verified"}
        if eff.year < year:
            return {"status":"TEMPUS_VERIFIED","applicable":True,"status_at_tempus":"IN_FORCE","reason":"regulation was effective before case anchor year"}
        return {"status":"TEMPUS_REQUIRES_EXACT_DATE","applicable":None,"status_at_tempus":"UNKNOWN","reason":"same-year screening requires exact case date"}
    if not anchor:
        return {"status":"TEMPUS_UNVERIFIED","applicable":None,"status_at_tempus":"UNKNOWN","reason":"case temporal anchor could not be parsed"}
    if anchor < eff:
        return {"status":"NOT_YET_EFFECTIVE","applicable":False,"status_at_tempus":"NOT_YET_EFFECTIVE","reason":"case date predates regulation effective date"}
    if revoked:
        if rep:
            if anchor >= rep:
                if transitional_rule_found:
                    return {"status":"TRANSITIONAL_REVIEW_REQUIRED","applicable":None,"status_at_tempus":"REPEALED_OR_TRANSITIONAL","reason":"case date is on/after verified repeal date and transitional provision exists"}
                return {"status":"REVOKED_AT_TEMPUS","applicable":False,"status_at_tempus":"REVOKED","reason":"case date is on/after verified repeal date"}
            return {"status":"TEMPUS_VERIFIED","applicable":True,"status_at_tempus":"IN_FORCE_BEFORE_REPEAL","reason":"case date predates verified repeal date"}
        if rep_year:
            if anchor.year < rep_year:
                return {"status":"TEMPUS_VERIFIED","applicable":True,"status_at_tempus":"IN_FORCE_BEFORE_REPEAL","reason":"case year predates verified repeal instrument year"}
            if anchor.year > rep_year:
                if transitional_rule_found:
                    return {"status":"TRANSITIONAL_REVIEW_REQUIRED","applicable":None,"status_at_tempus":"REPEALED_OR_TRANSITIONAL","reason":"case year follows repeal instrument year and transitional provision exists"}
                return {"status":"REVOKED_AT_TEMPUS","applicable":False,"status_at_tempus":"REVOKED","reason":"case year follows verified repeal instrument year"}
            return {"status":"TEMPUS_REQUIRES_EXACT_DATE","applicable":None,"status_at_tempus":"UNKNOWN","reason":"case date falls in the same year as the repeal instrument; exact repeal date required"}
        if transitional_rule_found:
            return {"status":"TRANSITIONAL_REVIEW_REQUIRED","applicable":None,"status_at_tempus":"UNKNOWN","reason":"source records repeal and transitional provision but repeal date is not verified"}
        return {"status":"REPEAL_DATE_REQUIRED","applicable":None,"status_at_tempus":"UNKNOWN","reason":"source records repeal but repeal date was not verified"}
    return {"status":"TEMPUS_VERIFIED","applicable":True,"status_at_tempus":"IN_FORCE","reason":"regulation was effective by the relevant case date"}

def final_applicability(*, official_source_confirmed: bool, text_retrieved: bool,
                        identity_confirmed: bool, legal_status: str,
                        tempus: dict, case_nexus_status: str = "CASE_NEXUS_UNCERTAIN",
                        provision_temporal_status: str = "NOT_APPLICABLE") -> str:
    if not official_source_confirmed or not text_retrieved or not identity_confirmed:
        return "UNVERIFIED"
    if case_nexus_status == "NO_CASE_NEXUS":
        return "VERIFIED_NOT_RELEVANT"
    if tempus.get("status") in {"NOT_YET_EFFECTIVE","REVOKED_AT_TEMPUS"}:
        return "VERIFIED_NOT_APPLICABLE"
    if tempus.get("status") == "TRANSITIONAL_REVIEW_REQUIRED":
        return "TRANSITIONAL_REVIEW_REQUIRED"
    if tempus.get("status") in {"REPEAL_DATE_REQUIRED","TEMPUS_UNVERIFIED","TEMPUS_REQUIRES_EXACT_DATE"}:
        return "POTENTIALLY_APPLICABLE"
    if legal_status not in {"IN_FORCE","AMENDED_IN_FORCE","REVOKED"}:
        return "STATUS_UNCERTAIN"
    if provision_temporal_status == "HISTORICAL_PROVISION_VERSION_REQUIRED":
        return "HISTORICAL_PROVISION_VERSION_REQUIRED"
    if tempus.get("status") == "TEMPUS_VERIFIED" and tempus.get("applicable") is True:
        if case_nexus_status == "CASE_NEXUS_VERIFIED":
            return "VERIFIED_APPLICABLE"
        return "POTENTIALLY_APPLICABLE"
    return "POTENTIALLY_APPLICABLE"


def evaluate_provision_temporal_version(*, amended: bool, amendment_years: Iterable[int],
                                        anchor_value: str | None, requested_count: int) -> dict:
    """Guard against verifying a current article text for an earlier legal era."""
    if not requested_count:
        return {"status":"NOT_APPLICABLE","reason":"no article-level provision requested"}
    if not amended:
        return {"status":"VERSION_CURRENT_SOURCE_ACCEPTED","reason":"official source does not expose an amendment marker"}
    years=sorted({int(y) for y in (amendment_years or []) if str(y).isdigit()})
    if not years:
        return {"status":"AMENDMENT_CHAIN_UNRESOLVED","reason":"source reports amendment but amendment timing was not extracted"}
    anchor=parse_id_date(anchor_value)
    anchor_year=anchor.year if anchor else (int(anchor_value) if re.fullmatch(r"\d{4}",str(anchor_value or "")) else None)
    if anchor_year is None:
        return {"status":"AMENDMENT_CHAIN_UNRESOLVED","reason":"no case year/date available for article-version comparison"}
    if any(y > anchor_year for y in years):
        return {"status":"HISTORICAL_PROVISION_VERSION_REQUIRED","reason":"at least one identified amendment post-dates the case anchor; current article text cannot prove the historical version"}
    return {"status":"AMENDMENT_CHAIN_PRE_DATES_ANCHOR","reason":"identified amendment years do not post-date the case anchor"}

def verify_document_candidate(candidate: dict, *, source_text: str, snapshot: dict) -> dict:
    meta=extract_status_metadata(source_text)
    identity_ok, identity=_identity_matches(candidate, source_text)
    anchor,anchor_type=choose_temporal_anchor(candidate,snapshot)
    tempus=verify_tempus(
        effective_date=meta.get("effective_date"), anchor_value=anchor,
        revoked=bool(meta.get("revoked")),
        transitional_rule_found=bool(meta.get("transitional_rule_found")),
        repeal_date=meta.get("repeal_date"), repeal_years=meta.get("repeal_years") or [],
    )
    case_nexus_status=str(candidate.get("case_nexus_status") or "CASE_NEXUS_UNCERTAIN")
    # Known regulation resolution is promoted only after the official document
    # identity is confirmed. This prevents a search-engine result from proving
    # its own relevance while still allowing exact, case-routed instruments to
    # become VERIFIED_APPLICABLE.
    binding_provenance=candidate.get('provision_binding_provenance') or {}
    requested_provisions=list(candidate.get("requested_provisions") or [])
    has_case_bound_provision=bool(
        binding_provenance.get('case_bound') and requested_provisions
    )
    deterministic_query_route=(
        candidate.get("query_origin") in {
            "KNOWN_REGULATION","EXACT_CASE_REGULATION","DOMAIN_RULE_REGULATION"
        }
        and bool(candidate.get("case_nexus_domains"))
    )
    # Nexus can be proven by either a deterministic domain/query route OR by a
    # provision that was already bound to this exact instrument from the case
    # source before retrieval.  The latter is stronger than query origin and
    # closes the last false-negative path where a generic search hit reached the
    # correct official statute but remained CASE_NEXUS_UNCERTAIN forever.
    if identity_ok and (deterministic_query_route or has_case_bound_provision):
        case_nexus_status="CASE_NEXUS_VERIFIED"
    provision_text_location=locate_provisions(
        requested_provisions, source_text, candidate.get("url")
    )
    # RC18 R11: keep two distinct states.  Text verification asks only whether
    # an explicitly requested provision is present in an identity-confirmed
    # official instrument.  Case-bound provision verification remains stricter
    # and still requires CASE_NEXUS_VERIFIED.
    if identity_ok:
        provision_text_verification=verify_provisions(
            requested_provisions, source_text, candidate.get("url"))
    elif requested_provisions:
        provision_text_verification={
            "status":"PROVISION_BLOCKED_BY_INSTRUMENT_IDENTITY",
            "requested":[normalize_provision_ref(x) for x in requested_provisions if normalize_provision_ref(x)],
            "verified":[],
            "unverified":[normalize_provision_ref(x) for x in requested_provisions if normalize_provision_ref(x)],
            "citations":[],"verified_count":0,
            "requested_count":len([x for x in requested_provisions if normalize_provision_ref(x)]),
            "gate_reason":"confirmed official instrument identity is required before article-text verification",
        }
    else:
        provision_text_verification=verify_provisions([], source_text, candidate.get("url"))

    if identity_ok and case_nexus_status == "CASE_NEXUS_VERIFIED":
        provision_verification=verify_provisions(
            requested_provisions, source_text, candidate.get("url"))
    elif requested_provisions:
        provision_verification={
            "status":"PROVISION_BLOCKED_BY_INSTRUMENT_GATE",
            "requested":[normalize_provision_ref(x) for x in requested_provisions if normalize_provision_ref(x)],
            "verified":[],
            "unverified":[normalize_provision_ref(x) for x in requested_provisions if normalize_provision_ref(x)],
            "citations":[],"verified_count":0,
            "requested_count":len([x for x in requested_provisions if normalize_provision_ref(x)]),
            "gate_reason":"instrument identity and CASE_NEXUS_VERIFIED are required before case-bound article verification",
        }
    else:
        provision_verification=verify_provisions([], source_text, candidate.get("url"))
    provision_temporal=evaluate_provision_temporal_version(
        amended=bool(meta.get("amended")), amendment_years=meta.get("amendment_years") or [],
        anchor_value=anchor, requested_count=int(provision_verification.get("requested_count") or 0),
    )
    final=final_applicability(
        official_source_confirmed=bool(candidate.get("authoritative")),
        text_retrieved=bool(source_text), identity_confirmed=identity_ok,
        legal_status=meta.get("legal_status") or "STATUS_UNCERTAIN", tempus=tempus,
        case_nexus_status=case_nexus_status,
        provision_temporal_status=provision_temporal.get("status") or "NOT_APPLICABLE",
    )
    return {
        "official_source_confirmed": bool(candidate.get("authoritative")),
        "text_retrieved": bool(source_text),
        "identity_confirmed": identity_ok,
        "identity": identity,
        "case_nexus_status": case_nexus_status,
        "provision_text_location": provision_text_location,
        "provision_text_verification": provision_text_verification,
        "provision_verification": provision_verification,
        **meta,
        "tempus_anchor": anchor,
        "tempus_anchor_type": anchor_type,
        "tempus_status": tempus.get("status"),
        "tempus_applicable": tempus.get("applicable"),
        "status_at_tempus": tempus.get("status_at_tempus"),
        "tempus_reason": tempus.get("reason"),
        "provision_temporal_version": provision_temporal,
        "final_status": final,
        "professional_verification": "PENDING",
    }
