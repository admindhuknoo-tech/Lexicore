from services.instrument_identity_contract import evaluate_instrument_identity_contract

ELECTORAL_DOMAINS = ["electoral_ethics"]


def test_uu_7_2017_rejects_pkpu_7_2017_same_number_year():
    row = {
        "title": "Peraturan KPU No. 7 Tahun 2017",
        "url": "https://jdih.kpu.go.id/peraturan-kpu-no-7-tahun-2017",
        "description": "Peraturan Komisi Pemilihan Umum",
    }
    r = evaluate_instrument_identity_contract(
        "UU:7:2017", row,
        expected_text="Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum",
        active_domains=ELECTORAL_DOMAINS,
    )
    assert r["passed"] is False
    assert r["type_match"] is False
    assert "INSTRUMENT_TYPE_MISMATCH" in r["reason"]


def test_uu_1_2015_rejects_uu_10_2015_kpk_candidate():
    row = {
        "title": "Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 1 Tahun 2015 Tentang Perubahan Atas Undang-Undang Nomor 30 Tahun 2002 Tentang Komisi Pemberantasan Tindak Pidana Korupsi Menjadi Undang-Undang",
        "url": "https://peraturan.bpk.go.id/Details/38210/uu-no-10-tahun-2015",
        "description": "Komisi Pemberantasan Tindak Pidana Korupsi",
    }
    r = evaluate_instrument_identity_contract(
        "UU:1:2015", row,
        expected_text="Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota",
        active_domains=ELECTORAL_DOMAINS,
    )
    assert r["passed"] is False
    assert r["number_year_match"] is False
    assert r["subject_family_match"] is False
    assert r["domain_compatible"] is False


def test_uu_7_2017_electoral_candidate_passes_contract():
    row = {
        "title": "UU No. 7 Tahun 2017",
        "url": "https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017",
        "description": "Pemilihan Umum",
    }
    r = evaluate_instrument_identity_contract(
        "UU:7:2017", row,
        expected_text="Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum",
        active_domains=ELECTORAL_DOMAINS,
    )
    assert r["passed"] is True
    assert r["type_match"] is True
    assert r["number_year_match"] is True
    assert r["subject_family_match"] is True
    assert r["domain_compatible"] is True


def test_uu_1_2015_pilkada_candidate_passes_contract():
    row = {
        "title": "UU No. 1 Tahun 2015",
        "url": "https://peraturan.bpk.go.id/Details/37674/uu-no-1-tahun-2015",
        "description": "Penetapan Perppu No. 1 Tahun 2014 tentang Pemilihan Gubernur, Bupati, dan Walikota Menjadi Undang-Undang",
    }
    r = evaluate_instrument_identity_contract(
        "UU:1:2015", row,
        expected_text="Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota",
        active_domains=ELECTORAL_DOMAINS,
    )
    assert r["passed"] is True
    assert r["type_match"] is True
    assert r["number_year_match"] is True
    assert r["subject_family_match"] is True


def test_ambiguous_metadata_is_not_false_rejected_before_fulltext():
    row = {"title": "Dokumen peraturan terkait", "url": "https://example.invalid/detail/123", "description": ""}
    r = evaluate_instrument_identity_contract(
        "UU:31:1999", row,
        expected_text="Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        active_domains=["corruption", "criminal"],
    )
    assert r["passed"] is True
    assert r["type_match"] is None
    assert r["number_year_match"] is None


def test_verification_pipeline_rejects_pkpu_before_fetch_or_embedded_uu_match():
    from services.regulatory_retrieval import _verify_positive_law_results
    row = {
        "title": "Peraturan KPU No. 7 Tahun 2017",
        "url": "https://jdih.kpu.go.id/peraturan-kpu-no-7-tahun-2017",
        "description": "Pemilihan Umum",
        "query": "Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum",
        "query_origin": "EXACT_CASE_REGULATION",
        "case_nexus_domains": ["electoral_ethics"],
        "case_nexus_status": "CASE_NEXUS_UNCERTAIN",
        "authoritative": True,
        "document_classification": {"legal_instrument_candidate": True},
        "requested_provisions": ["Pasal 3"],
    }
    out = _verify_positive_law_results([row], snapshot={}, max_documents=2, time_budget_seconds=2.0)[0]
    assert out["positive_law_verification"]["final_status"] == "REJECTED_INSTRUMENT_IDENTITY_CONTRACT"
    assert out["positive_law_verification"]["fetch_attempted"] is False
    assert out["instrument_identity_contract"]["type_match"] is False


def test_verification_pipeline_rejects_cross_family_kpk_candidate_for_pilkada_uu():
    from services.regulatory_retrieval import _verify_positive_law_results
    row = {
        "title": "Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 1 Tahun 2015 Tentang Perubahan Atas Undang-Undang Nomor 30 Tahun 2002 Tentang Komisi Pemberantasan Tindak Pidana Korupsi Menjadi Undang-Undang",
        "url": "https://peraturan.bpk.go.id/Details/38210/uu-no-10-tahun-2015",
        "description": "Komisi Pemberantasan Tindak Pidana Korupsi",
        "query": "Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota",
        "query_origin": "EXACT_CASE_REGULATION",
        "case_nexus_domains": ["electoral_ethics"],
        "case_nexus_status": "CASE_NEXUS_UNCERTAIN",
        "authoritative": True,
        "document_classification": {"legal_instrument_candidate": True},
        "requested_provisions": ["Pasal 2"],
    }
    out = _verify_positive_law_results([row], snapshot={}, max_documents=2, time_budget_seconds=2.0)[0]
    assert out["positive_law_verification"]["final_status"] == "REJECTED_INSTRUMENT_IDENTITY_CONTRACT"
    assert out["positive_law_verification"]["fetch_attempted"] is False
    assert "NUMBER_YEAR_MISMATCH" in out["instrument_identity_contract"]["reason"]
    assert "SUBJECT_FAMILY_MISMATCH" in out["instrument_identity_contract"]["reason"]
