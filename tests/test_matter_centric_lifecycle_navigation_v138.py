from pathlib import Path
import re

HTML = Path(__file__).resolve().parents[1] / 'static' / 'index.html'


def source():
    return HTML.read_text(encoding='utf-8')


def test_primary_navigation_keeps_matter_first_and_norm_conflict_semantics():
    s = source()
    nav = s[s.index('<nav class="nav"'):s.index('</nav>', s.index('<nav class="nav"'))]
    panels = re.findall(r'data-panel="([^"]+)"', nav)
    assert panels[0] == 'client'
    assert set(panels) == {'client','draft','review','case','corpus','risk','research','norm'}
    assert 'Client / Intake & Matter' in nav
    assert 'Norm Conflict Analysis' in nav
    assert 'Conflict Check' not in nav


def test_navigation_numbers_are_unique_sequential_labels():
    s = source()
    nav = s[s.index('<nav class="nav"'):s.index('</nav>', s.index('<nav class="nav"'))]
    assert re.findall(r'<span class="nav-order">(\d+)</span>', nav) == [str(i) for i in range(1, 9)]


def test_client_remains_default_workspace():
    s = source()
    assert '<button class="active" data-panel="client">' in s
    assert '<section class="panel active" id="client">' in s
    assert '<section class="panel" id="draft">' in s
    assert '<h1 id="pageTitle">Client / Intake & Matter</h1>' in s


def test_dashboard_contains_one_metric_for_each_existing_module():
    s = source()
    start = s.index('<div class="cards" aria-label="Lifecycle workspace">')
    end = s.index('</div><div class="workspace-subnav-host"', start)
    cards = s[start:end]
    panels = re.findall(r'data-panel="([^"]+)"', cards)
    assert set(panels) == {'client','draft','review','case','corpus','risk','research','norm'}
    assert len(panels) == 8


def test_case_companion_cards_are_semantic_not_stale_sequence_numbers():
    s = source()
    assert 'CORPUS · SUMBER REGULASI' in s
    assert 'RESEARCH · VERIFIKASI' in s
    assert 'NORM CONFLICT · ANTINOMI' in s
    assert '3 · KORPUS REGULASI' not in s
    assert '4 · RISET HUKUM' not in s
    assert '7 · KONFLIK NORMA' not in s
