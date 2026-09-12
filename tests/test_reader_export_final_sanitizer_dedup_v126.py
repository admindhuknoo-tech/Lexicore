from exporters.common import LexiCoreCivilPresentationSanitizer


def test_v126_reader_residue_terms_are_cleaned():
    source = (
        "Local Deterministic | Evidence-to-Action | retrieval sumber hukum | "
        "case keterkaitan | candidate result | actual loss | intervening acts | "
        "outstanding principal | exposure, recovery dan kausalitas | "
        "Hubungan sebab/akibat atau impact"
    )
    out = LexiCoreCivilPresentationSanitizer.clean_text(source)
    for residue in (
        "Local Deterministic", "Evidence-to-Action", "retrieval sumber hukum",
        "case keterkaitan", "candidate result", "actual loss",
        "intervening acts", "outstanding principal", "exposure", "recovery",
        "impact",
    ):
        assert residue not in out
    assert "mode deterministik lokal" in out
    assert "analisis bukti ke tindakan" in out
    assert "penelusuran sumber hukum" in out
    assert "keterkaitan materi perkara" in out
    assert "hasil kandidat hukum" in out
    assert "kerugian nyata" in out
    assert "tindakan atau faktor perantara" in out
    assert "sisa pokok kewajiban" in out
    assert "risiko hukum, pemulihan kerugian/aset, dan kausalitas" in out
    assert "Hubungan sebab-akibat atau dampak" in out


def test_v126_deduplicates_only_explicit_action_nodes():
    payload = {
        "actions": [
            "Dapatkan dan uji bukti primer.",
            "  Dapatkan   dan uji bukti primer.  ",
            "Verifikasi norma.",
        ],
        "evidence": ["Dokumen A", "Dokumen A"],
        "issues": ["Isu A", "Isu A"],
    }
    out = LexiCoreCivilPresentationSanitizer.sanitize_object(payload)
    assert len(out["actions"]) == 2
    assert out["evidence"] == ["Dokumen A", "Dokumen A"]
    assert out["issues"] == ["Isu A", "Isu A"]


def test_v126_preserves_dict_action_type_and_deduplicates_stably():
    first = {"action": "Periksa bukti", "priority": 1}
    duplicate = {"priority": 1, "action": "Periksa bukti"}
    second = {"action": "Verifikasi hukum", "priority": 1}
    out = LexiCoreCivilPresentationSanitizer.sanitize_object(
        {"recommended_actions": [first, duplicate, second]}
    )
    assert len(out["recommended_actions"]) == 2
    assert isinstance(out["recommended_actions"][0], dict)
    assert out["recommended_actions"][0]["action"] == "Periksa bukti"


def test_v126_generic_string_lists_are_never_deduplicated():
    values = ["sama", "sama", "berbeda"]
    out = LexiCoreCivilPresentationSanitizer.sanitize_object(values)
    assert out == values
