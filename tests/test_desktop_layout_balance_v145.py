from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / 'static' / 'index.html'


def test_desktop_layout_fills_viewport_and_footer_is_pushed_down():
    text = HTML.read_text(encoding='utf-8')
    assert 'v1.4.5 — desktop balance' in text
    assert '.shell{min-height:100dvh;align-items:stretch}' in text
    assert '.side{height:100dvh;min-height:100dvh;align-self:start}' in text
    assert 'min-height:100dvh;max-width:none;display:flex;flex-direction:column;' in text
    assert '.main>.ownership{margin-top:auto;' in text


def test_desktop_balance_is_scoped_to_desktop_breakpoint():
    text = HTML.read_text(encoding='utf-8')
    marker = '@media(min-width:1001px){'
    pos = text.index('v1.4.5 — desktop balance')
    start = text.rfind(marker, 0, pos)
    assert start >= 0
    assert text.find('@media(max-width:720px)', pos) > pos
