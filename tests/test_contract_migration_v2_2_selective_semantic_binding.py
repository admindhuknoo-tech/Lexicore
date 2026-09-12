from services.legal_reasoning_chain import build_reasoning_chain
from services.reasoning_contract import validate_reasoning_contract


def _result(*, law_status="CANDIDATE", evidence=True, counter=False, classification=None):
    element = {
        "id": "absolute_competence",
        "element": "Kompetensi absolut forum berdasarkan subjek dan objek",
        "status": "SUPPORTED" if evidence else "NEEDS_EVIDENCE",
        "alleged_act": "Penggugat memilih Pengadilan Negeri untuk sengketa waris.",
        "supporting_evidence": ([{"statement": "Surat keterangan ahli waris dan objek sengketa waris", "source_classification": "ACTUAL_EVIDENTIARY_ITEM"}] if evidence else []),
        "counter_evidence": ([{"statement": "Akta pembagian waris menunjukkan sengketa telah selesai", "source_classification": "ACTUAL_EVIDENTIARY_ITEM"}] if counter else []),
    }
    if classification:
        element["procedural_merits"] = classification
    return {
        "legal_issues": ["Apakah Pengadilan Negeri memiliki kompetensi absolut untuk sengketa waris?"],
        "element_matrix": [element],
        "applicable_law": [{"source": "UU Peradilan Agama Pasal 49", "status": law_status, "domain": "waris kompetensi absolut"}],
        "causation_analysis": {"status": "NEXUS_NOT_ESTABLISHED", "reason": "Belum relevan untuk isu prosedural."},
    }


def test_selective_binding_adds_stable_lineage_without_parallel_pipeline():
    chain = build_reasoning_chain(_result())["chains"][0]
    binding = chain["binding_context"]
    assert binding["status"] == "BOUND"
    assert binding["issue_key"].startswith("issue:")
    assert binding["element_key"].startswith("element:")
    assert chain["element_test"]["binding"]["element_key"] == binding["element_key"]


def test_candidate_law_is_semantic_hold_not_structural_contract_failure():
    built = build_reasoning_chain(_result(law_status="CANDIDATE"))
    contract = validate_reasoning_contract(built)
    assert contract["status"] == "PASS"
    assert contract["semantic_status"] == "HOLD"
    assert any(x["stage"] == "applicable_law" for x in contract["semantic_holds"])


def test_element_test_granular_status_respects_law_gate_before_evidence_counting():
    chain = build_reasoning_chain(_result(law_status="CANDIDATE", evidence=True))["chains"][0]
    assert chain["element_test"]["granular_status"] == "LAW_GATE_HOLD"
    assert chain["element_test"]["gate"] == "HOLD"


def test_counter_evidence_generates_granular_contested_status_only_when_evidentiary_channel_exists():
    chain = build_reasoning_chain(_result(law_status="VERIFIED_APPLICABLE", evidence=True, counter=True))["chains"][0]
    assert chain["counter_evidence"]["status"] == "MAPPED"
    assert chain["element_test"]["granular_status"] == "SUPPORTED_WITH_COUNTER"


def test_issue_risk_is_aggregated_from_element_chains():
    built = build_reasoning_chain(_result(law_status="VERIFIED_APPLICABLE", evidence=True))
    assert len(built["issue_risk"]) == 1
    assert built["issue_risk"][0]["element_count"] == 1
    assert built["issue_risk"][0]["issue_key"].startswith("issue:")


def test_recommended_action_carries_gap_provenance():
    chain = build_reasoning_chain(_result(law_status="CANDIDATE", evidence=False))["chains"][0]
    provenance = chain["recommended_action"]["derived_from"]
    assert provenance["law_gate"] == "CANDIDATE"
    assert provenance["evidence_gate"] == "MISSING"
