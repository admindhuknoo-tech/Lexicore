from exporters.common import LexiCoreCivilPresentationSanitizer, LexiCoreLowLevelRenderGovernor


def test_final_micro_normalization_exact_reader_phrases():
    raw = (
        "missing link | Missing Link | merits | Merits | "
        "Personal responsibility | personal responsibility | "
        "Source: UU | Provision Citation: https://example.test | "
        "mode mode deterministik lokal | Mode Mode Deterministik Lokal"
    )
    out = LexiCoreCivilPresentationSanitizer.clean_text(raw)
    assert "missing link" not in out
    assert "Missing Link" not in out
    assert "merits" not in out
    assert "Merits" not in out
    assert out.count("Pertanggungjawaban individual") == 2
    assert "Sumber: UU" in out
    assert "Tautan Sumber Resmi: https://example.test" in out
    assert "mode mode deterministik lokal" not in out
    assert "Mode Mode Deterministik Lokal" not in out


def test_micro_normalization_does_not_damage_unrelated_substrings():
    raw = "sources: tetap | resource: tetap | meritorious tetap | datasource: tetap"
    out = LexiCoreCivilPresentationSanitizer.clean_text(raw)
    assert out == raw


def test_low_level_governor_applies_micro_normalization_before_render():
    gov = LexiCoreLowLevelRenderGovernor(is_civil=False)
    out = gov.intercept(
        "Personal responsibility | Source: X | Provision Citation: Y | missing link"
    )
    assert out == (
        "Pertanggungjawaban individual | Sumber: X | "
        "Tautan Sumber Resmi: Y | keterputusan uraian"
    )
