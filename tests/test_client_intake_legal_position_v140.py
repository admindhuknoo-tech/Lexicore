from pathlib import Path

from client_communication import build_client_communication
from database import EXPECTED_COLUMNS, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'static' / 'index.html'


def source():
    return HTML.read_text(encoding='utf-8')


def test_client_intake_collects_address_and_legal_position():
    s = source()
    assert 'id="cAddress"' in s
    assert 'id="cLegalPosition"' in s
    for value, label in [('suspect','Tersangka'),('defendant','Terdakwa'),('plaintiff','Penggugat'),('respondent','Tergugat')]:
        assert f'<option value="{value}">{label}</option>' in s


def test_legal_position_has_direct_draft_starters_without_auto_generation():
    s = source()
    assert "suspect:{label:'Tersangka',template:'Permohonan Praperadilan'" in s
    assert "defendant:{label:'Terdakwa',template:'Eksepsi Pidana'" in s
    assert "plaintiff:{label:'Penggugat',template:'Gugatan Perdata'" in s
    assert "respondent:{label:'Tergugat',template:'Jawaban Tergugat'" in s
    body = s[s.index('function startLegalPositionDraft()'):s.index('function clientNavigateSection', s.index('function startLegalPositionDraft()'))]
    assert "activatePanel('draft')" in body
    assert 'generateDraft()' not in body
    assert 'kewenangan kuasa tetap wajib diverifikasi' in body


def test_representation_draft_receives_address_and_position_context():
    s = source()
    body = s[s.index('function startRepresentationDraft()'):s.index('function startLegalPositionDraft()', s.index('function startRepresentationDraft()'))]
    assert "party1.value+=' | Alamat: '+(cAddress.value||'').trim()" in body
    assert "'Kedudukan hukum klien: '+cfg.label" in body


def test_client_communications_schema_persists_intake_context():
    cols = {name for name, _ in EXPECTED_COLUMNS['client_communications']}
    assert SCHEMA_VERSION >= 11
    assert {'client_address', 'legal_position'} <= cols


def test_consultation_can_render_position_and_address_as_recorded_context():
    d = build_client_communication({
        'document_type': 'legal_service_consultation',
        'client_name': 'Klien Uji',
        'client_address': 'Jl. Uji 1, Batu',
        'legal_position': 'defendant',
        'matter': 'Perkara Uji',
    })
    assert 'Kedudukan hukum yang dicatat: Terdakwa.' in d['message']
    assert 'Alamat/domisili yang dicatat: Jl. Uji 1, Batu.' in d['message']
