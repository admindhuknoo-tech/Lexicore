from services.sal_source_of_truth import build_governed_pools
from services.legal_reasoning_chain import _law_candidates


def _domain_contract():
    return {
        "primary_domain": "corruption",
        "domains": [
            {"id": "corruption", "role": "PRIMARY"},
            {"id": "financial_services", "role": "SECONDARY"},
            {"id": "criminal", "role": "SECONDARY"},
            {"id": "regional_government", "role": "SECONDARY"},
        ],
        "domain_contract": ["corruption", "financial_services", "criminal", "regional_government"],
        "supporting_only": [],
    }


def _result_with_official(rows):
    return {
        "domain_contract": _domain_contract(),
        "source_text": "Perkara tindak pidana korupsi terkait kredit BPR milik pemerintah daerah.",
        "source_ledger": [],
        "case_regulatory_snapshot": {"official_results": rows},
        "applicable_law": [],
        "regulatory_matches": [],
    }


def test_internal_kpk_personnel_regulation_cannot_enter_candidate_law_pool_even_if_policy_metadata_was_lost():
    title = (
        "Perubahan Atas Peraturan Komisi Pemberantasan Korupsi Nomor 10 Tahun 2010 "
        "Tentang Tata Cara Penilaian Kinerja Individu Penasihat dan Pegawai"
    )
    result = _result_with_official([
        {
            "title": title,
            "domain": "corruption",
            "query_origin": "DISCOVERY",
            "positive_law_verification": {"final_status": "CANDIDATE"},
        }
    ])
    pools = build_governed_pools(result)
    assert all(title not in row.get("source", "") for row in pools["candidate_law_pool"])
    assert any(title in row.get("source", "") for row in pools["rejected_law_pool"])
    rejected = next(row for row in pools["rejected_law_pool"] if title in row.get("source", ""))
    assert rejected["sal_subject_matter_reason"] == "INTERNAL_INSTITUTIONAL_GOVERNANCE_NO_CASE_NEXUS"
    result["sal_single_source_of_truth"] = True
    selected = _law_candidates(
        result,
        {"element": "Perbuatan melawan hukum/penyalahgunaan kewenangan", "owner_domain": "corruption"},
        "Apakah penyimpangan kredit BPR merupakan tindak pidana korupsi?",
    )
    assert all("Penilaian Kinerja Individu" not in row.get("source", "") for row in selected)


def test_internal_kpk_personnel_regulation_exact_case_row_may_remain_auditable_but_never_governing_candidate():
    title = (
        "Peraturan Komisi Pemberantasan Korupsi Tentang Penilaian Kinerja Individu "
        "Penasihat dan Pegawai"
    )
    result = _result_with_official([
        {
            "title": title,
            "domain": "corruption",
            "query_origin": "EXACT_CASE_REGULATION",
            "candidate_law_eligible": False,
            "provision_binding_provenance": {"case_bound": True},
            "positive_law_verification": {"final_status": "UNVERIFIED"},
        }
    ])
    pools = build_governed_pools(result)
    assert not pools["candidate_law_pool"]
    assert pools["rejected_law_pool"]


def test_tipikor_and_banking_rules_remain_candidate_law_eligible():
    result = _result_with_official([
        {
            "title": "UU No. 31 Tahun 1999 jo UU No. 20 Tahun 2001 tentang Pemberantasan Tindak Pidana Korupsi",
            "domain": "corruption",
            "query_origin": "DISCOVERY",
            "positive_law_verification": {"final_status": "CANDIDATE"},
        },
        {
            "title": "Undang-Undang Nomor 10 Tahun 1998 tentang Perbankan",
            "domain": "financial_services",
            "query_origin": "DISCOVERY",
            "positive_law_verification": {"final_status": "CANDIDATE"},
        },
    ])
    pools = build_governed_pools(result)
    sources = [row.get("source", "") for row in pools["candidate_law_pool"]]
    assert any("Pemberantasan Tindak Pidana Korupsi" in x for x in sources)
    assert any("Perbankan" in x for x in sources)
