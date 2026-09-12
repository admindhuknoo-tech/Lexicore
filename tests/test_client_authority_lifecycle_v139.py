from pathlib import Path
import re

from client_communication import build_client_communication

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'static' / 'index.html'


def source():
    return HTML.read_text(encoding='utf-8')


def nav_panels(s):
    start = s.index('<nav class="nav"')
    end = s.index('</nav>', start)
    return re.findall(r'data-panel="([^"]+)"', s[start:end])


def test_lifecycle_places_draft_immediately_after_client_and_contract_review_is_separate_work_module():
    s = source()
    assert nav_panels(s) == ['client', 'draft', 'review', 'case', 'corpus', 'risk', 'research', 'norm']
    assert 'Legal Drafting / Authority' in s
    assert '>Contract Review<' in s
    assert 'Contract / Engagement Review' not in s


def test_dashboard_cards_follow_same_lifecycle_order():
    s = source()
    start = s.index('<div class="cards" aria-label="Lifecycle workspace">')
    end = s.index('</div><div class="workspace-subnav-host"', start)
    cards = s[start:end]
    assert re.findall(r'data-panel="([^"]+)"', cards) == ['client', 'draft', 'review', 'case', 'corpus', 'risk', 'research', 'norm']


def test_client_adds_legal_service_branch_with_consultation_and_representation_request():
    s = source()
    assert '<option value="legal_service">Layanan Jasa Hukum</option>' in s
    assert '<option value="consultation">Konseling / Konsultasi Hukum</option>' in s
    assert '<option value="representation_request">Permintaan Menjadi Kuasa Hukum</option>' in s
    assert 'id="clientServiceBranch"' in s
    assert 'id="clientAuthorityNote"' in s


def test_representation_request_routes_to_surat_kuasa_draft_not_contract_review():
    s = source()
    start = s.index('function startRepresentationDraft()')
    end = s.index('function clientNavigateSection', start)
    body = s[start:end]
    assert "activatePanel('draft')" in body
    assert "o.value==='Surat Kuasa Khusus'" in body
    assert "docType.value='Surat Kuasa Khusus'" in body
    assert "activatePanel('review')" not in body
    assert "party1.value=(cName.value||'').trim()" in body


def test_consultation_document_explicitly_does_not_imply_power_of_attorney():
    d = build_client_communication({
        'document_type': 'legal_service_consultation',
        'client_name': 'Klien Uji',
        'matter': 'Matter Uji',
        'progress': 'Konsultasi awal',
        'next_step': 'Menelaah dokumen',
    })
    assert d['professional_status'] == 'DRAFT_FOR_LAWYER_REVIEW'
    assert 'konseling/konsultasi hukum' in d['message'].lower()
    assert 'tidak dengan sendirinya merupakan pemberian kuasa' in d['message'].lower()
    assert 'Surat Kuasa' in d['message']
