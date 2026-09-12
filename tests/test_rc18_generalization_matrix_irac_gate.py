from services.case_domain_classifier import classify_case
from services.case_working_paper import build_case_working_paper


def _base(dc, action_plan=None):
    return {
        'domain_classification': dc,
        'case_posture': dc.get('posture'),
        'action_plan': action_plan or [],
        'case_readiness': {'components': {}},
        'source_ledger': [],
        'legal_issues': ['Apakah posisi hukum para pihak didukung bukti dan norma yang berlaku?'],
        'evidentiary_gaps': [],
        'arguments_for': [],
        'arguments_against': [],
        'case_regulatory_snapshot': {'official_results': []},
    }


def test_classifier_adds_formal_legal_area_and_user_position_without_breaking_domain_contract():
    text=(
        'Jawaban Tergugat atas Gugatan Penggugat mengenai wanprestasi perjanjian. '
        'Tergugat menolak seluruh dalil gugatan.'
    )
    c=classify_case(text)
    assert c['primary_domain'] in ('civil_procedure','civil_contract')
    assert c['ranah_hukum']=='PERDATA'
    assert c['posisi_pengguna']=='TERGUGAT'
    assert c['posisi_pengguna_confidence']=='HIGH'
    assert 'domain_contract' in c


def test_unknown_inheritance_case_does_not_fall_through_to_corruption():
    c=classify_case('Para ahli waris mempersoalkan pembagian warisan dan harta waris setelah pewaris meninggal dunia.')
    assert c['posture']=='GENERAL_LEGAL'
    assert c['primary_domain']=='general_legal'
    assert c['primary_domain']!='corruption'
    assert c['forum_screen']['inheritance_detected'] is True


def test_tactical_matrix_uses_legal_area_and_position_with_generic_fallback():
    dc=classify_case('Jawaban Tergugat atas Gugatan Penggugat mengenai wanprestasi perjanjian. Tergugat menolak dalil gugatan.')
    wp=build_case_working_paper(_base(dc))
    actions=' '.join(x['action'].lower() for x in wp['action_plan'])
    assert 'jawaban per dalil' in actions
    assert all(x.get('ranah_hukum') in (None,'PERDATA') for x in wp['action_plan'])

    unknown=classify_case('Hubungan para pihak dan dokumen transaksi baru perlu diperiksa lebih lanjut tanpa klasifikasi yang pasti.')
    wp2=build_case_working_paper(_base(unknown))
    actions2=' '.join(x['action'].lower() for x in wp2['action_plan'])
    assert 'kronologi material' in actions2


def test_action_planner_blocks_unverified_specific_article_recommendation():
    dc=classify_case('Jawaban Tergugat atas Gugatan Penggugat mengenai wanprestasi perjanjian. Tergugat menolak dalil gugatan.')
    result=_base(dc,[{
        'priority':'P1',
        'action':'Gunakan Pasal 2 UU Nomor 1 Tahun 2015 sebagai dasar tindakan.',
        'issue':'Dasar hukum',
    }])
    wp=build_case_working_paper(result)
    actions=[x['action'] for x in wp['action_plan']]
    assert not any('Gunakan Pasal 2' in x for x in actions)
    assert any(x.get('condition')=='LEGAL_VERIFICATION_REQUIRED' for x in wp['action_plan'])


def test_legal_construction_exposes_explicit_irac_contract():
    dc=classify_case('Jawaban Tergugat atas Gugatan Penggugat mengenai wanprestasi perjanjian. Tergugat menolak dalil gugatan.')
    wp=build_case_working_paper(_base(dc))
    lc=wp['legal_construction']
    assert lc['reasoning_model']=='IRAC_DETERMINISTIC_FAIL_CLOSED'
    assert lc['chains']
    irac=lc['chains'][0]['irac']
    assert set(irac)=={'issue','rule','application','conclusion'}
    assert irac['conclusion']
