from exporters.common import (
    LexiCoreCivilPresentationSanitizer,
    _resolved_document_header_label,
    _case_export_sections,
)


def test_strong_duplik_posture_projection():
    text = "Para Tergugat melalui kuasa hukumnya dengan ini mengajukan DUPLIK terhadap REPLIK Penggugat."
    assert LexiCoreCivilPresentationSanitizer.resolve_civil_posture_label(text) == "Duplik Perdata / Pihak Tergugat"


def test_bare_opponent_mention_does_not_force_duplik():
    text = "Penggugat menyebut duplik pihak lawan dalam uraian kronologi."
    assert LexiCoreCivilPresentationSanitizer.resolve_civil_posture_label(text) == ""


def test_civil_global_swap_and_reader_noise_cleanup():
    raw = (
        "keberatan formil terhadap dakwaan atau forum; surat dakwaan; teks dakwaan; "
        "norma yang dirujuk dalam dakwaan; LEGAL_VERIFICATION_REQUIRED; "
        "FACT_ASSERTION/PRIMARY_EVIDENCE; Positive-Allow SAL; current issue; "
        "active-clash admission SAL; norma yang berlaku, act, bukti; act yang didalilkan"
    )
    out = LexiCoreCivilPresentationSanitizer.clean_text(raw, is_civil=True)
    for forbidden in (
        "dakwaan", "LEGAL_VERIFICATION_REQUIRED", "FACT_ASSERTION/PRIMARY_EVIDENCE",
        "Positive-Allow SAL", "current issue", "active-clash admission SAL",
        " act ", "act yang didalilkan",
    ):
        assert forbidden.lower() not in out.lower()


def test_non_civil_dakwaan_is_preserved():
    raw = "surat dakwaan dan teks dakwaan harus diuji"
    out = LexiCoreCivilPresentationSanitizer.clean_text(raw, is_civil=False)
    assert "surat dakwaan" in out.lower()
    assert "teks dakwaan" in out.lower()


def test_recursive_sanitizer_preserves_structure_and_types():
    data = {"a": ["LEGAL_VERIFICATION_REQUIRED", {"b": "Not established"}], "n": 3, "ok": True}
    out = LexiCoreCivilPresentationSanitizer.sanitize_object(data, is_civil=False)
    assert out["a"][0] == "DIPERLUKAN VERIFIKASI HUKUM POSITIF"
    assert out["a"][1]["b"] == "Belum terbukti"
    assert out["n"] == 3 and out["ok"] is True


def test_generic_header_falls_back_to_strong_duplik_source():
    x = {
        "professional_review": {
            "document_structure": {
                "display_document_type": "Dokumen Hukum / Kepemilikan Suara Belum Terverifikasi"
            }
        },
        "material_source_ledger": [
            {"statement": "Para Tergugat melalui Kuasa Hukumnya dengan ini mengajukan DUPLIK terhadap REPLIK Penggugat."}
        ],
    }
    assert _resolved_document_header_label(x) == "Duplik Perdata / Pihak Tergugat"


def test_case_export_final_pass_cleans_sections_13_to_16_style_noise():
    x = {
        "title": "Case Analysis",
        "filename": "Duplik.pdf",
        "professional_verification": "PENDING",
        "domain_classification": {"ranah_hukum": "PERDATA"},
        "professional_review": {
            "review_status": "WORKING_DRAFT_ONLY",
            "document_structure": {"display_document_type": "Dokumen Hukum / Kepemilikan Suara Belum Terverifikasi"},
            "strategic_recommendation": {
                "recommended_outline": [
                    "Objek eksepsi dan bagian surat dakwaan yang secara spesifik dipersoalkan",
                    "Keberatan per isu, masing-masing dengan teks dakwaan",
                    "Audit norma yang dirujuk dalam dakwaan",
                ]
            },
        },
        "material_source_ledger": [
            {"statement": "Para Tergugat dengan ini mengajukan DUPLIK terhadap REPLIK Penggugat."}
        ],
        "executive_summary": "Fakta kunci: belum ada FACT_ASSERTION/PRIMARY_EVIDENCE yang lolos Positive-Allow SAL; current issue belum lolos active-clash admission SAL.",
        "coverage_note": "Verifikasi profesional: Menunggu verifikasi lawyer.",
    }
    _, sections = _case_export_sections(x)
    dumped = "\n".join(str(v) for _, lines in sections for v in lines)
    for forbidden in ("surat dakwaan", "teks dakwaan", "dirujuk dalam dakwaan", "FACT_ASSERTION/PRIMARY_EVIDENCE", "Positive-Allow SAL", "current issue", "active-clash admission SAL"):
        assert forbidden.lower() not in dumped.lower()
