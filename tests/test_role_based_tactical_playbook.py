"""Regression tests for the generalized (ranah_hukum x posisi_pengguna)
tactical playbook added to services/case_action_planner.py and
services/case_role_detector.py.

These tests intentionally do NOT touch the Kasus-A objection / corruption-
credit paths already covered by tests/test_precision_action_plan.py — they
cover the generalization gap that existed before: any case that was neither
an objection nor a corruption/credit merits case previously received zero
procedural/tactical actions.
"""
from services.case_action_planner import build_case_action_plan
from services.case_role_detector import detect_case_role


def _base(source_text, domain_classification, doc_type="LEGAL_DOCUMENT"):
    return {
        "source_text": source_text,
        "domain_classification": domain_classification,
        "professional_review": {"document_structure": {"document_type": doc_type}, "findings": []},
        "element_reasoning": {"law_gate": {"verified": True}, "elements": []},
        "evidentiary_gaps": [],
    }


def test_perdata_tergugat_gets_hir_rbg_playbook():
    r = _base(
        "Kami, kuasa hukum Tergugat, menyampaikan jawaban gugatan atas perkara "
        "wanprestasi perjanjian sewa menyewa antara Penggugat dan Tergugat.",
        {"posture": "PERDATA_LITIGASI", "primary_domain": "civil_contract", "domain_contract": ["civil_contract"]},
        doc_type="CIVIL_PLEADING",
    )
    plan = build_case_action_plan(r)
    issues = [a["issue"] for a in plan["actions"]]
    assert "Eksepsi Kompetensi (Relatif/Absolut)" in issues
    assert "Draf Jawaban Gugatan" in issues
    assert "Kelayakan Gugatan Rekonvensi (Balik)" in issues


def test_perdata_penggugat_gets_standing_and_posita_playbook():
    r = _base(
        "Kami, kuasa hukum Penggugat, mengajukan gugatan wanprestasi terhadap "
        "Tergugat atas perjanjian jual beli yang tidak dipenuhi.",
        {"posture": "PERDATA_LITIGASI", "primary_domain": "civil_contract", "domain_contract": ["civil_contract"]},
        doc_type="CIVIL_PLEADING",
    )
    plan = build_case_action_plan(r)
    issues = [a["issue"] for a in plan["actions"]]
    assert "Legal standing dan syarat formil gugatan" in issues
    assert "Koherensi posita-petitum dengan alat bukti primer" in issues


def test_pidana_umum_terdakwa_gets_praperadilan_playbook():
    r = _base(
        "Kami, penasihat hukum Terdakwa, dalam perkara dugaan tindak pidana "
        "penggelapan. Terdakwa ditetapkan sebagai tersangka setelah penyidikan.",
        {"posture": "GENERAL_LEGAL", "primary_domain": "criminal", "domain_contract": ["criminal"]},
    )
    plan = build_case_action_plan(r)
    issues = [a["issue"] for a in plan["actions"]]
    assert "Kelayakan Praperadilan (Uji Formil Penangkapan/Penahanan/Penyidikan)" in issues
    assert "Nota Keberatan (Eksepsi Dakwaan)" in issues
    assert "Persiapan Saksi Meringankan (A De Charge)" in issues


def test_tun_pemohon_gets_90_day_deadline_playbook():
    r = _base(
        "Kami, kuasa hukum Pemohon, mengajukan gugatan terhadap Keputusan Tata "
        "Usaha Negara yang diterbitkan oleh pejabat tata usaha negara.",
        {"posture": "TATA_USAHA_NEGARA", "primary_domain": "administrative", "domain_contract": ["administrative"]},
    )
    plan = build_case_action_plan(r)
    issues = [a["issue"] for a in plan["actions"]]
    assert "Tenggang waktu 90 hari sejak KTUN diketahui/diterima" in issues


def test_ambiguous_role_fails_closed_instead_of_guessing():
    r = _base(
        "Dokumen hukum umum tanpa penanda otorship yang jelas mengenai suatu perkara.",
        {"posture": "GENERAL_LEGAL", "primary_domain": "civil_contract", "domain_contract": []},
    )
    plan = build_case_action_plan(r)
    issues = [a["issue"] for a in plan["actions"]]
    assert "Identifikasi forum dan posisi pihak secara manual" in issues
    role = detect_case_role(r["source_text"], r)
    assert role["posisi_pengguna"] == "TIDAK_TERIDENTIFIKASI"


def test_role_detection_prefers_authorship_signal_over_bare_label():
    # Both "Penggugat" and "Tergugat" appear (normal for any pleading), but
    # only one side's authorship markers are present.
    text = (
        "Kami, kuasa hukum Tergugat, dalam perkara antara Penggugat melawan "
        "Tergugat, menyampaikan jawaban atas gugatan Penggugat."
    )
    role = detect_case_role(text, {"domain_classification": {"posture": "PERDATA_LITIGASI"}})
    assert role["posisi_pengguna"] == "TERGUGAT"
    assert role["confidence"] == "HIGH"


def test_objection_path_unaffected_by_new_playbook():
    # Kasus-A objection path must still win outright and must not be diluted
    # by the new role-based branch (it only fires in the `else` case).
    r = {
        "domain_classification": {"posture": "PIDANA_KHUSUS_PENYIDIKAN", "primary_domain": "corruption"},
        "professional_review": {
            "document_structure": {"document_type": "EKSEPSI_OR_OBJECTION"},
            "strategic_recommendation": {"approach": "REBUILD_OBJECTION_AROUND_FORMAL_DEFECTS"},
            "findings": [{"type": "TEMPUS_GAP", "severity": "HIGH"}],
        },
        "reasoning_guard": {"tempus": {"status": "TEMPUS_TRANSITION_REVIEW_REQUIRED"}, "citation_anomalies": []},
        "element_reasoning": {"law_gate": {"verified": True}, "elements": []},
        "evidentiary_gaps": [],
        "source_text": "Nota keberatan atas surat dakwaan.",
    }
    plan = build_case_action_plan(r)
    issues = [a["issue"] for a in plan["actions"]]
    assert "Tempus delicti dan ketentuan peralihan" in issues
    assert "Eksepsi Kompetensi (Relatif/Absolut)" not in issues


def test_citation_guardrail_blocks_unverified_pasal():
    r = {
        "source_text": "Terdakwa didakwa melanggar Pasal 2 UU No. 20 Tahun 2001 dan Pasal 55 KUHP.",
        "provision_refs": ["Pasal 2 UU No. 20 Tahun 2001", "Pasal 55 KUHP"],
        "domain_classification": {"posture": "PIDANA_KHUSUS_PENYIDIKAN", "primary_domain": "corruption"},
        "professional_review": {"document_structure": {"document_type": "LEGAL_DOCUMENT"}, "findings": []},
        "element_reasoning": {"law_gate": {"verified": True}, "elements": []},
        "evidentiary_gaps": [],
        "case_regulatory_snapshot": {"official_results": []},
    }
    plan = build_case_action_plan(r)
    assert plan["citation_guardrail"]["unverified_provisions"] == ["Pasal 2", "Pasal 55"]
    assert any("belum lolos verifikasi sumber resmi" in b for b in plan["blockers"])
    assert plan["actions"][0]["issue"] == "Verifikasi pasal yang belum lolos gate sumber resmi"


def test_citation_guardrail_clears_when_provision_verified():
    r = {
        "source_text": "Terdakwa didakwa melanggar Pasal 2 UU No. 20 Tahun 2001.",
        "provision_refs": ["Pasal 2 UU No. 20 Tahun 2001"],
        "domain_classification": {"posture": "PIDANA_KHUSUS_PENYIDIKAN", "primary_domain": "corruption"},
        "professional_review": {"document_structure": {"document_type": "LEGAL_DOCUMENT"}, "findings": []},
        "element_reasoning": {"law_gate": {"verified": True}, "elements": []},
        "evidentiary_gaps": [],
        "case_regulatory_snapshot": {"official_results": [{"positive_law_verification": {
            "final_status": "VERIFIED_APPLICABLE",
            "provision_verification": {"status": "PROVISION_VERIFIED", "verified": ["Pasal 2"]},
        }}]},
    }
    plan = build_case_action_plan(r)
    assert plan["citation_guardrail"]["unverified_provisions"] == []
    assert not any("belum lolos verifikasi sumber resmi" in b for b in plan["blockers"])
