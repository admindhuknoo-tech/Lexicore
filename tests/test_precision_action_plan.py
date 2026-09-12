from services.case_action_planner import build_case_action_plan


def _verified():
    return {
        "case_regulatory_snapshot": {"official_results": [{"positive_law_verification": {
            "final_status": "VERIFIED_APPLICABLE", "identity_confirmed": True,
            "case_nexus_status": "CASE_NEXUS_VERIFIED", "tempus_status": "TEMPUS_VERIFIED",
            "tempus_applicable": True,
            "provision_verification": {"status": "PROVISION_VERIFIED", "verified_count": 2},
        }}]},
    }


def test_objection_plan_prioritizes_primary_doc_tempus_and_attribution():
    r = _verified()
    r.update({
        "professional_review": {
            "document_structure": {"document_type": "EKSEPSI_OR_OBJECTION"},
            "strategic_recommendation": {"approach": "REBUILD_OBJECTION_AROUND_FORMAL_DEFECTS"},
            "findings": [
                {"type": "TEMPUS_GAP", "severity": "HIGH"},
                {"type": "LEGAL_CITATION_ANOMALY", "severity": "HIGH"},
            ],
        },
        "reasoning_guard": {"tempus": {"status": "TEMPUS_TRANSITION_REVIEW_REQUIRED"}, "citation_anomalies": [{}]},
        "element_reasoning": {"law_gate": {"verified": True}, "elements": [{"element": "Kausalitas", "status": "DISPUTED"}]},
        "evidentiary_gaps": [],
    })
    plan = build_case_action_plan(r)
    issues = [a["issue"] for a in plan["actions"]]
    assert issues[0] in {"Tempus delicti dan ketentuan peralihan", "Validasi identitas dan nomor seluruh peraturan dalam dakwaan asli"}
    assert "Atribusi perbuatan individual terdakwa" in issues
    assert plan["strategic_posture"] == "FORMAL_OBJECTION_FIRST__MERITS_RESERVED"


def test_corruption_credit_plan_targets_actual_loss_and_causation():
    r = _verified()
    r.update({
        "domain_classification": {"domain_contract": ["corruption", "financial_services"]},
        "is_corruption": True,
        "is_credit": True,
        "element_reasoning": {"law_gate": {"verified": True}, "elements": [
            {"element": "Kerugian keuangan negara/daerah nyata", "status": "NOT_ESTABLISHED", "strong_evidence_source_count": 0},
            {"element": "Kausalitas", "status": "DISPUTED", "strong_evidence_source_count": 0},
            {"element": "Mens rea / tujuan menguntungkan", "status": "NOT_ESTABLISHED", "strong_evidence_source_count": 0},
            {"element": "Personal responsibility", "status": "DISPUTED", "strong_evidence_source_count": 0},
        ]},
        "evidentiary_gaps": ["Laporan hasil perhitungan kerugian keuangan negara/daerah lengkap"],
        "professional_review": {"document_structure": {"document_type": "LEGAL_DOCUMENT"}, "findings": []},
    })
    plan = build_case_action_plan(r)
    issues = " | ".join(a["issue"] for a in plan["actions"])
    assert "Actual loss chain" in issues
    assert "Causal chain" in issues
    assert "Mens rea / benefit tracing" in issues
    assert "Responsibility matrix" in issues


def test_unresolved_element_action_is_element_closure_ready():
    r = _verified()
    r.update({
        "professional_review": {"document_structure": {"document_type": "LEGAL_DOCUMENT"}, "findings": []},
        "element_reasoning": {"law_gate": {"verified": True}, "elements": [
            {"element": "Kausalitas", "status": "NOT_ESTABLISHED", "strong_evidence_source_count": 0,
             "risk": "Kausalitas belum terbukti."},
        ]},
        "evidentiary_gaps": [],
    })
    plan = build_case_action_plan(r)
    actions = plan["actions"]
    assert any("Kausalitas" in (a.get("related_elements") or []) for a in actions)
    assert all(a.get("success_criteria") for a in actions)
