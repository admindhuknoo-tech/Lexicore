from services.case_domain_classifier import classify_case
from services.material_tempus_extractor import extract_material_tempus_candidates, select_material_tempus
from services import regulatory_retrieval as rr
from regulatory_db import get_all_regulations


def _reg(reg_id):
    return next(r for r in get_all_regulations() if r.get('id') == reg_id)


def test_r30_r28_baseline_contract_is_preserved():
    tipikor=_reg('uu_tipikor_31_1999')
    names=[a.get('pasal') for a in tipikor.get('articles') or []]
    assert tipikor.get('official_url') == 'https://peraturan.bpk.go.id/Details/45350/uu-no-31-tahun-1999'
    for p in ('Pasal 2 ayat (1)','Pasal 3','Pasal 9','Pasal 18'):
        assert p in names
    assert rr.EXACT_CASE_RECOVERY_RESERVE_SECONDS == 4.0


def test_r30_kpk_expansion_from_r29_remains_available():
    kpk=_reg('uu_kpk_30_2002')
    names=[a.get('pasal') for a in kpk.get('articles') or []]
    assert kpk.get('official_url') == 'https://peraturan.bpk.go.id/Details/44493/Undang-Undang-no-30-tahun-2002'
    assert 'Pasal 6' in names and 'Pasal 7' in names
    assert 'Undang-Undang Nomor 30 Tahun 2002 tentang Komisi Pemberantasan Tindak Pidana Korupsi' in rr.KNOWN_REGULATION_QUERIES['corruption']


def test_r30_material_tempus_extracts_explicit_material_date_but_does_not_verify_it():
    text='Persetujuan kredit dilakukan pada tanggal 27 September 2022 dan pencairan dilaksanakan setelah persetujuan tersebut.'
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert selected['value'] == '2022-09-27'
    assert selected['precision'] == 'date'
    # Candidate extraction is discovery only; verify_tempus/applicability remains a separate gate.
    assert 'verified' not in selected
    assert 'applicable' not in selected


def test_r30_material_tempus_rejects_vehicle_year_procedural_date_and_statute_year():
    text=(
        'Mobil Honda Jazz tahun 2020 dijadikan agunan. '
        'Surat dakwaan dibacakan dalam persidangan tanggal 31 Agustus 2026. '
        'Perbuatan didakwakan melanggar Undang-Undang Nomor 31 Tahun 1999. '
        'Tanggal atau periode pemberian kredit tidak disebutkan.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_UNKNOWN'
    assert selected['value'] is None
    assert rr.detect_material_year(text) is None
    assert rr.detect_material_date(text) is None


def test_r30_material_tempus_multiple_material_dates_fail_closed_as_ambiguous():
    text=(
        'Pemberian kredit terjadi pada tanggal 10 Januari 2021. '
        'Pencairan kredit terjadi pada tanggal 15 Februari 2022.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_AMBIGUOUS'
    assert selected['value'] is None


def test_r30_civil_wanprestasi_domain_and_queries_are_reachable():
    text=(
        'Penggugat menggugat Tergugat karena wanprestasi dan cidera janji atas perjanjian jual beli. '
        'Somasi telah dikirim namun pembayaran tetap tidak dilakukan dan Penggugat menuntut ganti rugi.'
    )
    c=classify_case(text)
    assert c['primary_domain'] in {'civil_contract','civil_procedure'}
    assert 'civil_contract' in c['domain_contract']
    domains=rr.detect_domains(text)
    queries=rr.build_case_queries(text,domains=domains,max_queries=20)
    joined='\n'.join(queries).lower()
    assert 'kuhperdata' in joined
    assert ('1238' in joined or '1243' in joined)
    assert '1365' in joined


def test_r30_employment_domain_and_key_routes_are_reachable():
    text=(
        'Pekerja mengalami pemutusan hubungan kerja (PHK) setelah hubungan kerja berdasarkan PKWT. '
        'Perselisihan mengenai pesangon dan upah telah ditempuh melalui bipartit.'
    )
    c=classify_case(text)
    assert c['primary_domain'] == 'employment'
    domains=rr.detect_domains(text)
    queries=rr.build_case_queries(text,domains=domains,max_queries=20)
    joined='\n'.join(queries).lower()
    assert 'ketenagakerjaan' in joined
    assert 'pp 35 tahun 2021' in joined or 'peraturan pemerintah nomor 35 tahun 2021' in joined
    assert 'perselisihan hubungan industrial' in joined


def test_r30_1_bap_credit_date_outranks_procedural_and_regulation_dates():
    text=(
        'Berita Acara Pemeriksaan tanggal 21 Mei 2026. '
        'Diperlihatkan Perjanjian Kredit Nomor 10130003097 tanggal 27 September 2022. '
        'POJK No. 23 Tahun 2022 berlaku 23 November 2022.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert selected['value'] == '2022-09-27'
    assert selected['precision'] == 'date'
    assert rr.detect_material_date(text) == '2022-09-27'


def test_r30_1_regulation_only_dates_do_not_become_material_tempus():
    text=(
        'POJK No. 23 Tahun 2022 berlaku 23 November 2022. '
        'Undang-Undang Nomor 31 Tahun 1999 diundangkan 16 Agustus 1999.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_UNKNOWN'
    assert rr.detect_material_date(text) is None
