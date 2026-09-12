from exporters.common import (
    LexiCoreCivilPresentationSanitizer,
    _case_export_sections,
)


def test_section_12_reader_facing_internal_route_terms_are_hidden():
    raw = (
        "ID audit SAL_CONTRACT_LEDGER_0008_614ED82A2B | Informasi administratif/provenance | "
        "Tujuan analisis: Document Audit | Jalur yang diizinkan: Document Audit, "
        "Procedural/Merits, Regulation/Tempus | asal-usul data SAL"
    )
    out = LexiCoreCivilPresentationSanitizer.clean_text(raw)
    assert "SAL_CONTRACT_LEDGER" not in out
    assert "Document Audit" not in out
    assert "Procedural/Merits" not in out
    assert "Regulation/Tempus" not in out
    assert "asal-usul data SAL" not in out
    assert "Referensi Audit: 0008" in out
    assert "Audit Dokumen" in out
    assert "Prosedural / Pokok Perkara" in out
    assert "Dasar Hukum / Waktu Berlaku" in out


def test_semantic_layer_is_not_exported_to_reader_pdf_docx_model():
    payload = {
        "semantic_admission_ledger": {
            "contract_version": "SAL-1.0",
            "contract_status": "PASS",
            "statements_processed": 3,
            "semantic_type_counts": {"FACT_ASSERTION": 3},
            "admissibility_counts": {"LIMITED": 3},
        },
        "coverage_note": "Verifikasi profesional diperlukan.",
    }
    _meta, sections = _case_export_sections(payload)
    headings = [h for h, _ in sections]
    assert not any("SAL" in h or "Penerimaan Semantik" in h for h in headings)


def test_section_16_internal_semantic_tokens_are_reader_facing():
    raw = (
        "Fakta kunci: belum ada FACT_ASSERTION/PRIMARY_EVIDENCE yang lolos Positive-Allow SAL sebagai fakta kunci. "
        "Isu utama: belum ada current issue yang lolos active-clash admission SAL."
    )
    out = LexiCoreCivilPresentationSanitizer.clean_text(raw)
    for forbidden in (
        "FACT_ASSERTION/PRIMARY_EVIDENCE",
        "Positive-Allow SAL",
        "current issue",
        "active-clash admission SAL",
    ):
        assert forbidden not in out
    assert "pernyataan faktual atau bukti primer" in out
    assert "isu hukum aktif" in out
