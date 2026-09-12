"""Golden-case regression benchmark for LexiCore Case Analysis.

The benchmark is intentionally outcome-neutral. It checks whether a run surfaces
known reasoning requirements from a reference case, not whether the defence/prosecution
will win. It is safe to run in CI and on local deterministic outputs.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _blob(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("executive_summary", "legal_analysis", "legal_issues", "recommendations", "strategic_recommendation"):
        value = result.get(key)
        parts.append(str(value or ""))
    for f in (result.get("professional_review") or {}).get("findings", []) or []:
        if isinstance(f, dict): parts.append(" ".join(str(k) for k in f.keys()) + " " + " ".join(str(v or "") for v in f.values()))
    for a in (result.get("precision_action_plan") or {}).get("actions", []) or []:
        if isinstance(a, dict): parts.append(" ".join(str(k) for k in a.keys()) + " " + " ".join(str(v or "") for v in a.values()))
    for e in (result.get("element_reasoning") or {}).get("elements", []) or []:
        if isinstance(e, dict): parts.append(" ".join(str(k) for k in e.keys()) + " " + " ".join(str(v or "") for v in e.values()))
    return _clean(" ".join(parts)).lower()


GOLDEN_BENCHMARKS = {
    "ELYADWI_1815": {
        "name": "Elya Dwi Admoko — Case Analysis 18:15",
        "baseline_score": 6.4,
        "expected": [
            {"id":"primary_doc_validation", "weight":12, "terms":["dokumen primer", "dakwaan asli", "validasi"]},
            {"id":"tempus_transition", "weight":15, "terms":["tempus", "ketentuan peralihan"]},
            {"id":"legal_identity_anomaly", "weight":10, "terms":["identitas peraturan", "salah tahun", "nomor"]},
            {"id":"individual_attribution", "weight":13, "terms":["atribusi", "individual", "tanggung jawab"]},
            {"id":"causal_chain", "weight":13, "terms":["kausalitas", "causal chain", "rantai"]},
            {"id":"forum_merits_separation", "weight":10, "terms":["forum", "merits", "pokok perkara"]},
            {"id":"fiduciary_non_dispositive", "weight":7, "terms":["fidusia", "tidak otomatis", "bukan satu-satunya"]},
            {"id":"actual_loss_recovery", "weight":7, "terms":["kerugian", "recovery", "outstanding"]},
            {"id":"element_test", "weight":8, "terms":["unsur", "element test", "bukti"]},
            {"id":"action_traceability", "weight":5, "terms":["related_elements", "evidence_targets", "success_criteria"]},
        ],
    }
}


def benchmark_case(result: Dict[str, Any], benchmark_id: str = "ELYADWI_1815") -> Dict[str, Any]:
    spec = GOLDEN_BENCHMARKS[benchmark_id]
    blob = _blob(result)
    checks = []
    earned = 0
    for item in spec["expected"]:
        matched = [t for t in item["terms"] if t in blob]
        ok = len(matched) >= 1
        if ok: earned += item["weight"]
        checks.append({"id":item["id"], "passed":ok, "weight":item["weight"], "matched_terms":matched})

    er = result.get("element_reasoning") or {}
    elements = er.get("elements") or []
    actions = (result.get("precision_action_plan") or {}).get("actions") or []
    full_chain = result.get("legal_reasoning_chain") or {}
    unresolved = [e for e in elements if isinstance(e, dict) and e.get("status") in {"NOT_ESTABLISHED","NEEDS_EVIDENCE","DISPUTED"}]
    traceable = 0
    for e in unresolved:
        name = _clean(e.get("element")).lower()
        if any(name and name in " ".join(str(v) for v in (x.get("related_elements") or [])).lower() for x in actions if isinstance(x, dict)):
            traceable += 1
    traceability_ratio = (traceable / len(unresolved)) if unresolved else 1.0

    if unresolved and traceability_ratio < 1.0:
        checks.append({"id":"unresolved_elements_have_actions", "passed":False, "weight":5, "matched_terms":[]})
    else:
        checks.append({"id":"unresolved_elements_have_actions", "passed":True, "weight":5, "matched_terms":["all unresolved elements trace to actions"]})
        earned += 5

    chain_required = {
        "issue", "applicable_law", "legal_elements", "alleged_act", "evidence",
        "counter_evidence", "element_test", "causation", "risk",
        "procedural_merits_classification", "recommended_action"
    }
    from services.reasoning_contract import validate_reasoning_contract
    validation = validate_reasoning_contract(full_chain)
    chain_ok = validation.get("status") == "PASS" and bool(full_chain.get("chains")) and all(chain_required.issubset(set(c.keys())) for c in (full_chain.get("chains") or []) if isinstance(c, dict))
    if chain_ok:
        earned += 5
        checks.append({"id":"full_reasoning_chain_contract", "passed":True, "weight":5, "matched_terms":["11-stage chain"]})
    else:
        checks.append({"id":"full_reasoning_chain_contract", "passed":False, "weight":5, "matched_terms":[]})

    score = round(min(100, earned), 1)
    return {
        "benchmark_id": benchmark_id,
        "benchmark_name": spec["name"],
        "baseline_score_10": spec["baseline_score"],
        "score_100": score,
        "score_10": round(score / 10, 2),
        "checks": checks,
        "unresolved_element_count": len(unresolved),
        "traceable_unresolved_element_count": traceable,
        "traceability_ratio": round(traceability_ratio, 3),
        "release_gate": "PASS" if score >= 90 and traceability_ratio >= 1.0 else "REVIEW_REQUIRED",
        "interpretation": "Regression coverage of reasoning requirements; not a probability of success, guilt, liability, or court outcome.",
    }
