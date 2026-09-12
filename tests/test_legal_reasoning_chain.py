from services.legal_reasoning_chain import build_reasoning_chain


def test_full_reasoning_chain_has_all_eleven_stages():
    result = {
        "legal_issues": ["Apakah keputusan kredit dapat diatribusikan secara personal?"],
        "element_reasoning": {"elements": [{
            "element": "Personal responsibility",
            "issue": "Apakah keputusan kredit dapat diatribusikan secara personal?",
            "applicable_law": "UU kandidat — perlu verifikasi",
            "alleged_act": "Menyetujui pencairan kredit",
            "prosecution_support": "Terdakwa menyetujui pencairan kredit",
            "defense_focus": "Pihak lain melakukan analisa dan survei",
            "counter_evidence": "SK kewenangan menunjukkan fungsi komite",
            "status": "DISPUTED",
            "causation": "Hubungan keputusan dengan pencairan masih harus diuji.",
            "risk": "Atribusi personal belum settled.",
            "procedural_merits": "MERITS",
        }]},
        "applicable_law": [{"source": "UU Nomor 31 Tahun 1999", "status": "VERIFIED_APPLICABLE", "domain": "corruption"}],
        "case_regulatory_snapshot": {"official_results": [{
            "title": "UU Nomor 31 Tahun 1999",
            "positive_law_verification": {
                "final_status": "VERIFIED_APPLICABLE",
                "identity_confirmed": True,
                "case_nexus_status": "CASE_NEXUS_VERIFIED",
                "tempus_status": "TEMPUS_VERIFIED",
                "tempus_applicable": True,
                "provision_verification": {"status": "PROVISION_VERIFIED", "verified_count": 1, "verified": ["Pasal 3"]},
            },
        }]},
        "material_source_ledger": [{
            "source_index": 4, "statement": "Notulen komite mencatat persetujuan pencairan kredit oleh komite.",
            "display_classification": "ACTUAL_EVIDENTIARY_ITEM",
            "label": "DOCUMENT",
        }],
        "precision_action_plan": {"actions": [{
            "priority": "P1", "issue": "Responsibility matrix", "action": "Petakan aktor dan kewenangan.",
            "related_elements": ["Personal responsibility"], "evidence_targets": ["SK", "notulen"],
            "success_criteria": "Setiap aktor terpetakan.",
        }]},
    }
    chain = build_reasoning_chain(result)
    assert chain["status"] == "COMPLETED"
    assert chain["chain_count"] == 1
    row = chain["chains"][0]
    for stage in ("issue", "applicable_law", "legal_elements", "alleged_act", "evidence",
                  "counter_evidence", "element_test", "causation", "risk",
                  "procedural_merits_classification", "recommended_action"):
        assert stage in row
    assert row["recommended_action"]["status"] == "LINKED"


def test_missing_counter_evidence_is_explicit_not_fabricated():
    result = {
        "legal_issues": ["Apakah perbuatan terbukti?"],
        "element_matrix": [{
            "element": "Perbuatan melawan hukum",
            "alleged_act": "Menandatangani persetujuan",
            "status": "DISPUTED",
        }],
        "applicable_law": [],
        "material_source_ledger": [{"statement": "Dokumen persetujuan ditandatangani terdakwa.", "label": "DOCUMENT"}],
    }
    chain = build_reasoning_chain(result)
    row = chain["chains"][0]
    assert row["counter_evidence"]["status"] == "MISSING"
    assert row["applicable_law"]["status"] == "MISSING"
    assert row["status"] == "BLOCKED_LAW_VERIFICATION"
