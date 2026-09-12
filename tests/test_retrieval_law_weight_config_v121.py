from retrieval.search_router import LexiCoreLawRetrievalRouter
from services.regulatory_retrieval import load_law_weight_config


def _domains(*ids):
    return [{"id": x, "role": "PRIMARY" if i == 0 else "SECONDARY"} for i, x in enumerate(ids)]


def test_config_is_frozen_v121_and_has_no_force_admit_switch():
    cfg = load_law_weight_config()
    assert cfg["config_version"] == "1.2.1_frozen"
    assert "force_admitted_core_laws" not in cfg
    assert cfg["invariants"]["retriever_may_mark_applicable_law"] is False
    assert cfg["invariants"]["retriever_may_override_tempus"] is False


def test_internal_kpk_personnel_regulation_is_hard_dropped_even_with_high_initial_score():
    router = LexiCoreLawRetrievalRouter()
    row = {
        "title": "Peraturan Komisi Pemberantasan Korupsi tentang Tata Cara Penilaian Kinerja Individu Penasihat dan Pegawai",
        "initial_vector_score": 0.99,
    }
    decision = router.evaluate_candidate(row, _domains("corruption", "financial_services", "criminal"))
    assert decision["status"] == "REJECTED_SUBJECT_MATTER_UNPROVEN"
    assert "INTERNAL_INSTITUTIONAL_GOVERNANCE_NO_CASE_NEXUS" in decision["hard_drop_reasons"]


def test_protected_tipikor_law_bypasses_retrieval_drop_only():
    router = LexiCoreLawRetrievalRouter()
    row = {
        "title": "Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "initial_vector_score": 0.05,
    }
    decision = router.evaluate_candidate(row, _domains("corruption", "criminal"))
    assert decision["status"] == "POSITIVE_NEXUS_VERIFIED"
    assert decision["protected_candidate"] is True
    assert decision["protected_effect"] == "BYPASS_RETRIEVAL_DROP_ONLY"
    assert decision["may_mark_applicable_law"] is False
    assert decision["may_override_tempus"] is False


def test_fiduciary_credit_law_is_contextual_not_governing():
    router = LexiCoreLawRetrievalRouter()
    row = {
        "title": "Ketentuan mengenai perjanjian kredit, agunan dan jaminan fidusia pada BPR",
        "initial_vector_score": 0.55,
    }
    decision = router.evaluate_candidate(row, _domains("financial_services", "corruption", "civil_contract"))
    assert decision["status"] == "POSITIVE_NEXUS_VERIFIED"
    assert decision["candidate_role"] == "CONTEXTUAL_LAW"
    assert decision["may_mark_applicable_law"] is False


def test_cross_domain_mining_candidate_is_degraded_and_rejected():
    router = LexiCoreLawRetrievalRouter()
    row = {
        "title": "Peraturan tentang Izin Usaha Pertambangan dan AMDAL",
        "initial_vector_score": 0.95,
    }
    decision = router.evaluate_candidate(row, _domains("corruption", "financial_services"))
    assert decision["status"] == "REJECTED_SUBJECT_MATTER_UNPROVEN"
    assert decision["degraded_reasons"]
    assert decision["final_retrieval_score"] < 0.75


def test_apply_retrieval_weights_returns_only_positive_allowed_candidates():
    router = LexiCoreLawRetrievalRouter()
    rows = [
        {
            "title": "POJK tentang tata kelola BPR dan prinsip kehati-hatian dalam pemberian kredit",
            "initial_vector_score": 0.55,
        },
        {
            "title": "Peraturan KPK tentang penilaian kinerja individu penasihat dan pegawai KPK",
            "initial_vector_score": 0.99,
        },
    ]
    filtered = router.apply_retrieval_weights(rows, _domains("financial_services", "corruption"))
    assert len(filtered) == 1
    assert "POJK" in filtered[0]["title"]
    assert filtered[0]["law_weight_policy"]["status"] == "POSITIVE_NEXUS_VERIFIED"
