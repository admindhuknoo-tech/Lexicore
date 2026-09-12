"""SAL v1.0 Single Source of Truth Governor — Positive-Allow Enforcement.

This module is the mandatory data boundary between semantic admission and
reasoning consumers.  Raw source is audit-only.  Downstream consumers may read
only closed pools compiled here and must possess a route token for the target
consumer.  There is no legacy/raw fallback.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set, Tuple

from services.contract_enforcer import LexiCoreContractEnforcer
from retrieval.search_router import LexiCoreLawRetrievalRouter

EVIDENCE_CONSUMER = "Evidence Map"
ALLEGED_ACT_CONSUMER = "Alleged Act"
ISSUE_CONSUMER = "Issue"
LAW_CONSUMER = "Candidate Law"
SUMMARY_FACT_CONSUMER = "Summary Facts"
SUMMARY_ACTION_CONSUMER = "Summary Actions"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _statement_text(row: Dict[str, Any]) -> str:
    return _clean(row.get("statement") or row.get("evidence") or row.get("text") or row.get("text_payload"))


def _sal(row: Dict[str, Any]) -> Dict[str, Any]:
    value = row.get("sal_contract")
    return value if isinstance(value, dict) else {}


def _sal_text(row: Dict[str, Any]) -> str:
    sal = _sal(row)
    return _clean(sal.get("text_payload") or _statement_text(row))


def _token_for(row: Dict[str, Any]) -> Dict[str, Any]:
    sal = _sal(row)
    adm = sal.get("admission_contract") or {}
    env = sal.get("semantic_envelope") or {}
    adv = LexiCoreContractEnforcer.adversarial_context_from_payload(sal)
    return {
        "statement_id": sal.get("statement_id"),
        "semantic_type": env.get("semantic_type"),
        "speaker_role": adv.get("speaker_role"),
        "position": adv.get("position"),
        "stance": adv.get("stance"),
        "epistemic_status": adv.get("epistemic_status"),
        "admissibility_state": adm.get("admissibility_state", "REJECTED"),
        "allowed_consumers": list(adm.get("restricted_routes") or []),
        "prohibited_consumers": list(adm.get("prohibited_routes") or []),
        "positive_allow_status": "UNASSESSED",
    }


def _pool_row(row: Dict[str, Any], idx: int) -> Dict[str, Any]:
    sal = _sal(row)
    env = sal.get("semantic_envelope") or {}
    adm = sal.get("admission_contract") or {}
    adv = LexiCoreContractEnforcer.adversarial_context_from_payload(sal)
    return {
        **row,
        "source_index": row.get("source_index", idx),
        "statement_id": sal.get("statement_id"),
        "semantic_type": env.get("semantic_type"),
        "speaker_role": adv.get("speaker_role"),
        "position": adv.get("position"),
        "stance": adv.get("stance"),
        "epistemic_status": adv.get("epistemic_status"),
        "admissibility_state": adm.get("admissibility_state"),
        "allowed_consumers": list(adm.get("restricted_routes") or []),
        "prohibited_consumers": list(adm.get("prohibited_routes") or []),
    }


# Positive semantic proof for an alleged act requires an actor + concrete act,
# not merely a remedy/object/evidence label.
_ACTOR_RE = re.compile(
    r"\b(?:saya|kami|dia|ia|terdakwa|tersangka|penggugat|tergugat|pemohon|termohon|"
    r"debitur|kreditur|direktur|komisaris|pejabat|pegawai|saksi|ahli|pihak\s+(?:pertama|kedua)|"
    r"[A-Z][A-Za-zÀ-ÿ.'-]+(?:\s+[A-Z][A-Za-zÀ-ÿ.'-]+){0,3})\b",
    re.I,
)
_ACT_RE = re.compile(
    r"\b(?:membayar|menerima|menyerahkan|menandatangani|menyetujui|memutuskan|mengalihkan|"
    r"menguasai|mengambil|mengirim|mentransfer|memberikan|menolak|menghentikan|melakukan|"
    r"menggunakan|menjual|membeli|meminjam|meminjamkan|mencairkan|mengajukan|mengubah|"
    r"menghapus|memerintahkan|menyimpan|mengembalikan|tidak\s+membayar|belum\s+membayar|"
    r"tidak\s+memenuhi|gagal\s+memenuhi|melanggar|menyalahgunakan|melampaui)\b",
    re.I,
)
_REMEDY_OBJECT_RE = re.compile(
    r"^\s*(?:ganti\s+rugi|pengembalian\s+(?:pinjaman|uang|barang)|pembayaran\s+ganti\s+rugi|"
    r"pemulihan\s+hak|pembatalan|permohonan|petitum|tuntutan|bukti\s+\w+|surat\s+\w+)",
    re.I,
)
_PAST_PRESENT_CUES = re.compile(
    r"\b(?:telah|sudah|pernah|sedang|sekarang|pada\s+tanggal|tanggal\s+\d|tahun\s+\d{4}|"
    r"tidak\s+pernah|belum\s+membayar|masih\s+belum)\b",
    re.I,
)
_FUTURE_CUES = re.compile(r"\b(?:akan|hendak|berencana|rencana|minggu\s+depan|bulan\s+depan|apabila|jika|bila)\b", re.I)


def _actor_act_positive_proof(row: Dict[str, Any]) -> Tuple[bool, str]:
    """Require positive actor + concrete past/present act proof for Alleged Act."""
    text = _sal_text(row)
    sal = _sal(row)
    env = sal.get("semantic_envelope") or {}
    st = str(env.get("semantic_type") or "")
    modality = str(env.get("modality_temporality") or "").upper()
    if st != "FACT_ASSERTION":
        return False, "ALLEGED_ACT_REQUIRES_FACT_ASSERTION"
    if not text or _REMEDY_OBJECT_RE.search(text):
        return False, "ALLEGED_ACT_REMEDY_OBJECT_NOT_ACT"
    if "FUTURE" in modality or _FUTURE_CUES.search(text):
        return False, "ALLEGED_ACT_FUTURE_NOT_CURRENT_ACT"
    actor_ok = bool(_ACTOR_RE.search(text))
    act_ok = bool(_ACT_RE.search(text))
    temporal_ok = bool(_PAST_PRESENT_CUES.search(text)) or not _FUTURE_CUES.search(text)
    if not actor_ok:
        return False, "ALLEGED_ACT_ACTOR_UNPROVEN"
    if not act_ok:
        return False, "ALLEGED_ACT_CONCRETE_ACT_UNPROVEN"
    if not temporal_ok:
        return False, "ALLEGED_ACT_TEMPORALITY_UNPROVEN"
    return True, "POSITIVE_ACTOR_ACT_PROOF"


# Subject-matter family registry used only for admission alignment.  It does not
# decide substantive applicability; downstream law verification still owns
# identity/status/tempus/provision validation.
_DOMAIN_FAMILIES = {
    "civil_contract": {
        "perdata", "perikatan", "kontrak", "wanprestasi", "cidera janji", "utang", "hutang", "pinjaman", "somasi"
    },
    "civil_procedure": {"hukum acara perdata", "hir", "rbg", "rv", "perma", "sema", "kompetensi relatif", "kompetensi absolut"},
    "civil_tort": {"perbuatan melawan hukum", "pmh", "tort"},
    "criminal": {"pidana", "kuhp", "tersangka", "terdakwa", "penyidikan", "penuntutan"},
    "corruption": {"tipikor", "korupsi", "pemberantasan tindak pidana korupsi", "kerugian keuangan negara", "suap", "gratifikasi"},
    "banking": {"perbankan", "bank", "bpr", "kredit", "debitur", "ojk", "pojk", "seojk"},
    "land_property": {"pertanahan", "agraria", "tanah", "bpn", "sertipikat", "sertifikat", "skpt"},
    "religious_court": {"peradilan agama", "waris", "ahli waris", "perkawinan", "perceraian"},
    "employment": {"ketenagakerjaan", "hubungan industrial", "pekerja", "buruh", "phk", "alih daya", "outsourcing", "penyerahan sebagian pelaksanaan pekerjaan"},
    "mining": {"pertambangan", "minerba", "izin usaha pertambangan", "iup", "mining"},
    "ip": {"hki", "kekayaan intelektual", "hak cipta", "merek", "paten", "lisensi"},
    "corporate": {"perseroan", "direksi", "komisaris", "rups", "pemegang saham", "korporasi"},
    "bankruptcy": {"kepailitan", "pkpu", "pailit", "penundaan kewajiban pembayaran utang"},
    "administrative": {"ptun", "tata usaha negara", "aaupb", "upaya administratif"},
}
_DOMAIN_ALIASES = {
    "civil_contract": "civil_contract", "perdata": "civil_contract", "hukum_kontrak": "civil_contract",
    "civil_procedure": "civil_procedure", "hukum_acara_perdata": "civil_procedure",
    "civil_tort": "civil_tort", "pmh": "civil_tort",
    "criminal": "criminal", "pidana_umum": "criminal",
    "corruption": "corruption", "pidana_khusus": "corruption",
    "financial_services": "banking", "perbankan": "banking",
    "land_property": "land_property", "pertanahan": "land_property",
    "religious_court": "religious_court", "keluarga_waris": "religious_court",
    "employment": "employment", "ketenagakerjaan": "employment",
    "corporate": "corporate", "administrative": "administrative",
    "hki": "ip", "ip": "ip", "pertambangan": "mining", "mining": "mining",
    "bankruptcy": "bankruptcy", "kepailitan": "bankruptcy",
}


def _families_from_text(text: str) -> Set[str]:
    low = _clean(text).lower()
    found: Set[str] = set()
    for family, markers in _DOMAIN_FAMILIES.items():
        if any(marker in low for marker in markers):
            found.add(family)
    return found


def _case_families(result: Dict[str, Any]) -> Set[str]:
    dc = result.get("domain_contract") or result.get("domain_classification") or {}
    found: Set[str] = set()
    if isinstance(dc, dict):
        values = [dc.get("primary_domain"), dc.get("ranah_hukum"), dc.get("posture")]
        values += list(dc.get("domain_contract") or [])
    else:
        values = [dc]
    for value in values:
        norm = _clean(value).lower().replace(" ", "_")
        if norm in _DOMAIN_ALIASES:
            found.add(_DOMAIN_ALIASES[norm])
        found |= _families_from_text(_clean(value))
    found |= _families_from_text(_clean(result.get("source_text"))[:20000])
    return found




def _active_law_policy_domains(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Project the case-domain contract into the retrieval policy shape.

    This is a final candidate-law admission guard only.  It never changes the
    case-domain classifier and never marks a norm applicable.
    """
    dc = result.get("domain_contract") or result.get("domain_classification") or {}
    if not isinstance(dc, dict):
        return []
    domains = dc.get("domains") or []
    if isinstance(domains, list) and any(isinstance(x, dict) for x in domains):
        return [dict(x) for x in domains if isinstance(x, dict) and x.get("id")]
    ids = dc.get("domain_contract") or []
    if not isinstance(ids, list):
        ids = []
    supporting = set(dc.get("supporting_only") or [])
    return [
        {"id": str(x), "role": "SUPPORTING_ONLY" if str(x) in supporting else "SECONDARY"}
        for x in ids if str(x).strip()
    ]


def _final_candidate_law_policy(result: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    """Re-evaluate candidate-law relevance at the SSoT boundary.

    Retrieval normally attaches ``law_weight_policy`` before verification, but
    historical/verified rows may be reconstructed without that metadata.  The
    canonical Candidate Law pool therefore performs one final fail-closed
    institutional-mismatch check using candidate-owned title/text only.

    Exact case citations remain available in the regulatory snapshot for
    identity/provision audit.  A hard institutional mismatch, however, may not
    become governing-law material merely because it was fetched or verified.
    """
    existing = row.get("law_weight_policy")
    domains = _active_law_policy_domains(result)
    probe = dict(row)
    source = _clean(row.get("source") or row.get("title") or row.get("citation"))
    probe.setdefault("title", source)
    probe.setdefault("initial_vector_score", 1.0)
    try:
        decision = LexiCoreLawRetrievalRouter().evaluate_candidate(probe, domains)
    except Exception:
        decision = {}

    # Preserve an upstream explicit rejection even if the re-evaluation cannot
    # load the config.  Otherwise use the fresh decision to recover metadata
    # lost by older reconstruction paths.
    if isinstance(existing, dict) and existing.get("status") == "REJECTED_SUBJECT_MATTER_UNPROVEN":
        return existing
    if decision.get("hard_drop_reasons"):
        return decision
    if isinstance(existing, dict) and existing:
        return existing
    return decision


def _law_rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in result.get("applicable_law") or []:
        if isinstance(item, dict):
            source = _clean(item.get("source") or item.get("regulation") or item.get("qualified_citation") or item.get("title"))
            if source:
                rows.append({**item, "source": source, "origin": item.get("origin") or "applicable_law"})
        else:
            source = _clean(item)
            if source:
                rows.append({"source": source, "status": "UNVERIFIED", "domain": "", "origin": "applicable_law"})
    snap = result.get("case_regulatory_snapshot") or {}
    for item in snap.get("official_results") or []:
        if not isinstance(item, dict):
            continue
        source = _clean(item.get("title") or item.get("citation") or item.get("source"))
        if not source:
            continue
        ver = item.get("positive_law_verification") or {}
        pv = ver.get("provision_verification") or {}
        rows.append({
            "source": source,
            "status": _clean(ver.get("final_status") or item.get("status") or "UNVERIFIED").upper(),
            "domain": _clean(item.get("domain")),
            "provisions": list(pv.get("verified") or []),
            "identity_confirmed": ver.get("identity_confirmed"),
            "case_nexus_status": ver.get("case_nexus_status") or item.get("case_nexus_status"),
            "tempus_status": ver.get("tempus_status"),
            "tempus_applicable": ver.get("tempus_applicable"),
            "query_origin": item.get("query_origin"),
            "candidate_role": item.get("candidate_role"),
            "law_weight_policy": item.get("law_weight_policy"),
            "candidate_law_eligible": item.get("candidate_law_eligible"),
            "provision_binding_provenance": item.get("provision_binding_provenance"),
            "origin": "official_results",
        })
    for item in result.get("regulatory_matches") or []:
        if not isinstance(item, dict):
            continue
        source = _clean(item.get("title") or item.get("citation") or item.get("source") or item.get("regulation"))
        if source:
            rows.append({**item, "source": source, "status": _clean(item.get("status") or "UNVERIFIED").upper(), "origin": "regulatory_matches"})
    out: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = (_clean(row.get("source")).lower(), _clean(row.get("domain")).lower())
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _positive_law_compatibility(row: Dict[str, Any], case_families: Set[str]) -> Tuple[bool, str, Set[str]]:
    blob = " ".join([_clean(row.get("source")), _clean(row.get("domain")), " ".join(map(str, row.get("provisions") or []))])
    law_families = _families_from_text(blob)
    # Explicit domain metadata is positive proof too.
    domain_norm = _clean(row.get("domain")).lower().replace(" ", "_")
    if domain_norm in _DOMAIN_ALIASES:
        law_families.add(_DOMAIN_ALIASES[domain_norm])
    if not law_families:
        return False, "REJECTED_SUBJECT_MATTER_UNPROVEN", law_families
    if not case_families:
        return False, "REJECTED_CASE_SUBJECT_MATTER_UNPROVEN", law_families
    compatible = set(law_families) & set(case_families)
    # Civil procedure can support civil merits matters only when the case is civil.
    if "civil_procedure" in law_families and case_families & {"civil_contract", "civil_tort", "land_property", "religious_court"}:
        compatible.add("civil_procedure")
    # Banking may be contextual in corruption involving bank credit, but not the governing offence law.
    if "banking" in law_families and "corruption" in case_families and "banking" in case_families:
        compatible.add("banking")
    if not compatible:
        return False, "REJECTED_SUBJECT_MATTER_UNPROVEN", law_families
    return True, "POSITIVE_SUBJECT_MATTER_COMPATIBILITY_PROVEN", law_families


def build_governed_pools(result: Dict[str, Any]) -> Dict[str, Any]:
    """Compile all positive-allow pools and authoritative route-token ledger."""
    ledger = result.get("source_ledger") or []
    evidence_pool: List[Dict[str, Any]] = []
    alleged_pool: List[Dict[str, Any]] = []
    issue_basis_pool: List[Dict[str, Any]] = []
    audit_pool: List[Dict[str, Any]] = []
    action_pool: List[Dict[str, Any]] = []
    summary_fact_pool: List[str] = []
    summary_action_pool: List[str] = []
    route_ledger: Dict[str, Dict[str, Any]] = {}
    law_citation_domains: Set[str] = set()

    prepared: List[Tuple[int, Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
    for idx, raw in enumerate(ledger):
        if not isinstance(raw, dict):
            continue
        sal = _sal(raw)
        if not sal:
            continue
        sal = LexiCoreContractEnforcer.enforce_routing(sal)
        row = dict(raw)
        row["sal_contract"] = sal
        token = _token_for(row)
        sid = token.get("statement_id")
        if not sid:
            continue
        prepared.append((idx, row, sal, token))
        env = sal.get("semantic_envelope") or {}
        if env.get("semantic_type") == "LAW_CITATION":
            law_citation_domains |= _families_from_text(_sal_text(row) + " " + _clean(env.get("domain_posture")))

    # Active clash exists only where an admitted current proposition and a source
    # law citation share a subject-matter family.  Future actions can never create it.
    for idx, row, sal, token in prepared:
        env = sal.get("semantic_envelope") or {}
        st = str(env.get("semantic_type") or "")
        state = str((sal.get("admission_contract") or {}).get("admissibility_state") or "REJECTED")
        pooled = _pool_row(row, idx)
        text = _sal_text(row)
        stmt_families = _families_from_text(text + " " + _clean(env.get("domain_posture")))
        allowed = set(token.get("allowed_consumers") or [])
        prohibited = set(token.get("prohibited_consumers") or [])

        # Evidence: positive proof = PRIMARY_EVIDENCE + producer route.
        if st == "PRIMARY_EVIDENCE" and state == "ADMITTED" and LexiCoreContractEnforcer.route_allowed(sal, EVIDENCE_CONSUMER):
            evidence_pool.append(pooled)
        else:
            prohibited.add(EVIDENCE_CONSUMER)
            allowed.discard(EVIDENCE_CONSUMER)

        # Alleged act: positive proof = FACT_ASSERTION + actor + concrete past/current act.
        act_ok, act_reason = _actor_act_positive_proof(row)
        if act_ok and LexiCoreContractEnforcer.route_allowed(sal, ALLEGED_ACT_CONSUMER):
            alleged_pool.append(pooled)
            epistemic = str(token.get("epistemic_status") or "UNSPECIFIED")
            if not epistemic.startswith("UNVERIFIED_PROSECUTION_ALLEGATION") and not epistemic.startswith("UNVERIFIED_DEFENSE_REBUTTAL"):
                summary_fact_pool.append(text)
        else:
            prohibited.add(ALLEGED_ACT_CONSUMER)
            allowed.discard(ALLEGED_ACT_CONSUMER)
            token["alleged_act_rejection_reason"] = act_reason

        # Primary evidence may also support governed factual summary, while a
        # mere document reference/evidence claim never does.
        if st == "PRIMARY_EVIDENCE" and state == "ADMITTED":
            if text and text not in summary_fact_pool:
                summary_fact_pool.append(text)

        # Current Issue: positive clash only, never future/pre-litigation plan alone.
        if st in {"FACT_ASSERTION", "PARTY_ARGUMENT"} and state in {"ADMITTED", "LIMITED"} and ISSUE_CONSUMER in allowed:
            if stmt_families & law_citation_domains:
                issue_basis_pool.append(pooled)
            else:
                prohibited.add(ISSUE_CONSUMER)
                allowed.discard(ISSUE_CONSUMER)
                token["issue_rejection_reason"] = "REJECTED_UNPROVEN_NO_SAME_DOMAIN_LAW_CLASH"
        else:
            allowed.discard(ISSUE_CONSUMER)

        if state in {"LEAD_ONLY", "LIMITED"} and LexiCoreContractEnforcer.route_allowed(sal, "Document Audit"):
            audit_pool.append(pooled)
        if LexiCoreContractEnforcer.route_allowed(sal, "Action Plan"):
            action_pool.append(pooled)
            if text:
                summary_action_pool.append(text)

        token["allowed_consumers"] = sorted(allowed)
        token["prohibited_consumers"] = sorted(prohibited)
        token["positive_allow_status"] = "ADMITTED_TO_ONE_OR_MORE_POOLS" if any(
            sid == x.get("statement_id") for x in evidence_pool + alleged_pool + issue_basis_pool
        ) else "REJECTED_UNPROVEN_OR_RESTRICTED"
        route_ledger[sid] = token

    case_families = _case_families(result)
    law_pool: List[Dict[str, Any]] = []
    rejected_laws: List[Dict[str, Any]] = []
    for row in _law_rows(result):
        policy = _final_candidate_law_policy(result, row)
        hard_drop = list(policy.get("hard_drop_reasons") or []) if isinstance(policy, dict) else []
        explicit_eligible = row.get("candidate_law_eligible")
        if explicit_eligible is False or hard_drop:
            rejected_laws.append({
                **row,
                "law_weight_policy": policy or row.get("law_weight_policy"),
                "sal_subject_matter_status": "REJECTED_SUBJECT_MATTER_UNPROVEN",
                "sal_subject_matter_reason": hard_drop[0] if hard_drop else "RETRIEVAL_POLICY_REJECTED",
                "sal_subject_matter_families": sorted(_families_from_text(_clean(row.get("source")))),
            })
            continue
        # Upstream retrieval rejection is authoritative for non-exact discovery.
        if isinstance(policy, dict) and policy.get("status") == "REJECTED_SUBJECT_MATTER_UNPROVEN" and str(row.get("query_origin") or "").upper() != "EXACT_CASE_REGULATION":
            rejected_laws.append({
                **row,
                "law_weight_policy": policy,
                "sal_subject_matter_status": "REJECTED_SUBJECT_MATTER_UNPROVEN",
                "sal_subject_matter_reason": "RETRIEVAL_POSITIVE_NEXUS_UNPROVEN",
                "sal_subject_matter_families": sorted(_families_from_text(_clean(row.get("source")))),
            })
            continue
        ok, reason, law_families = _positive_law_compatibility(row, case_families)
        if ok:
            law_pool.append({
                **row,
                "sal_subject_matter_status": "ADMITTED",
                "sal_subject_matter_reason": reason,
                "sal_subject_matter_families": sorted(law_families),
            })
        else:
            rejected_laws.append({
                **row,
                "sal_subject_matter_status": "REJECTED_SUBJECT_MATTER_UNPROVEN",
                "sal_subject_matter_reason": reason,
                "sal_subject_matter_families": sorted(law_families),
            })

    dc = result.get("domain_contract") or result.get("domain_classification") or {}
    pools = {
        "orchestration_status": "ENFORCED",
        "policy": "SAL_V1_POSITIVE_ALLOW_SINGLE_SOURCE_OF_TRUTH_NO_RAW_FALLBACK",
        "case_domain": _clean((dc or {}).get("primary_domain") if isinstance(dc, dict) else dc) or "UNKNOWN",
        "case_domain_families": sorted(case_families),
        "evidence_map_pool": evidence_pool,
        "alleged_act_pool": alleged_pool,
        "current_issue_source_pool": issue_basis_pool,
        "candidate_law_pool": law_pool,
        "isolated_document_audit_pool": audit_pool,
        "action_plan_pool": action_pool,
        "summary_fakta_kunci_pool": summary_fact_pool,
        "summary_rencana_tindakan_pool": summary_action_pool,
        "rejected_law_pool": rejected_laws,
        "route_token_ledger": route_ledger,
        "current_issue_admission": "ADMITTED" if issue_basis_pool else "REJECTED_UNPROVEN_NO_ACTIVE_CLASH",
        "constraints": {
            "raw_source_direct_access": "PROHIBITED_FOR_REASONING_CONSUMERS",
            "fallback_to_original_candidates": "PROHIBITED",
            "consumer_without_route_token": "BLOCKED_ROUTE_CONTRACT",
            "empty_evidence_pool_behavior": "EVIDENCE_MISSING",
            "empty_alleged_act_pool_behavior": "ALLEGED_ACT_MISSING",
            "empty_current_issue_pool_behavior": "CURRENT_ISSUE_MISSING",
            "empty_candidate_law_pool_behavior": "APPLICABLE_LAW_MISSING",
            "law_admission_policy": "POSITIVE_SUBJECT_MATTER_PROOF_REQUIRED",
        },
    }
    result["sal_governed_pools"] = pools
    result["sal_single_source_of_truth"] = True
    return pools


def enforce_governed_consumers(result: Dict[str, Any]) -> Dict[str, Any]:
    """Lock Issue Builder and governed executive-summary inputs to SSoT pools."""
    pools = result.get("sal_governed_pools") or build_governed_pools(result)
    if pools.get("orchestration_status") != "ENFORCED":
        return result
    if not pools.get("current_issue_source_pool"):
        if result.get("legal_issues"):
            result["potential_legal_issues_pre_sal"] = list(result.get("legal_issues") or [])
        result["legal_issues"] = []
        result["current_issue_gate"] = "BLOCKED_ROUTE_CONTRACT"
    else:
        result["current_issue_gate"] = "POSITIVE_ALLOW_ADMITTED"
    result["governed_executive_summary_data"] = {
        "Fakta Kunci": list(pools.get("summary_fakta_kunci_pool") or []),
        "Rencana Tindakan": list(pools.get("summary_rencana_tindakan_pool") or []),
    }
    return result


def governed_summary_lines(result: Dict[str, Any]) -> List[str]:
    """Exporter-safe executive summary using only positive-allow pools."""
    pools = result.get("sal_governed_pools") or {}
    facts = [_clean(x) for x in pools.get("summary_fakta_kunci_pool") or [] if _clean(x)]
    actions = [_clean(x) for x in pools.get("summary_rencana_tindakan_pool") or [] if _clean(x)]
    issues = [_clean(x) for x in result.get("legal_issues") or [] if _clean(x)]
    out: List[str] = []
    if facts:
        out.append("Fakta kunci: " + "; ".join(facts[:4]))
    else:
        out.append("Fakta kunci: belum ada FACT_ASSERTION/PRIMARY_EVIDENCE yang lolos Positive-Allow SAL sebagai fakta kunci.")
    if issues:
        out.append("Isu utama: " + "; ".join(issues[:3]))
    else:
        out.append("Isu utama: belum ada current issue yang lolos active-clash admission SAL.")
    if actions:
        out.append("Rencana tindakan: " + "; ".join(actions[:5]))
    return out


def route_token_allows(result: Dict[str, Any], row: Dict[str, Any], consumer: str) -> bool:
    pools = result.get("sal_governed_pools") or {}
    if pools.get("orchestration_status") != "ENFORCED":
        return False
    sid = row.get("statement_id")
    if not sid:
        sal = _sal(row)
        sid = sal.get("statement_id") if sal else None
    token = (pools.get("route_token_ledger") or {}).get(sid)
    if not token:
        return False
    return consumer in set(token.get("allowed_consumers") or []) and consumer not in set(token.get("prohibited_consumers") or [])


def pool_for_consumer(result: Dict[str, Any], consumer: str) -> List[Dict[str, Any]]:
    pools = result.get("sal_governed_pools") or {}
    mapping = {
        "Evidence Map": "evidence_map_pool",
        "Alleged Act": "alleged_act_pool",
        "Issue": "current_issue_source_pool",
        "Candidate Law": "candidate_law_pool",
        "Document Audit": "isolated_document_audit_pool",
        "Action Plan": "action_plan_pool",
    }
    key = mapping.get(consumer)
    if not key or pools.get("orchestration_status") != "ENFORCED":
        return []
    return list(pools.get(key) or [])
