from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'static' / 'index.html'
APP = ROOT / 'app.py'


def test_case_process_strip_is_compact_and_input_aware():
    src = HTML.read_text(encoding='utf-8')
    assert 'id="caseProcessStrip"' in src
    assert 'id="caseProcessInputLabel"' in src
    assert 'data-case-step="input"' in src
    assert 'data-case-step="mode"' in src
    assert 'data-case-step="analysis"' in src
    assert 'caseFile?.addEventListener(\'change\',syncCaseProcessStrip)' in src
    assert 'caseNarrative?.addEventListener(\'input\',syncCaseProcessStrip)' in src
    assert 'caseRegulatoryMode?.addEventListener(\'change\',syncCaseProcessStrip)' in src


def test_export_refreshes_case_history_without_full_page_reload():
    src = HTML.read_text(encoding='utf-8')
    assert 'await refreshCaseAnalysisAfterExport(fmt);' in src
    assert 'async function refreshCaseAnalysisAfterExport(fmt)' in src
    assert 'await loadAll();' in src
    assert 'window.location.reload' not in src


def test_case_history_detail_decodes_working_paper_for_review():
    src = APP.read_text(encoding='utf-8')
    assert "'case_working_paper'" in src
    tuple_line = next(line for line in src.splitlines() if "'case_analyses': ('facts'" in line)
    assert "'case_working_paper'" in tuple_line
    dict_line = next(line for line in src.splitlines() if "dict_json_fields=" in line)
    assert "'case_working_paper'" in dict_line


def test_history_review_reopens_case_workspace_not_only_toast():
    src = HTML.read_text(encoding='utf-8')
    start = src.index("if(kind==='case_analyses')")
    block = src[start:start+1800]
    assert 'renderCaseWorkingPaper(x);' in block
    assert "activatePanel('case');" in block
    assert "scrollIntoView" in block
    assert "syncCaseProcessStrip();" in block
