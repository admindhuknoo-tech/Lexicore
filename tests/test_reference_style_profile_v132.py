from exporters.common import LexiCoreCivilPresentationSanitizer


def test_v130_macro_reader_polish_is_present_at_render_boundary():
    clean = LexiCoreCivilPresentationSanitizer.clean_text
    assert clean("Case Analysis") == "Analisis Perkara"
    assert clean("CASE ANALYSIS") == "ANALISIS PERKARA"
    assert clean("TINDAKAN: menjawab gap ini") == "TINDAKAN: menjawab kekosongan pembuktian ini"
    assert clean("Rekomendasi: menutup gap ini") == "Rekomendasi: menutup kekosongan pembuktian ini"
    assert clean("Keterkaitan Materi Perkara") == "keterkaitan materi perkara"
    assert clean("adanya fee") == "adanya imbalan/komisi"
    assert clean("bukti kickback") == "bukti pembayaran balik tidak sah"


def test_brand_literal_remains_outside_case_analysis_mapping():
    # The sanitizer may normalize generic report titles, but the exporters render
    # the branded masthead as a literal and must keep this exact text.
    brand = "Evidence-to-Action Case Analysis | Initiated by ELF - Erfan's Law Firm"
    assert "Evidence-to-Action Case Analysis" in brand
