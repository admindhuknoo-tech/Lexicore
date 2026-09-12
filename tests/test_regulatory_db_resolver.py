from regulatory_db import NormResolver, corpus_stats


def test_regulatory_corpus_meets_release_floor_and_preserves_r17_plus_kpk():
    stats = corpus_stats()
    assert stats["regulations"] >= 45
    assert stats["regulations"] >= 48
    assert stats["articles"] >= 100


def test_exact_tipikor_and_kpk_are_not_mixed():
    tipikor = NormResolver.resolve("UU:31:1999")
    kpk = NormResolver.resolve("UU KPK")
    assert tipikor[:3] == ("UU:31:1999", 1.0, "explicit_match")
    assert kpk[:3] == ("UU:30:2002", 1.0, "explicit_match")


def test_pp_resolver_supports_canonical_and_human_forms():
    cases = {
        "PP:54:2017": "PP:54:2017",
        "PP 54/2017": "PP:54:2017",
        "PP 35/2021": "PP:35:2021",
        "PP 24/1997": "PP:24:1997",
    }
    for raw, expected in cases.items():
        resolved, conf, reason, diagnostics = NormResolver.resolve(raw)
        assert resolved == expected
        assert conf > 0.0
        assert reason != "no_resolution"
        assert diagnostics == []


def test_31_2017_is_preserved_as_diagnostic_candidate_not_autocorrected():
    for raw in ("31/2017", "UU 31 Tahun 2017", "31-2017"):
        resolved, conf, reason, diagnostics = NormResolver.resolve(raw)
        assert resolved == "UU:31:2017"
        assert resolved != "UU:31:1999"
        assert conf > 0.0
        assert conf <= 0.40
        assert "diagnostic_candidate" in reason
        assert diagnostics
        assert "VERIFIKASI MANUAL" in diagnostics[0]


def test_unknown_expected_valid_case_cannot_false_green_by_string_echo():
    raw = "PP:99:2099"
    resolved, conf, reason, diagnostics = NormResolver.resolve(raw)
    assert resolved == raw
    assert conf == 0.0
    assert reason == "no_resolution"
    assert diagnostics
