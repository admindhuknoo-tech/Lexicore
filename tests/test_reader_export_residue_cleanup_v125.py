from exporters.common import LexiCoreCivilPresentationSanitizer


def test_final_reader_residue_terms_are_cleaned():
    source = (
        "[Dalil Pembelaan / DEFENSE_COUNSEL] | Element Test | PROSECUTOR | "
        "case keterkaitan | causal chain | dinyatakan applicable | Applicable law | "
        "exposure, recovery"
    )
    out = LexiCoreCivilPresentationSanitizer.clean_text(source)
    assert "DEFENSE_COUNSEL" not in out
    assert "PROSECUTOR" not in out
    assert "Element Test" not in out
    assert "case keterkaitan" not in out
    assert "causal chain" not in out
    assert "dinyatakan applicable" not in out
    assert "Applicable law" not in out
    assert "exposure" not in out
    assert "recovery" not in out
    assert "Penasihat Hukum" in out
    assert "Jaksa Penuntut Umum" in out
    assert "Pengujian Unsur Hukum" in out
    assert "keterkaitan materi perkara" in out
    assert "Rantai Hubungan Kausalitas" in out
    assert "dinyatakan dapat diterapkan" in out
    assert "Hukum yang berlaku" in out
    assert "risiko hukum dan pemulihan kerugian/aset" in out


def test_recursive_sanitizer_keeps_structure_types():
    payload = {
        "a": ["DEFENSE_COUNSEL", ("Element Test", "LEGAL_VERIFICATION_REQUIRED")],
        "n": 3,
        "flag": True,
    }
    out = LexiCoreCivilPresentationSanitizer.sanitize_object(payload)
    assert isinstance(out, dict)
    assert isinstance(out["a"], list)
    assert isinstance(out["a"][1], tuple)
    assert out["n"] == 3
    assert out["flag"] is True
    assert out["a"][0] == "Penasihat Hukum"
    assert out["a"][1][0] == "Pengujian Unsur Hukum"
    assert out["a"][1][1] == "DIPERLUKAN VERIFIKASI HUKUM POSITIF"
