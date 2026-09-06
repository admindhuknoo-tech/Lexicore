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


def _reg_identity(text: str) -> dict:
    """Extract only explicit regulation number/year identity from source text."""
    s=re.sub(r"\s+", " ", text or "")
    patterns=(
        ("UU", r"(?:Undang-Undang|Undang undang|UU)(?:\s*\(UU\))?\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("PP", r"(?:Peraturan Pemerintah|PP)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("PERMA", r"(?:Peraturan Mahkamah Agung|PERMA)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("SEMA", r"(?:Surat Edaran Mahkamah Agung|SEMA)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
        ("PERPRES", r"(?:Peraturan Presiden|PERPRES)\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*(\d+[A-Za-z]?)\s+Tahun\s+(\d{4})"),
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
    "land_property": ("agraria", "pertanahan", "pendaftaran tanah", "sertipikat", "sertifikat", "hak milik", "uupa", "bpn"),
    "religious_court": ("peradilan agama", "pengadilan agama", "kompetensi absolut", "kewenangan absolut", "waris", "wakaf"),
    "civil_procedure": ("acara perdata", "eksepsi", "obscuur", "plurium", "gugatan", "hir", "rbg", "rv", "perma", "sema"),
    "civil_contract": ("kuhperdata", "burgerlijk", "perikatan", "perjanjian", "wanprestasi", "perbuatan melawan hukum", "1365"),
    "administrative": ("ptun", "tata usaha negara", "administrasi pemerintahan", "aaupb"),
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

def _identity_matches(candidate: dict, source_text: str) -> tuple[bool, dict]:
    # Exact retrieval query is the requested instrument identity.  Prefer it
    # over a search-result title because official search engines often return
    # amendment/referencing documents whose title mentions another statute.
    expected=_reg_identity(candidate.get("query") or "")
    if not expected.get("key"):
        expected=_reg_identity(candidate.get("title") or "")
    actual=_reg_identity(source_text)
    if not expected.get("key"):
        return False, actual

    kind=expected.get("type")
    number=re.escape(str(expected.get("number") or ""))
    year=str(expected.get("year") or "")
    kind_patterns={
        "UU":r"(?:Undang-Undang|Undang undang|UU)",
        "PP":r"(?:Peraturan Pemerintah|PP)",
        "PERMA":r"(?:Peraturan Mahkamah Agung|PERMA)",
        "SEMA":r"(?:Surat Edaran Mahkamah Agung|SEMA)",
        "PERPRES":r"(?:Peraturan Presiden|PERPRES)",
    }
    lead=kind_patterns.get(kind)
    if lead and re.search(lead+r"(?:\s*\([^)]*\))?\s+(?:Republik Indonesia\s+)?(?:Nomor|No\.?)\s*"+number+r"\s+Tahun\s+"+year, source_text or "", re.I):
        return True, expected
    return expected.get("key") == actual.get("key"), actual


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


def extract_status_metadata(source_text: str) -> dict:
    """Extract explicit status metadata from an official result/detail page.

    This intentionally understands common JDIH/BPK labels, but never infers a
    repeal/amendment from chronology alone.
    """
    text=re.sub(r"\s+", " ", source_text or "").strip()
    low=text.lower()
    effective=_first_date_after(text, (
        "Tanggal Berlaku", "Tanggal mulai berlaku", "Berlaku mulai",
        "mulai berlaku pada tanggal", "mulai berlaku sejak",
        "berlaku pada tanggal", "berlaku sejak",
    ))
    promulgation=_first_date_after(text, ("Diundangkan pada tanggal", "diundangkan tanggal"))
    enactment=_first_date_after(text, ("Ditetapkan pada tanggal", "ditetapkan tanggal"))

    revoked=bool(re.search(r"\b(?:dicabut dengan|dinyatakan tidak berlaku|tidak berlaku lagi|status(?: peraturan)?\s*:?\s*tidak berlaku)\b", low, re.I))
    amended=bool(re.search(r"\b(?:diubah dengan|perubahan atas|telah diubah)\b", low, re.I))
    transitional=bool(re.search(r"\bketentuan peralihan\b", low, re.I))
    explicit_in_force=bool(effective) or bool(re.search(r"\bberlaku mulai\b|\bmulai berlaku\b|\bstatus(?: peraturan)?\s*:?\s*berlaku\b", low, re.I))

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
        "amended": amended,
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
    if snapshot.get("procedural_date_candidate"):
        # This is only a fallback anchor; it does not become a substantive date.
        return str(snapshot.get("procedural_date_candidate")), "PROCEDURAL_DATE_FALLBACK"
    return None, "UNKNOWN_DATE"


def verify_tempus(*, effective_date: str | None, anchor_value: str | None,
                  revoked: bool, transitional_rule_found: bool) -> dict:
    if not anchor_value:
        return {"status":"TEMPUS_UNVERIFIED","applicable":None,"reason":"case temporal anchor not established"}
    eff=parse_id_date(effective_date)
    if not eff:
        return {"status":"TEMPUS_UNVERIFIED","applicable":None,"reason":"effective date not verified from official source"}

    anchor=parse_id_date(anchor_value)
    if not anchor and re.fullmatch(r"\d{4}", str(anchor_value)):
        year=int(anchor_value)
        if eff.year > year:
            return {"status":"NOT_YET_EFFECTIVE","applicable":False,"reason":"regulation effective year is after case anchor year"}
        if eff.year < year and not revoked:
            return {"status":"TEMPUS_VERIFIED","applicable":True,"reason":"regulation was effective before case anchor year"}
        return {"status":"TEMPUS_REQUIRES_EXACT_DATE","applicable":None,"reason":"same-year screening requires exact case date"}
    if not anchor:
        return {"status":"TEMPUS_UNVERIFIED","applicable":None,"reason":"case temporal anchor could not be parsed"}
    if anchor < eff:
        return {"status":"NOT_YET_EFFECTIVE","applicable":False,"reason":"case date predates regulation effective date"}
    if revoked:
        if transitional_rule_found:
            return {"status":"TRANSITIONAL_REVIEW_REQUIRED","applicable":None,"reason":"source records repeal/non-force marker and a transitional provision"}
        return {"status":"REVOKED_STATUS_REQUIRES_REPEAL_DATE","applicable":None,"reason":"source records repeal/non-force marker but repeal date was not verified"}
    return {"status":"TEMPUS_VERIFIED","applicable":True,"reason":"regulation was effective by the relevant case date"}


def final_applicability(*, official_source_confirmed: bool, text_retrieved: bool,
                        identity_confirmed: bool, legal_status: str,
                        tempus: dict, case_nexus_status: str = "CASE_NEXUS_UNCERTAIN") -> str:
    if not official_source_confirmed or not text_retrieved or not identity_confirmed:
        return "UNVERIFIED"
    if case_nexus_status == "NO_CASE_NEXUS":
        return "VERIFIED_NOT_RELEVANT"
    if tempus.get("status") == "NOT_YET_EFFECTIVE":
        return "VERIFIED_NOT_APPLICABLE"
    if legal_status == "REVOKED":
        return "TRANSITIONAL_REVIEW_REQUIRED" if tempus.get("status") == "TRANSITIONAL_REVIEW_REQUIRED" else "STATUS_UNCERTAIN"
    if legal_status not in {"IN_FORCE","AMENDED_IN_FORCE"}:
        return "STATUS_UNCERTAIN"
    if tempus.get("status") == "TEMPUS_VERIFIED" and tempus.get("applicable") is True:
        if case_nexus_status == "CASE_NEXUS_VERIFIED":
            return "VERIFIED_APPLICABLE"
        return "POTENTIALLY_APPLICABLE"
    if tempus.get("status") == "TRANSITIONAL_REVIEW_REQUIRED":
        return "TRANSITIONAL_REVIEW_REQUIRED"
    return "POTENTIALLY_APPLICABLE"

def verify_document_candidate(candidate: dict, *, source_text: str, snapshot: dict) -> dict:
    meta=extract_status_metadata(source_text)
    identity_ok, identity=_identity_matches(candidate, source_text)
    anchor,anchor_type=choose_temporal_anchor(candidate,snapshot)
    tempus=verify_tempus(
        effective_date=meta.get("effective_date"), anchor_value=anchor,
        revoked=bool(meta.get("revoked")),
        transitional_rule_found=bool(meta.get("transitional_rule_found")),
    )
    case_nexus_status=str(candidate.get("case_nexus_status") or "CASE_NEXUS_UNCERTAIN")
    # Known regulation resolution is promoted only after the official document
    # identity is confirmed. This prevents a search-engine result from proving
    # its own relevance while still allowing exact, case-routed instruments to
    # become VERIFIED_APPLICABLE.
    if identity_ok and candidate.get("query_origin") == "KNOWN_REGULATION" and candidate.get("case_nexus_domains"):
        case_nexus_status="CASE_NEXUS_VERIFIED"
    requested_provisions=list(candidate.get("requested_provisions") or [])
    # Instrument-before-article gate: an article number is meaningless until
    # the official instrument identity and its case nexus are established.
    # This prevents Pasal 18/Pasal 3 in unrelated statutes from being counted
    # as legal support merely because the number happens to match.
    if identity_ok and case_nexus_status == "CASE_NEXUS_VERIFIED":
        provision_verification=verify_provisions(
            requested_provisions,
            source_text,
            candidate.get("url"),
        )
    elif requested_provisions:
        provision_verification={
            "status":"PROVISION_BLOCKED_BY_INSTRUMENT_GATE",
            "requested":[normalize_provision_ref(x) for x in requested_provisions if normalize_provision_ref(x)],
            "verified":[],
            "unverified":[normalize_provision_ref(x) for x in requested_provisions if normalize_provision_ref(x)],
            "citations":[],"verified_count":0,
            "requested_count":len([x for x in requested_provisions if normalize_provision_ref(x)]),
            "gate_reason":"instrument identity and CASE_NEXUS_VERIFIED are required before article verification",
        }
    else:
        provision_verification=verify_provisions([], source_text, candidate.get("url"))
    final=final_applicability(
        official_source_confirmed=bool(candidate.get("authoritative")),
        text_retrieved=bool(source_text), identity_confirmed=identity_ok,
        legal_status=meta.get("legal_status") or "STATUS_UNCERTAIN", tempus=tempus,
        case_nexus_status=case_nexus_status,
    )
    return {
        "official_source_confirmed": bool(candidate.get("authoritative")),
        "text_retrieved": bool(source_text),
        "identity_confirmed": identity_ok,
        "identity": identity,
        "case_nexus_status": case_nexus_status,
        "provision_verification": provision_verification,
        **meta,
        "tempus_anchor": anchor,
        "tempus_anchor_type": anchor_type,
        "tempus_status": tempus.get("status"),
        "tempus_applicable": tempus.get("applicable"),
        "tempus_reason": tempus.get("reason"),
        "final_status": final,
        "professional_verification": "PENDING",
    }
