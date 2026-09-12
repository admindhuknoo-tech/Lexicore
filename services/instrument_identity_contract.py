"""Cross-domain instrument identity contract for LexiCore.

This module is metadata-only and fail-closed on *explicit* contradictions.
It does not verify positive law and does not replace full-text identity checks.
Its job is to prevent a candidate from reaching exact verification when the
candidate is clearly a different instrument type/number-year/subject family.
"""
from __future__ import annotations

import re
from typing import Iterable

_KEY_RE = re.compile(
    r"^(UU|PP|PERPU|PERPPU|PERMA|SEMA|PERPRES|POJK|SEOJK|PKPU|PERDKPP|PERBAWASLU):([0-9]+[A-Za-z]?):((?:19|20)\d{2})$",
    re.I,
)

_TYPE_PATTERNS = (
    ("PERPU", r"^\s*(?:PERPPU|PERPU|Peraturan\s+Pemerintah\s+Pengganti\s+Undang[- ]Undang)\b"),
    ("PKPU", r"^\s*(?:PKPU|Peraturan\s+(?:Komisi\s+Pemilihan\s+Umum|KPU))\b"),
    ("PERDKPP", r"^\s*(?:Peraturan\s+DKPP|PERDKPP)\b"),
    ("PERBAWASLU", r"^\s*(?:Peraturan\s+Bawaslu|PERBAWASLU)\b"),
    ("POJK", r"^\s*(?:POJK|Peraturan\s+Otoritas\s+Jasa\s+Keuangan)\b"),
    ("SEOJK", r"^\s*(?:SEOJK|Surat\s+Edaran\s+Otoritas\s+Jasa\s+Keuangan)\b"),
    ("PERMA", r"^\s*(?:PERMA|Peraturan\s+Mahkamah\s+Agung)\b"),
    ("SEMA", r"^\s*(?:SEMA|Surat\s+Edaran\s+Mahkamah\s+Agung)\b"),
    ("PERPRES", r"^\s*(?:PERPRES|Peraturan\s+Presiden)\b"),
    ("PP", r"^\s*(?:PP|Peraturan\s+Pemerintah)\b"),
    ("UU", r"^\s*(?:UU|Undang[- ]Undang)\b"),
)

_SUBJECT_MARKERS = {
    "electoral_ethics": (
        "pemilihan umum", "pemilu", "pilkada", "pemilihan gubernur",
        "pemilihan bupati", "pemilihan walikota", "kpu", "bawaslu", "dkpp",
        "kode etik penyelenggara",
    ),
    "corruption": (
        "pemberantasan tindak pidana korupsi", "komisi pemberantasan tindak pidana korupsi",
        "tindak pidana korupsi", "tipikor", "kpk",
    ),
    "financial_services": (
        "perbankan", "bank perkreditan rakyat", "bank perekonomian rakyat", "bpr",
        "otoritas jasa keuangan",
    ),
    "employment": (
        "ketenagakerjaan", "hubungan industrial", "pemutusan hubungan kerja", "phk", "pkwt", "pkwtt",
    ),
    "civil_contract": (
        "kitab undang-undang hukum perdata", "kuhperdata", "burgerlijk wetboek",
        "wanprestasi", "perikatan", "perjanjian", "perbuatan melawan hukum",
    ),
    "land_property": ("agraria", "pendaftaran tanah", "hak atas tanah", "pertanahan"),
    "consumer": ("perlindungan konsumen",),
    "data_privacy": ("pelindungan data pribadi", "informasi dan transaksi elektronik"),
    "administrative": ("administrasi pemerintahan", "peradilan tata usaha negara", "ptun"),
}

_DOMAIN_COMPAT = {
    "electoral_ethics": {"electoral_ethics"},
    "corruption": {"corruption", "criminal"},
    "financial_services": {"financial_services"},
    "employment": {"employment"},
    "civil_contract": {"civil_contract", "civil_procedure"},
    "land_property": {"land_property", "civil_contract", "civil_procedure"},
    "consumer": {"consumer", "civil_contract", "civil_procedure"},
    "data_privacy": {"data_privacy", "criminal", "civil_contract"},
    "administrative": {"administrative"},
}


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def key_parts(key: str | None):
    m = _KEY_RE.fullmatch(str(key or "").strip())
    if not m:
        return None
    kind = m.group(1).upper().replace("PERPPU", "PERPU")
    return kind, m.group(2).upper(), m.group(3)


def _identity_from_structured_url(url: str | None) -> str | None:
    s = str(url or "")
    if not s:
        return None
    pats = (
        ("UU", r"(?:^|[/_-])uu-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])"),
        ("PP", r"(?:^|[/_-])pp-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])"),
        ("PERPU", r"(?:^|[/_-])(?:perpu|perppu)-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])"),
        ("PERPRES", r"(?:^|[/_-])perpres-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])"),
        ("PKPU", r"(?:^|[/_-])(?:pkpu|peraturan-kpu)-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])"),
    )
    for kind, pat in pats:
        m = re.search(pat, s, re.I)
        if m:
            return f"{kind}:{m.group(1).upper()}:{m.group(2)}"
    return None


def _leading_instrument_type(title: str | None) -> str | None:
    s = _clean(title)
    if not s:
        return None
    for kind, pat in _TYPE_PATTERNS:
        if re.search(pat, s, re.I):
            return kind
    return None


def _leading_identity_from_title(title: str | None) -> str | None:
    s = _clean(title)
    kind = _leading_instrument_type(s)
    if not kind:
        return None
    # The number/year must be bound near the leading instrument label; do not
    # scan the full title where referenced/amended instruments may appear.
    head = s[:180]
    if kind in {"PKPU", "PERDKPP", "PERBAWASLU"}:
        m = re.search(r"(?:Nomor|No\.?)\s*([0-9]+[A-Za-z]?)\s*(?:Tahun\s*)?((?:19|20)\d{2})", head, re.I)
        if not m:
            m = re.search(r"(?:Nomor|No\.?)\s*([0-9]+[A-Za-z]?)\s*/[^ ]*?/((?:19|20)\d{2})", head, re.I)
    else:
        m = re.search(r"(?:Nomor|No\.?)\s*([0-9]+[A-Za-z]?)\s*Tahun\s*((?:19|20)\d{2})", head, re.I)
        if not m:
            m = re.search(r"\b([0-9]+[A-Za-z]?)\s*/\s*((?:19|20)\d{2})\b", head, re.I)
    if not m:
        return None
    return f"{kind}:{m.group(1).upper()}:{m.group(2)}"


def candidate_primary_identity(row: dict) -> str | None:
    return _identity_from_structured_url(row.get("url")) or _leading_identity_from_title(row.get("title"))


def subject_families(value: str | None) -> set[str]:
    low = _clean(value).lower()
    return {family for family, markers in _SUBJECT_MARKERS.items() if any(m in low for m in markers)}


def _registry_subject_text(expected_key: str | None) -> str:
    if not expected_key:
        return ""
    try:
        from regulatory_db import get_all_regulations
        from services.positive_law_verification import regulation_identity
    except Exception:
        return ""
    for reg in get_all_regulations() or []:
        title = " ".join(str(reg.get(k) or "") for k in ("nomor", "tentang")).strip()
        if str(regulation_identity(title).get("key") or "").upper() == str(expected_key).upper():
            return title
    return ""


def evaluate_instrument_identity_contract(
    expected_key: str | None,
    row: dict,
    *,
    expected_text: str | None = None,
    active_domains: Iterable[str] | None = None,
    phase: str = "PREFETCH",
    official_text: str | None = None,
) -> dict:
    """Evaluate the two-stage instrument identity contract.

    PREFETCH is deliberately structural only: an explicit instrument-type or
    number/year contradiction is a hard reject, while subject/domain signals
    are diagnostic and may not suppress an otherwise correct statute before
    official text is retrieved.

    POSTFETCH runs only after official text is available.  At that stage an
    explicit subject-family/domain contradiction in the official text can fail
    closed.  Unknown semantic metadata still remains neutral.
    """
    exp = key_parts(expected_key)
    if not exp:
        return {"passed": True, "status": "NO_EXPECTED_IDENTITY", "reason": "no canonical expected identity"}

    exp_type, exp_num, exp_year = exp
    cand_key = candidate_primary_identity(row)
    cand = key_parts(cand_key)
    cand_type = cand[0] if cand else _leading_instrument_type(row.get("title"))

    type_match = None if not cand_type else (cand_type == exp_type)
    number_year_match = None
    if cand:
        number_year_match = (cand[1] == exp_num and cand[2] == exp_year)

    expected_subject_text = " ".join(filter(None, [expected_text, _registry_subject_text(expected_key)]))
    phase=str(phase or "PREFETCH").upper()
    candidate_subject_text = " ".join(str(row.get(k) or "") for k in ("title", "description", "snippet", "summary"))
    if phase == "POSTFETCH" and official_text:
        candidate_subject_text = " ".join(filter(None, [candidate_subject_text, str(official_text)[:12000]]))
    expected_families = subject_families(expected_subject_text)
    candidate_families = subject_families(candidate_subject_text)
    subject_family_match = None
    if expected_families and candidate_families:
        subject_family_match = bool(expected_families & candidate_families)

    domains = {str(x) for x in (active_domains or []) if x}
    domain_compatible = None
    if candidate_families and domains:
        compat = set().union(*(_DOMAIN_COMPAT.get(f, {f}) for f in candidate_families))
        domain_compatible = bool(compat & domains)

    hard_reasons = []
    semantic_reasons = []
    if type_match is False:
        hard_reasons.append("INSTRUMENT_TYPE_MISMATCH")
    if number_year_match is False:
        hard_reasons.append("NUMBER_YEAR_MISMATCH")
    if subject_family_match is False:
        semantic_reasons.append("SUBJECT_FAMILY_MISMATCH")
    if domain_compatible is False:
        semantic_reasons.append("DOMAIN_INCOMPATIBLE")

    # R35 two-stage contract: semantic metadata must never create a pre-fetch
    # false negative.  It becomes a hard gate only after official text exists.
    reasons=list(hard_reasons)
    if phase == "POSTFETCH":
        reasons.extend(semantic_reasons)
    passed = not reasons
    return {
        "passed": passed,
        "phase": phase,
        "status": "PASS" if passed else reasons[0],
        "reason": ",".join((reasons + [r for r in semantic_reasons if r not in reasons])) if (reasons or semantic_reasons) else "no explicit identity-contract contradiction",
        "semantic_warnings": semantic_reasons,
        "expected_key": expected_key,
        "candidate_primary_key": cand_key,
        "expected_type": exp_type,
        "candidate_type": cand_type,
        "type_match": type_match,
        "number_year_match": number_year_match,
        "expected_families": sorted(expected_families),
        "candidate_families": sorted(candidate_families),
        "subject_family_match": subject_family_match,
        "active_domains": sorted(domains),
        "domain_compatible": domain_compatible,
    }
