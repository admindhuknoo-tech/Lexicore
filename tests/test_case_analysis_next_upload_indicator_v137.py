from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"


def source():
    return HTML.read_text(encoding="utf-8")


def test_manual_input_has_single_slim_next_process_control():
    s = source()
    assert 'id="caseNextChip"' in s
    assert 'onclick="advanceCaseFlow()"' in s
    assert "PROSES · Mode & Analisis →" in s
    assert "NEXT · Mode & Analisis →" in s


def test_file_choose_has_visible_status_and_real_upload_success_state():
    s = source()
    assert 'id="caseUploadStatus"' in s
    assert "✓ File berhasil dipilih · " in s
    assert "✓ Upload sukses · " in s
    assert "p.stage==='UPLOAD_STORED'" in s


def test_next_control_routes_to_mode_without_starting_analysis_implicitly():
    s = source()
    start = s.index('function advanceCaseFlow()')
    end = s.index('function syncCaseProcessStrip()', start)
    body = s[start:end]
    assert "caseRegulatoryMode.focus()" in body
    assert "scrollIntoView" in body
    assert "analyzeCase()" not in body
