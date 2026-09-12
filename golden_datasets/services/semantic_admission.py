"""LexiCore SAL v1.0 — Universal Semantic Admission Contract.

This is an upstream data gate, not a substantive law engine.  It classifies
source statements and restricts which downstream nodes may consume them.  The
contract is fail-closed: malformed or ambiguous payloads are isolated in
Document Audit and can never be upgraded by a downstream component.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover - production fail-safe handles absence
    Draft202012Validator = None

SEMANTIC_TYPES = {
    "FACT_ASSERTION", "DOCUMENT_REFERENCE", "PARTY_ARGUMENT", "COUNTER_ARGUMENT",
    "QUESTION", "FUTURE_ACTION", "EVIDENCE_CLAIM", "PRIMARY_EVIDENCE",
    "LAW_CITATION", "LEGAL_OPINION", "METADATA",
}

OFFICIAL_NODES = {
    "Case Readiness", "Evidence Map", "Candidate Law", "Regulation/Tempus",
    "Norm Conflict", "Legal Construction", "Legal Elements", "Alleged Act",
    "Element Test", "Causation", "Risk", "Procedural/Merits", "Action Plan",
    "Document Audit", "Issue",
}
AUXILIARY_NODES = {"Counter-Evidence", "Evidence Lead", "Interrogation Context", "NONE"}
ALL_ROUTES = OFFICIAL_NODES | AUXILIARY_NODES
PROOF_ROUTES = {"Evidence Map", "Case Readiness"}
LAW_ROUTES = {"Candidate Law", "Regulation/Tempus", "Norm Conflict"}

_FUTURE = re.compile(r"\b(?:akan|hendak|berencana|rencana|perlu\s+(?:menyiapkan|mengajukan|melakukan|mendapatkan)|menyiapkan|mempersiapkan|memberikan\s+somasi|mengajukan\s+gugatan|dilanjutkan\s+mediasi|apabila\s+tidak\s+berhasil|jika\s+tidak\s+berhasil|tindak\s+lanjut)\b", re.I)
_QUESTION = re.compile(r"^\s*(?:apakah|apa|kapan|siapa|mengapa|kenapa|bagaimana|benarkah|bukankah|diperlihatkan\s+kepada\s+saudara|pertanyaan)\b|\?\s*$", re.I)
_LAW = re.compile(r"\b(?:pasal\s+\d+|undang[- ]undang|\buu\s*(?:no\.?|nomor)?\s*\d+|peraturan\s+(?:pemerintah|menteri|mahkamah|otoritas|daerah)|perma\b|sema\b|pojk\b|seojk\b|hir\b|rbg\b|yurisprudensi\b|klausul\s+\d+)\b", re.I)
_DOC_REF = re.compile(r"\b(?:surat|akta|sertipikat|sertifikat|kuitansi|kwitansi|bukti\s+transfer|rekening koran|perjanjian|kontrak|bpkb|faktur|skpt|surat kuasa|laporan audit|dokumen)\b", re.I)
_SHORT_EVIDENCE_REFERENCE = re.compile(r"^\s*bukti\s+[A-Za-zÀ-ÿ0-9_/().-]+(?:\s+[A-Za-zÀ-ÿ0-9_/().-]+){0,5}\s*$", re.I)
_EVIDENCE_CLAIM = re.compile(r"\b(?:saya|kami|penggugat|tergugat|tersangka|saksi|pemohon|termohon)\s+(?:memiliki|menyerahkan|melampirkan|mengajukan|membawa)\s+(?:bukti|dokumen|surat|akta|kuitansi|rekaman)\b", re.I)
_COUNTER = re.compile(r"\b(?:membantah|menyangkal|menolak\s+dalil|tidak\s+benar|eksepsi|sanggahan|counter|keberatan)\b", re.I)
_LEGAL_OPINION = re.compile(r"\b(?:menurut\s+(?:kami|hemat|pendapat)|berpendapat|secara hukum|dapat ditafsirkan|seharusnya|patut dinilai|kami menilai)\b", re.I)
_PARTY_ARG = re.compile(r"\b(?:mendalilkan|menyatakan\s+bahwa|menuduh|mengklaim|menuntut|memohon|beralasan|menurut\s+penggugat|menurut\s+tergugat|menurut\s+tersangka)\b", re.I)
_METADATA = re.compile(r"^\s*(?:nomor|no\.?|tanggal|nama|nip|nik|alamat|jabatan|tempat|hal|perihal|lampiran|kepada\s+yth|judul)\s*[:\-]", re.I)
_PRIMARY_DATA = re.compile(r"\b(?:saldo|mutasi|debit|kredit|nominal|jumlah|rp\.?\s*[0-9]|ditransfer|dibayarkan|ditandatangani|tercatat|terbit|bernomor)\b", re.I)

_DOMAIN_RULES = {
    "HKI": ("hak cipta", "merek", "paten", "lisensi", "kekayaan intelektual", "desain industri"),
    "HUKUM_KONTRAK": ("wanprestasi", "cidera janji", "utang", "hutang", "pinjaman", "perjanjian", "kontrak", "somasi", "prestasi"),
    "PIDANA_KHUSUS": ("tipikor", "korupsi", "kerugian keuangan negara", "gratifikasi", "suap"),
    "PIDANA_UMUM": ("tersangka", "terdakwa", "penyidikan", "pidana", "dakwaan"),
    "PERTANAHAN": ("sertipikat", "sertifikat hak", "tanah", "bpn", "skpt", "agraria"),
    "KETENAGAKERJAAN": ("phk", "pekerja", "buruh", "upah", "hubungan industrial"),
    "ADMINISTRASI": ("ptun", "keputusan tata usaha negara", "aaupb", "upaya administratif"),
    "KELUARGA_WARIS": ("waris", "ahli waris", "pewaris", "perceraian", "perkawinan"),
    "KORPORASI": ("perseroan", "rups", "komisaris", "pemegang saham", "direksi"),
    "PERBANKAN": ("bpr", "bank", "kredit", "debitur", "agunan", "ojk"),
    "PERTAMBANGAN": ("pertambangan", "izin usaha pertambangan", "iup", "minerba", "mining"),
}


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _statement_id(text: str, index: int = 0, prefix: str = "GEN") -> str:
    digest = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:10].upper()
    return f"SAL_CONTRACT_{prefix.upper()}_{index:04d}_{digest}"


def _domain_from_text(text: str, domain_contract: Dict[str, Any] | None = None) -> str:
    low = _clean(text).lower()
    hits = []
    for name, markers in _DOMAIN_RULES.items():
        score = sum(1 for marker in markers if marker in low)
        if score:
            hits.append((score, name))
    if hits:
        hits.sort(reverse=True)
        return hits[0][1]
    dc = domain_contract or {}
    primary = str(dc.get("primary_domain") or "").lower()
    mapping = {
        "civil_contract": "HUKUM_KONTRAK", "corruption": "PIDANA_KHUSUS", "criminal": "PIDANA_UMUM",
        "financial_services": "PERBANKAN", "land_property": "PERTANAHAN", "employment": "KETENAGAKERJAAN",
        "administrative": "ADMINISTRASI", "religious_court": "KELUARGA_WARIS", "corporate": "KORPORASI",
    }
    return mapping.get(primary, "GENERAL_LEGAL")


def _provenance(source_item: Dict[str, Any] | None, posture: str = "") -> str:
    item = source_item or {}
    explicit = _clean(item.get("provenance") or item.get("speaker") or item.get("source_role"))
    if explicit:
        return explicit
    label = _clean(item.get("label")).upper()
    if label in {"ALLEGATION", "PLEADING ASSERTION"}:
        return "PARTY_PLEADING"
    if label in {"DENIAL / LIMITATION", "COUNTER_ARGUMENT"}:
        return "OPPOSING_PARTY"
    if "BAP" in posture.upper():
        return "BAP_SOURCE_UNATTRIBUTED"
    return "SOURCE_DOCUMENT"


def _modality(text: str, semantic_type: str) -> str:
    low = text.lower()
    if semantic_type == "QUESTION": return "INTERROGATIVE_UNCERTAIN"
    if semantic_type == "FUTURE_ACTION":
        return "FUTURE_CONDITIONAL" if any(x in low for x in ("apabila", "jika", "bila")) else "FUTURE_PLANNED"
    if semantic_type in {"PARTY_ARGUMENT", "COUNTER_ARGUMENT", "EVIDENCE_CLAIM"}: return "ASSERTED_UNVERIFIED"
    if re.search(r"\b(?:diduga|dugaan|diperkirakan|kemungkinan)\b", low): return "ALLEGED_OR_UNCERTAIN"
    if re.search(r"\b(?:apabila|jika|bila)\b", low): return "CONDITIONAL"
    return "ASSERTED"


def classify_semantic_type(text: str, source_item: Dict[str, Any] | None = None) -> str:
    """Assign exactly one semantic type using fail-closed precedence."""
    s = _clean(text)
    low = s.lower()
    item = source_item or {}
    label = _clean(item.get("label")).upper()
    source_class = _clean(item.get("source_classification") or item.get("display_classification")).upper()

    if _QUESTION.search(s): return "QUESTION"
    if _FUTURE.search(s): return "FUTURE_ACTION"
    if _METADATA.search(s) or source_class in {"DOCUMENT_METADATA", "PROCEDURAL_METADATA", "PARTY_IDENTITY", "DOCUMENT_STRUCTURE"}: return "METADATA"
    if label == "DENIAL / LIMITATION" or source_class == "LEGAL_ARGUMENT" and _COUNTER.search(s) or _COUNTER.search(s): return "COUNTER_ARGUMENT"
    if _EVIDENCE_CLAIM.search(s): return "EVIDENCE_CLAIM"
    if label == "ALLEGATION" or source_class in {"PLEADED_FACT", "PLEADING_ASSERTION", "ALLEGED_ROLE"} or _PARTY_ARG.search(s): return "PARTY_ARGUMENT"
    if _LEGAL_OPINION.search(s): return "LEGAL_OPINION"
    if _LAW.search(s): return "LAW_CITATION"
    # Only treat content as PRIMARY_EVIDENCE when upstream provenance expressly
    # marks an actual evidentiary artefact; a BAP/pleading being a primary source
    # does not make each sentence primary evidence.
    if source_class == "ACTUAL_EVIDENTIARY_ITEM" and _PRIMARY_DATA.search(s): return "PRIMARY_EVIDENCE"
    if (_DOC_REF.search(s) and (len(s.split()) <= 16 or re.search(r"\b(?:adanya|terdapat|berupa|dokumen)\b", low))) or _SHORT_EVIDENCE_REFERENCE.match(s):
        return "DOCUMENT_REFERENCE"
    return "FACT_ASSERTION"


def _routing_for(semantic_type: str, text: str) -> Tuple[str, List[str], List[str], str, str]:
    all_non_none = sorted(ALL_ROUTES - {"NONE"})
    if semantic_type == "QUESTION":
        return "REJECTED", ["Interrogation Context"], [r for r in all_non_none if r != "Interrogation Context"], "QUESTION_NOT_FACT_OR_EVIDENCE", "RETAIN_AS_CONTEXT"
    if semantic_type == "FUTURE_ACTION":
        return "REJECTED", ["Action Plan"], [r for r in all_non_none if r != "Action Plan"], "FUTURE_ACTION_NOT_HISTORICAL_PROOF", "ROUTE_AS_PROSPECTIVE_ACTION_ONLY"
    if semantic_type == "DOCUMENT_REFERENCE":
        return "LEAD_ONLY", ["Document Audit", "Evidence Lead"], ["Evidence Map", "Case Readiness", "Legal Elements", "Element Test", "Causation"], "REFERENCE_REQUIRES_PRIMARY_ARTEFACT", "VERIFY_REFERENCED_ARTEFACT"
    if semantic_type == "EVIDENCE_CLAIM":
        return "LEAD_ONLY", ["Evidence Lead", "Document Audit"], ["Evidence Map", "Case Readiness", "Element Test", "Causation"], "EVIDENCE_CLAIM_IS_NOT_EVIDENCE", "VERIFY_CLAIMED_EVIDENCE_ARTEFACT"
    if semantic_type == "PARTY_ARGUMENT":
        return "LIMITED", ["Issue", "Alleged Act", "Element Test"], ["Evidence Map", "Case Readiness"], "PARTY_ARGUMENT_UNVERIFIED", "MAP_AS_UNVERIFIED_ARGUMENT"
    if semantic_type == "COUNTER_ARGUMENT":
        return "LIMITED", ["Counter-Evidence", "Element Test", "Issue"], ["Evidence Map", "Case Readiness"], "COUNTER_ARGUMENT_NOT_COUNTER_EVIDENCE", "MAP_AS_COUNTER_ARGUMENT_ONLY"
    if semantic_type == "PRIMARY_EVIDENCE":
        return "ADMITTED", ["Evidence Map", "Case Readiness", "Element Test"], [], "PRIMARY_EVIDENCE_REQUIRES_PROPOSITION_COMPATIBILITY", "EXECUTE_PROPOSITION_COMPATIBILITY_CHECK"
    if semantic_type == "LAW_CITATION":
        return "LIMITED", ["Candidate Law", "Regulation/Tempus", "Norm Conflict"], ["Evidence Map", "Case Readiness", "Alleged Act"], "LAW_REQUIRES_DOMAIN_TEMPUS_STATUS_GATES", "EXECUTE_LAW_ADMISSION_GATES"
    if semantic_type == "LEGAL_OPINION":
        return "LIMITED", ["Legal Construction"], ["Candidate Law", "Evidence Map", "Case Readiness"], "LEGAL_OPINION_NOT_POSITIVE_LAW", "USE_AS_INTERPRETIVE_MATERIAL_ONLY"
    if semantic_type == "METADATA":
        return "LIMITED", ["Document Audit", "Regulation/Tempus", "Procedural/Merits"], ["Evidence Map", "Alleged Act", "Legal Elements"], "METADATA_CONTEXT_ONLY", "USE_FOR_PROVENANCE_POSTURE_OR_ADMIN_TEMPUS"
    # FACT_ASSERTION is admissible as a factual proposition, not automatically proof.
    return "LIMITED", ["Issue", "Alleged Act", "Case Readiness"], ["Evidence Map"], "FACT_ASSERTION_REQUIRES_EVIDENTIARY_CORROBORATION", "ROUTE_AS_UNVERIFIED_FACT_PROPOSITION"


def build_statement_contract(text: str, *, index: int = 0, prefix: str = "GEN", source_item: Dict[str, Any] | None = None,
                             domain_contract: Dict[str, Any] | None = None, posture: str = "") -> Dict[str, Any]:
    s = _clean(text)
    st = classify_semantic_type(s, source_item)
    state, allowed, prohibited, rationale, directive = _routing_for(st, s)
    domain = _domain_from_text(s, domain_contract)
    posture_value = _clean(posture or (domain_contract or {}).get("posture") or "UNKNOWN")
    payload = {
        "statement_id": _statement_id(s, index, prefix),
        "text_payload": s,
        "semantic_envelope": {
            "semantic_type": st,
            "provenance": _provenance(source_item, posture_value),
            "modality_temporality": _modality(s, st),
            "domain_posture": f"{domain} / {posture_value}",
        },
        "admission_contract": {
            "admissibility_state": state,
            "restricted_routes": allowed,
            "prohibited_routes": prohibited,
            "rationale": rationale,
        },
        "downstream_migration": {
            "primary_target_node": allowed[0] if allowed else "NONE",
            "next_execution_directive": directive,
        },
    }
    from services.contract_enforcer import LexiCoreContractEnforcer
    payload = LexiCoreContractEnforcer.enforce_routing(payload)
    return validate_and_route_sal_payload(payload, s)


def _schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas" / "LexiCore-SAL-v1.0.json"


def _builtin_contract_validation(payload: Dict[str, Any]) -> None:
    """Portable deterministic validator for the frozen SAL envelope.

    jsonschema remains the authoritative production validator when installed.
    This fallback enforces the immutable fields/enums/routes so a portable or
    air-gapped LexiCore installation does not collapse every valid statement
    into SYSTEM_CRITICAL_FALLBACK merely because the optional validator package
    is absent.
    """
    if not isinstance(payload, dict):
        raise TypeError("SAL_PAYLOAD_NOT_OBJECT")
    required_top = {"statement_id", "text_payload", "semantic_envelope", "admission_contract", "downstream_migration"}
    if set(payload) != required_top:
        raise ValueError("SAL_TOP_LEVEL_SCHEMA_MISMATCH")
    if not re.fullmatch(r"SAL_CONTRACT_[A-Z0-9_]+", str(payload.get("statement_id") or "")):
        raise ValueError("SAL_STATEMENT_ID_INVALID")
    if not isinstance(payload.get("text_payload"), str) or not payload["text_payload"].strip():
        raise ValueError("SAL_TEXT_PAYLOAD_INVALID")

    env = payload.get("semantic_envelope")
    if not isinstance(env, dict) or set(env) != {"semantic_type", "provenance", "modality_temporality", "domain_posture"}:
        raise ValueError("SAL_SEMANTIC_ENVELOPE_SCHEMA_MISMATCH")
    if env.get("semantic_type") not in SEMANTIC_TYPES:
        raise ValueError("SAL_SEMANTIC_TYPE_INVALID")
    for key in ("provenance", "modality_temporality", "domain_posture"):
        if not isinstance(env.get(key), str) or not env[key].strip():
            raise ValueError(f"SAL_{key.upper()}_INVALID")

    adm = payload.get("admission_contract")
    if not isinstance(adm, dict) or set(adm) != {"admissibility_state", "restricted_routes", "prohibited_routes", "rationale"}:
        raise ValueError("SAL_ADMISSION_CONTRACT_SCHEMA_MISMATCH")
    if adm.get("admissibility_state") not in {"ADMITTED", "LIMITED", "LEAD_ONLY", "REJECTED"}:
        raise ValueError("SAL_ADMISSIBILITY_STATE_INVALID")
    for key in ("restricted_routes", "prohibited_routes"):
        routes = adm.get(key)
        if not isinstance(routes, list) or any(r not in ALL_ROUTES for r in routes) or len(routes) != len(set(routes)):
            raise ValueError(f"SAL_{key.upper()}_INVALID")
    if not isinstance(adm.get("rationale"), str) or not adm["rationale"].strip():
        raise ValueError("SAL_RATIONALE_INVALID")

    dm = payload.get("downstream_migration")
    if not isinstance(dm, dict) or set(dm) != {"primary_target_node", "next_execution_directive"}:
        raise ValueError("SAL_DOWNSTREAM_SCHEMA_MISMATCH")
    if dm.get("primary_target_node") not in ALL_ROUTES:
        raise ValueError("SAL_PRIMARY_TARGET_INVALID")
    if not isinstance(dm.get("next_execution_directive"), str) or not dm["next_execution_directive"].strip():
        raise ValueError("SAL_NEXT_DIRECTIVE_INVALID")


def validate_payload(payload: Dict[str, Any]) -> None:
    # Authoritative schema validation when the dependency is available.
    if Draft202012Validator is not None:
        schema = json.loads(_schema_path().read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)
    else:
        _builtin_contract_validation(payload)

    allowed = set(payload["admission_contract"]["restricted_routes"])
    prohibited = set(payload["admission_contract"]["prohibited_routes"])
    if allowed & prohibited:
        raise ValueError("SAL_ROUTE_CONFLICT")
    primary = payload["downstream_migration"]["primary_target_node"]
    if allowed and primary not in allowed:
        raise ValueError("SAL_PRIMARY_TARGET_NOT_ALLOWED")
    if not allowed and primary != "NONE":
        raise ValueError("SAL_PRIMARY_TARGET_REQUIRES_ROUTE")


def isolated_payload(text_source: str, *, reason: str = "SAL_CONTRACT_VALIDATION_ERROR") -> Dict[str, Any]:
    text = _clean(text_source) or "[EMPTY_SOURCE_FRAGMENT]"
    prohibited = sorted(ALL_ROUTES - {"Document Audit", "NONE"})
    return {
        "statement_id": _statement_id(text, 0, "FALLBACK_ERR"),
        "text_payload": text,
        "semantic_envelope": {
            "semantic_type": "METADATA",
            "provenance": "SYSTEM_CRITICAL_FALLBACK",
            "modality_temporality": "UNKNOWN_SUSPECTED",
            "domain_posture": "SYSTEM_ISOLATION / UNKNOWN",
        },
        "admission_contract": {
            "admissibility_state": "LEAD_ONLY",
            "restricted_routes": ["Document Audit"],
            "prohibited_routes": prohibited,
            "rationale": f"AIR_GAP_FAIL_SAFE: {reason}. Source isolated from reasoning nodes.",
        },
        "downstream_migration": {
            "primary_target_node": "Document Audit",
            "next_execution_directive": "FORCE_MANUAL_PROFESSIONAL_VERIFICATION",
        },
    }


def validate_and_route_sal_payload(raw: Any, text_source: str) -> Dict[str, Any]:
    try:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
        validate_payload(payload)
        return payload
    except Exception as exc:
        fallback = isolated_payload(text_source, reason=type(exc).__name__)
        # The fallback itself is deliberately simple and must satisfy the same schema.
        if Draft202012Validator is not None:
            validate_payload(fallback)
        return fallback


def segment_source_text(source_text: str, limit: int = 220) -> List[str]:
    """Conservative segmentation preserving source wording without semantic synthesis."""
    text = str(source_text or "").replace("\r", "\n")
    chunks = []
    for raw in re.split(r"(?:\n{1,}|(?<=[.!?;])\s+(?=[A-ZÀ-Ý0-9]))", text):
        s = _clean(raw)
        if len(s) < 3:
            continue
        # Split only long enumerations; never paraphrase.
        if len(s) > 900:
            parts = [_clean(x) for x in re.split(r"\s+(?=\d+[.)]\s+)", s) if _clean(x)]
        else:
            parts = [s]
        chunks.extend(parts)
        if len(chunks) >= limit:
            break
    return chunks[:limit]


def build_sal_contract(source_text: str, *, domain_contract: Dict[str, Any] | None = None, posture: str = "", prefix: str = "DOC") -> Dict[str, Any]:
    statements = []
    for idx, statement in enumerate(segment_source_text(source_text)):
        statements.append(build_statement_contract(statement, index=idx, prefix=prefix, domain_contract=domain_contract, posture=posture))
    counts: Dict[str, int] = {}
    state_counts: Dict[str, int] = {}
    retrieval_parts = []
    for p in statements:
        st = p["semantic_envelope"]["semantic_type"]
        state = p["admission_contract"]["admissibility_state"]
        counts[st] = counts.get(st, 0) + 1
        state_counts[state] = state_counts.get(state, 0) + 1
        # Retrieval may use legal citations, facts and arguments; never future actions,
        # questions, recommendations, or bare references as subject-matter seeds.
        if st in {"FACT_ASSERTION", "PARTY_ARGUMENT", "COUNTER_ARGUMENT", "LAW_CITATION", "LEGAL_OPINION", "PRIMARY_EVIDENCE"} and state != "REJECTED":
            retrieval_parts.append(p["text_payload"])
    return {
        "contract_version": "SAL-1.0",
        "contract_status": "PASS",
        "statements": statements,
        "semantic_type_counts": counts,
        "admissibility_counts": state_counts,
        "retrieval_text": "\n".join(retrieval_parts)[:60000],
        "air_gap_policy": "FAIL_CLOSED_DOCUMENT_AUDIT_ONLY",
    }


def enrich_source_ledger_with_sal(ledger: Iterable[Dict[str, Any]], *, domain_contract: Dict[str, Any] | None = None, posture: str = "") -> List[Dict[str, Any]]:
    out = []
    for idx, item in enumerate(ledger or []):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        text = _clean(row.get("statement") or row.get("evidence"))
        if not text:
            continue
        sal = build_statement_contract(text, index=idx, prefix="LEDGER", source_item=row, domain_contract=domain_contract, posture=posture)
        row["sal_contract"] = sal
        row["sal_semantic_type"] = sal["semantic_envelope"]["semantic_type"]
        row["sal_admissibility_state"] = sal["admission_contract"]["admissibility_state"]
        row["sal_allowed_routes"] = sal["admission_contract"]["restricted_routes"]
        out.append(row)
    return out


def route_allowed(item: Dict[str, Any], route: str) -> bool:
    sal = item.get("sal_contract") or {}
    if sal:
        from services.contract_enforcer import LexiCoreContractEnforcer
        return LexiCoreContractEnforcer.route_allowed(sal, route)
    return True  # backward compatibility for legacy rows not yet enriched


def law_subject_matter_admissible(source: str, *, case_domains: Iterable[str] = (), issue_text: str = "", case_text: str = "") -> Tuple[bool, str]:
    """Early subject-matter admission gate; never decides legal validity/applicability."""
    from services.contract_enforcer import LexiCoreContractEnforcer
    _, ok, reason = LexiCoreContractEnforcer.enforce_law_admission(
        {"source": source}, case_domains=case_domains, issue_text=issue_text, case_text=case_text
    )
    return ok, reason
