from services.case_domain_classifier import classify_case
from services.document_posture_resolver import resolve_document_posture
from services.legal_review_engine import build_professional_review
from services.material_tempus_extractor import select_material_tempus
from services.regulatory_retrieval import retrieve_for_case_dynamic
from norm_conflict import analyze_conflicts


def _dkpp_text():
    return (
        'KOMISI PEMILIHAN UMUM KOTA BATU JAWABAN ATAS LAPORAN DUGAAN PELANGGARAN KODE ETIK. '
        'Dalam Pokok Aduan, Teradu menolak seluruh dalil Pengadu dan memberikan sanggahan. '
        'Teradu nyata-nyata telah resmi mengundurkan diri dan diberhentikan dengan hormat sejak tanggal 16 Januari 2018. '
        'Teradu kemudian ditetapkan sebagai Anggota KPU pada tanggal 11 Juni 2019. '
        'Pengaduan diterima pada tanggal 5 Maret 2021.'
    )


def test_canonical_posture_resolver_projects_dkpp_response_not_eksepsi():
    text = _dkpp_text()
    dc = classify_case(text)
    posture = resolve_document_posture(dc, {'source_text': text})
    assert posture['posture'] == 'RESPONSE_TO_COMPLAINT'
    assert posture['document_type'] == 'Jawaban atas Pengaduan Etik'
    assert posture['issue_label'] == 'Pokok Aduan'
    assert posture['remedy_label'] == 'Petitum Jawaban'


def test_professional_review_uses_canonical_response_posture_end_to_end():
    text = _dkpp_text()
    dc = classify_case(text)
    result = {
        'source_text': text,
        'domain_classification': dc,
        'source_ledger': [],
        'reasoning_guard': {},
        'case_regulatory_snapshot': {'retrieval_funnel': {'verified_applicable': 0}},
        'evidentiary_gaps': [],
    }
    review = build_professional_review(result, text)
    assert review['document_structure']['display_document_type'] == 'Jawaban atas Pengaduan Etik'
    strategy = review['strategic_recommendation']
    material = ' '.join(strategy.get('priorities', []) + strategy.get('recommended_outline', [])).lower()
    assert 'surat dakwaan' not in material
    assert 'bangun ulang eksepsi' not in material
    assert 'pokok aduan' in material


def test_regulatory_retrieval_reuses_single_canonical_material_tempus_selection():
    text = _dkpp_text()
    selected = select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert selected['value'] == '2018-01-16'
    snap = retrieve_for_case_dynamic(
        text=text,
        title='DKPP benchmark',
        provision_refs=[],
        qualified_queries=[],
        local_seed_matches=[],
        legal_issues=[],
        online=False,
        retrieval_mode='offline',
        domain_classification=classify_case(text),
        material_tempus_selection=selected,
    )
    assert snap['event_date_candidate'] == '2018-01-16'
    assert snap['event_year_candidate'] == 2018
    assert snap['material_tempus']['selection_basis'] == selected['selection_basis']


def test_norm_conflict_does_not_emit_unrelated_none_pseudo_conflicts():
    nc = analyze_conflicts(
        [
            'Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum',
            'Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur Bupati dan Walikota',
            'Peraturan DKPP Nomor 2 Tahun 2019 tentang Kode Etik',
        ],
        facts_context='Pengadu menyatakan satu tindakan bertentangan dengan kewajiban etik, tetapi tidak menyatakan norma-norma tersebut saling bertentangan.',
        regulatory_matches=[],
    )
    assert nc['status'] == 'NO_MATERIAL_NORM_CONFLICT_IDENTIFIED'
    assert nc['count'] == 0
    assert nc['conflicts_detected'] == []
