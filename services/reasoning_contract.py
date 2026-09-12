"""Cross-layer contract for LexiCore's auditable legal reasoning pipeline.

Any producer/consumer that changes the legal reasoning shape must migrate this
contract across service, API persistence, benchmark, UI, and exporters.
"""
from __future__ import annotations

from typing import Any, Dict

from services.legal_reasoning_chain import build_reasoning_chain

CONTRACT_VERSION = "2.3.1"
CONTRACT_STAGES = (
    "issue",
    "applicable_law",
    "legal_elements",
    "alleged_act",
    "evidence",
    "counter_evidence",
    "element_test",
    "causation",
    "risk",
    "procedural_merits_classification",
    "recommended_action",
)


def validate_reasoning_contract(chain: Dict[str, Any] | None) -> Dict[str, Any]:
    """Validate structure *and* semantic lineage of the canonical chain.

    Missing law/evidence/act is permitted when it is represented explicitly as a
    fail-closed status. What is not permitted is silent context drift: a stage
    must remain bound to the same issue/element lineage as the preceding stage.
    """
    chain = chain or {}
    rows = [r for r in chain.get("chains") or [] if isinstance(r, dict)]
    violations = []
    semantic_holds = []
    hard_semantic_violations = []
    for idx, row in enumerate(rows, 1):
        chain_id = row.get("chain_id") or f"E{idx}"
        missing = [stage for stage in CONTRACT_STAGES if stage not in row]
        if missing:
            violations.append({"chain_id": chain_id, "kind": "MISSING_STAGE", "missing_stages": missing})
            continue

        # Every stage is a typed envelope carrying an explicit status. This lets
        # the contract distinguish "missing but visible" from silent omission.
        for stage in CONTRACT_STAGES:
            envelope = row.get(stage)
            if not isinstance(envelope, dict):
                violations.append({"chain_id": chain_id, "kind": "UNTYPED_STAGE", "stage": stage})
                continue
            if not str(envelope.get("status") or "").strip():
                violations.append({"chain_id": chain_id, "kind": "MISSING_STAGE_STATUS", "stage": stage})

        binding = row.get("binding_context") or {}
        if not binding.get("issue_key") or not binding.get("element_key"):
            violations.append({"chain_id": chain_id, "kind": "MISSING_BINDING_CONTEXT"})
        elif binding.get("chain_id") != chain_id:
            violations.append({"chain_id": chain_id, "kind": "BINDING_CHAIN_MISMATCH"})

        owner_domain=str(binding.get("owner_domain") or "").strip()
        law_selected=(row.get("applicable_law") or {}).get("selected") or {}
        if owner_domain and law_selected:
            from services.legal_reasoning_chain import _domain_compatible
            if not _domain_compatible(owner_domain, str(law_selected.get("domain") or ""), str(law_selected.get("source") or "")):
                hard_semantic_violations.append({"chain_id":chain_id,"stage":"applicable_law","status":"DOMAIN_LINEAGE_VIOLATION"})
        owner_issue=str((row.get("legal_elements") or {}).get("owner_issue_id") or "").strip()
        if binding.get("owner_issue_id") and owner_issue and binding.get("owner_issue_id") != owner_issue:
            hard_semantic_violations.append({"chain_id":chain_id,"stage":"legal_elements","status":"ELEMENT_OWNERSHIP_VIOLATION"})

        issue_text=str((row.get('issue') or {}).get('value') or '').lower()
        element_text=str((row.get('legal_elements') or {}).get('element') or '').lower()
        if 'tempus' in issue_text and 'kausal' in element_text:
            hard_semantic_violations.append({"chain_id":chain_id,"stage":"legal_elements","status":"ISSUE_ELEMENT_MISMATCH_TEMPUS_CAUSATION"})
        law_blob=' '.join([str(law_selected.get('source') or ''), str(law_selected.get('domain') or '')]).lower() if isinstance(law_selected,dict) else ''
        if any(k in element_text for k in ('kerugian keuangan','kerugian negara','kerugian daerah','mens rea','penyalahgunaan kewenangan')) and any(k in law_blob for k in ('perbankan','bpr','pojk','seojk')) and not any(k in law_blob for k in ('tipikor','korupsi','kuhp')):
            hard_semantic_violations.append({"chain_id":chain_id,"stage":"applicable_law","status":"CONTEXT_LAW_USED_AS_GOVERNING_LAW"})
        for ev in (row.get('evidence') or {}).get('items') or []:
            if isinstance(ev,dict) and ev.get('admissibility') not in {None,'PASS'}:
                hard_semantic_violations.append({"chain_id":chain_id,"stage":"evidence","status":"EVIDENCE_PROPOSITION_MISMATCH"})

        # Substantive gaps are HOLDs, not structural failures. They are expected
        # in a legal workpaper and must remain auditable.
        for stage in ("applicable_law", "alleged_act", "evidence", "counter_evidence", "causation"):
            status = str((row.get(stage) or {}).get("status") or "").upper()
            if status in {"MISSING", "GAP", "CANDIDATE", "COUNTER_ARGUMENT_ONLY", "UNVERIFIED", "NOT_APPLICABLE"}:
                semantic_holds.append({"chain_id": chain_id, "stage": stage, "status": status})

    structural_status = "PASS" if rows and not violations else ("NOT_ASSESSED" if not rows else "FAIL")
    return {
        "contract_version": CONTRACT_VERSION,
        "required_stages": list(CONTRACT_STAGES),
        "chain_count": len(rows),
        "violations": violations,
        "semantic_holds": semantic_holds,
        "hard_semantic_violations": hard_semantic_violations,
        "status": structural_status,
        "semantic_status": ("FAIL" if structural_status == "PASS" and hard_semantic_violations else ("HOLD" if structural_status == "PASS" and semantic_holds else structural_status)),
    }


def attach_reasoning_contract(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach canonical chain + schema validation without changing source facts."""
    result = result or {}
    chain = build_reasoning_chain(result)
    result["legal_reasoning_chain"] = chain
    result["reasoning_contract"] = validate_reasoning_contract(chain)
    return result
