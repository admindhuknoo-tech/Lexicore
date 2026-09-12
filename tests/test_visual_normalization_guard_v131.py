from exporters.common import LexiCoreCivilPresentationSanitizer, LexiCoreLowLevelRenderGovernor


def test_residual_reader_facing_labels_are_normalized():
    raw = (
        "Domain: Pidana | [CRITICAL] Celah | Status review: Tahan | "
        "Review ini wajib diverifikasi lawyer | Ringkasan Review Hukum | "
        "Versi tampilan: ADV-VIEW-1.1 | Versi kontrak: 2.3.1 | "
        "Status struktur: Lolos | Status semantik: Ditahan | "
        "Urutan wajib: Isu -> Hukum | tanggal cut-off"
    )
    out = LexiCoreCivilPresentationSanitizer.clean_text(raw)
    assert "Domain:" not in out
    assert "[CRITICAL]" not in out
    assert "Status review:" not in out
    assert "Review ini" not in out
    assert "diverifikasi lawyer" not in out
    assert "Ringkasan Review Hukum" not in out
    assert "ADV-VIEW-1.1" not in out
    assert "Versi kontrak:" not in out
    assert "Status struktur:" not in out
    assert "Status semantik:" not in out
    assert "Urutan wajib:" not in out
    assert "tanggal cut-off" not in out
    assert "Ranah hukum: Pidana" in out
    assert "[KRITIS] Celah" in out
    assert "Status penelaahan: Tahan" in out
    assert "Penelaahan ini wajib diverifikasi profesional hukum" in out
    assert "Ringkasan Penelaahan Hukum" in out
    assert "Mode tampilan: Pemisahan posisi para pihak" in out
    assert "Versi struktur analisis: 2.3.1" in out
    assert "Kelengkapan struktur analisis: Lolos" in out
    assert "Status verifikasi analisis: Ditahan" in out
    assert "Urutan analisis: Isu -> Hukum" in out
    assert "tanggal batas perhitungan" in out


def test_residual_normalization_is_visible_at_low_level_render_boundary():
    gov = LexiCoreLowLevelRenderGovernor(is_civil=False)
    out = gov.intercept(
        "Domain: Pidana | [CRITICAL] | Versi tampilan: ADV-VIEW-1.1 | "
        "Status semantik: Ditahan | Provision Citation: X"
    )
    assert out == (
        "Ranah hukum: Pidana | [KRITIS] | Mode tampilan: Pemisahan posisi para pihak | "
        "Status verifikasi analisis: Ditahan | Tautan Sumber Resmi: X"
    )


def test_residual_normalization_does_not_touch_brand_or_legal_latin_terms():
    gov = LexiCoreLowLevelRenderGovernor(is_civil=False)
    brand = "Evidence-to-Action Case Analysis | Initiated by ELF - Erfan's Law Firm"
    assert gov.intercept(brand) == brand
    raw = "tempus delicti | mens rea | error in persona | meritorious"
    assert gov.intercept(raw) == raw
