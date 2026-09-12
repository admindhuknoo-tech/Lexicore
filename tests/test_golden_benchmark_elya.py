from services.case_benchmark import benchmark_case


def test_elya_golden_benchmark_requires_reasoning_chain_signals():
    r = {
        "legal_analysis": "Tempus delicti dan ketentuan peralihan perlu diverifikasi; pisahkan forum dan merits; fidusia tidak otomatis menentukan kompetensi.",
        "recommendations": "Validasi dokumen primer dakwaan asli dan identitas peraturan; uji atribusi individual dan kausalitas; periksa kerugian, recovery, outstanding.",
        "professional_review": {"findings": [{"type": "LEGAL_CITATION_ANOMALY"}]},
        "element_reasoning": {"elements": [{"element": "Kausalitas", "status": "DISPUTED"}], "law_gate": {"verified": False}},
        "precision_action_plan": {"actions": [{"issue":"Causal chain", "related_elements":["Kausalitas"], "evidence_targets":["dokumen primer"], "success_criteria":"uji"}]},
    }
    b = benchmark_case(r)
    assert b["score_10"] >= 8.5
    assert b["traceability_ratio"] == 1.0


def test_elya_golden_benchmark_fails_release_gate_when_chain_is_missing():
    b = benchmark_case({"legal_analysis": "ringkasan umum", "element_reasoning": {"elements": [{"element":"Kausalitas", "status":"DISPUTED"}]}})
    assert b["release_gate"] == "REVIEW_REQUIRED"
    assert b["traceability_ratio"] == 0.0
