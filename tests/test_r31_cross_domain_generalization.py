from services.case_domain_classifier import classify_case
from services.case_reasoning_guard import build_reasoning_guard
from services.official_identity_resolver import _identity_from_text, rank_candidates
from services.positive_law_verification import regulation_identity
from services.regulatory_retrieval import detect_domains, build_case_queries, _extract_case_regulation_bindings

DKPP_SAMPLE = (
    "KOMISI PEMILIHAN UMUM KOTA BATU JAWABAN ATAS LAPORAN DUGAAN PELANGGARAN KODE ETIK "
    "NOMOR PENGADUAN 157-P/L-DKPP/VII/2021 NOMOR PERKARA 167-PKE-DKPP/IX/2021. "
    "Teradu menolak seluruh dalil Pengadu. Teradu berpedoman pada Pasal 3 Undang-Undang Nomor 7 Tahun 2017 "
    "tentang Pemilihan Umum jo Pasal 2 Undang-Undang Nomor 1 Tahun 2015 tentang Penetapan Peraturan Pemerintah "
    "Pengganti Undang-Undang Nomor 1 Tahun 2014 tentang Pemilihan Gubernur, Bupati, dan Walikota Menjadi Undang-Undang "
    "jo Peraturan DKPP Nomor 2 Tahun 2019 tentang Kode Etik dan Pedoman Perilaku Penyelenggara Pemilihan Umum. "
    # Deliberately include a corruption-law title as a cited/reference-only fragment.
    "Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 1 Tahun 2015 Tentang Perubahan Atas "
    "Undang-Undang Nomor 30 Tahun 2002 Tentang Komisi Pemberantasan Tindak Pidana Korupsi Menjadi Undang-Undang."
)


def test_dkpp_proceeding_anchor_outranks_reference_only_criminal_terms():
    c = classify_case(DKPP_SAMPLE)
    assert c["primary_domain"] == "electoral_ethics"
    assert c["posture"] == "ELECTORAL_ETHICS_PROCEEDING"
    assert "criminal" not in c["domain_contract"]
    assert "corruption" not in c["domain_contract"]
    assert c["boundary_guard"]["proceeding_anchor"] == "ELECTORAL_ETHICS"


def test_reasoning_guard_does_not_turn_dkpp_into_pidana_or_tipikor():
    c = classify_case(DKPP_SAMPLE)
    g = build_reasoning_guard(DKPP_SAMPLE, c)
    assert g["flags"]["electoral_nexus"] is True
    assert g["flags"]["criminal_nexus"] is False
    assert g["flags"]["corruption_nexus"] is False
    assert g["tempus"]["status"] == "TEMPUS_NOT_TRIGGERED"
    assert "perkara pidana" not in g["guarded_synthesis"].lower()


def test_nested_perpu_reference_is_not_misclassified_as_uu_1_2015():
    title = (
        "Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 1 Tahun 2015 Tentang Perubahan Atas "
        "Undang-Undang Nomor 30 Tahun 2002 Tentang Komisi Pemberantasan Tindak Pidana Korupsi Menjadi Undang-Undang"
    )
    assert _identity_from_text(title) == "PERPU:1:2015"
    assert regulation_identity(title)["key"] == "PERPU:1:2015"

    ranked = rank_candidates("UU:1:2015", [("bpk", {"title": title, "url": "https://example.invalid/unstructured"})])
    assert not any(r.reason == "EXACT_TITLE_IDENTITY" for r in ranked)


def test_outer_uu_identity_still_wins_for_actual_uu_1_2015():
    title = (
        "Undang-Undang Nomor 1 Tahun 2015 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang "
        "Nomor 1 Tahun 2014 tentang Pemilihan Gubernur, Bupati, dan Walikota Menjadi Undang-Undang"
    )
    assert _identity_from_text(title) == "UU:1:2015"
    assert regulation_identity(title)["key"] == "UU:1:2015"


def test_dkpp_domain_emits_electoral_regulation_queries_not_criminal_defaults():
    domains = detect_domains(DKPP_SAMPLE)
    ids = [d["id"] for d in domains]
    assert ids[0] == "electoral_ethics"
    queries = build_case_queries(DKPP_SAMPLE, domains=domains, max_queries=10)
    low = "\n".join(queries).lower()
    assert "undang-undang nomor 7 tahun 2017" in low
    assert "undang-undang nomor 1 tahun 2015" in low
    assert "kuhap hak tersangka" not in low
    assert "uu tipikor penyalahgunaan" not in low


def test_case_binding_preserves_outer_uu_1_2015_identity():
    bindings = _extract_case_regulation_bindings(DKPP_SAMPLE)
    keys = {(b.get("identity") or {}).get("key") for b in bindings}
    assert "UU:7:2017" in keys
    assert "UU:1:2015" in keys


def test_fulltext_primary_identity_keeps_perpu_distinct_from_inner_uu():
    from legal_sources import _canonical_identity_key_from_text
    title = (
        "Peraturan Pemerintah Pengganti Undang-Undang Nomor 1 Tahun 2015 "
        "tentang Perubahan Atas Undang-Undang Nomor 30 Tahun 2002 tentang KPK"
    )
    assert _canonical_identity_key_from_text(title) == "PERPU:1:2015"


def test_cross_domain_arbitration_preserves_civil_and_employment_posture():
    civil = classify_case(
        "Penggugat mengajukan gugatan wanprestasi karena Tergugat tidak memenuhi Perjanjian Jual Beli "
        "dan telah disomasi. Dasar Pasal 1238 dan Pasal 1243 KUHPerdata."
    )
    assert civil["primary_domain"] == "civil_contract"
    assert "criminal" not in civil["domain_contract"]

    labor = classify_case(
        "Pekerja menggugat PHK sepihak. Perselisihan hubungan industrial telah melalui bipartit. "
        "PKWT dan upah menjadi pokok sengketa berdasarkan UU Ketenagakerjaan dan PP 35 Tahun 2021."
    )
    assert labor["primary_domain"] == "employment"
    assert "criminal" not in labor["domain_contract"]


def test_criminal_corruption_anchor_still_wins_when_process_is_explicit():
    sample = (
        "Jaksa Penuntut Umum mengajukan surat dakwaan terhadap Terdakwa dalam perkara tindak pidana korupsi "
        "pemberian kredit BPR yang didalilkan menimbulkan kerugian keuangan negara berdasarkan Pasal 3 UU 31 Tahun 1999."
    )
    c = classify_case(sample)
    assert c["primary_domain"] == "corruption"
    assert "criminal" in c["domain_contract"]
    assert "corruption" in c["domain_contract"]
