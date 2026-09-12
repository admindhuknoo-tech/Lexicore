from regulatory_db import get_all_regulations
from services import regulatory_retrieval as rr
from services.positive_law_verification import verify_document_candidate


def _reg_by_id(reg_id):
    return next(r for r in get_all_regulations() if r.get("id") == reg_id)


def test_r29_kpk_corpus_identity_and_provisions_are_present():
    reg = _reg_by_id("uu_kpk_30_2002")
    assert reg["official_url"] == "https://peraturan.bpk.go.id/Details/44493/Undang-Undang-no-30-tahun-2002"
    names = [a.get("pasal") for a in reg.get("articles") or []]
    assert "Pasal 6" in names
    assert "Pasal 7" in names


def test_r29_corruption_route_includes_uu_30_2002_without_replacing_r28_tipikor_queries():
    q = rr.KNOWN_REGULATION_QUERIES["corruption"]
    assert "Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi" in q
    assert "Undang-Undang Nomor 20 Tahun 2001 tentang Perubahan atas Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi" in q
    assert "Undang-Undang Nomor 30 Tahun 2002 tentang Komisi Pemberantasan Tindak Pidana Korupsi" in q


def test_r29_case_binding_binds_pasal_6_and_7_to_uu_30_2002():
    text = (
        "Dalam isu kewenangan KPK, Pasal 6 jo Pasal 7 "
        "Undang-Undang Nomor 30 Tahun 2002 tentang Komisi Pemberantasan Tindak Pidana Korupsi harus diverifikasi."
    )
    bindings = rr._extract_case_regulation_bindings(text)
    kpk = [b for b in bindings if (b.get("identity") or {}).get("key") == "UU:30:2002"]
    assert kpk
    assert kpk[0]["provisions"] == ["Pasal 6", "Pasal 7"]
    assert kpk[0]["provenance"] == "EXACT_CASE_TEXT"


def test_r29_uu_30_2002_identity_and_pasal_6_7_verify_fail_closed_on_tempus():
    source = """
    UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 30 TAHUN 2002
    TENTANG KOMISI PEMBERANTASAN TINDAK PIDANA KORUPSI

    Pasal 6
    Komisi Pemberantasan Korupsi mempunyai tugas sesuai ketentuan undang-undang.

    Pasal 7
    Dalam melaksanakan tugas koordinasi, Komisi Pemberantasan Korupsi melakukan tindakan sesuai ketentuan undang-undang.
    """
    candidate = {
        "title": "Undang-Undang Nomor 30 Tahun 2002 tentang Komisi Pemberantasan Tindak Pidana Korupsi",
        "url": "https://peraturan.bpk.go.id/Details/44493/Undang-Undang-no-30-tahun-2002",
        "authoritative": True,
        "requested_provisions": ["Pasal 6", "Pasal 7"],
        "query_origin": "EXACT_CASE_REGULATION",
        "case_nexus_domains": ["corruption"],
        "provision_binding_provenance": {"case_bound": True},
    }
    result = verify_document_candidate(candidate, source_text=source, snapshot={})
    assert result["identity_confirmed"] is True
    assert result["identity"]["key"] == "UU:30:2002"
    assert result["case_nexus_status"] == "CASE_NEXUS_VERIFIED"
    assert result["provision_verification"]["verified_count"] == 2
    assert result["provision_verification"]["verified"] == ["Pasal 6", "Pasal 7"]
    assert result["tempus_status"] == "TEMPUS_UNVERIFIED"
    assert result["tempus_applicable"] is None
    assert result["final_status"] == "VERIFICATION_REQUIRED"


def test_r29_r28_contract_constants_are_unchanged():
    # Guard the R28 route registry that must remain intact during KPK expansion.
    tipikor = _reg_by_id("uu_tipikor_31_1999")
    names = [a.get("pasal") for a in tipikor.get("articles") or []]
    for provision in ("Pasal 2 ayat (1)", "Pasal 3", "Pasal 9", "Pasal 18"):
        assert provision in names
    assert rr.EXACT_CASE_RECOVERY_RESERVE_SECONDS == 4.0

def test_r29_kpk_exact_recovery_seed_uses_canonical_bpk_detail_page():
    seeds = rr._canonical_official_seed_candidates("UU:30:2002")
    assert seeds
    assert seeds[0][0] == "local_corpus"
    assert seeds[0][1]["url"] == "https://peraturan.bpk.go.id/Details/44493/Undang-Undang-no-30-tahun-2002"
