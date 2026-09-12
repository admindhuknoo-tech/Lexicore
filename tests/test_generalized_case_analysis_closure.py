from services.material_tempus_extractor import select_material_tempus
from services.general_case_orchestrator import infer_document_posture, apply_general_case_orchestration


def test_dkpp_style_response_is_structural_response_not_criminal_template():
    text = '''
    KOMISI PEMILIHAN UMUM KOTA BATU
    JAWABAN ATAS LAPORAN DUGAAN PELANGGARAN KODE ETIK
    Dalam Pokok Aduan: Teradu menolak seluruh dalil yang diadukan Pengadu.
    Teradu memberikan sanggahan terhadap pokok aduan.
    '''
    p = infer_document_posture(text)
    assert p['posture'] == 'RESPONSE_TO_COMPLAINT'
    assert 'Jawaban' in p['document_type']


def test_generated_template_leak_is_normalized_but_source_is_preserved():
    text = 'JAWABAN ATAS PENGADUAN. Dalam Pokok Aduan Teradu membantah dalil Pengadu.'
    result = {
        'source_text': 'kutipan sumber: kata dakwaan hanya jika memang ada',
        'executive_review': {'document_type': 'Eksepsi / nota keberatan', 'advice': 'serang surat dakwaan dan petitum eksepsi'},
        'norm_conflicts': [{'status': 'NONE'}, {'status': 'NONE'}],
    }
    out = apply_general_case_orchestration(result, text)
    assert out['source_text'] == result['source_text']
    assert 'pokok aduan' in out['executive_review']['advice'].lower()
    assert 'petitum jawaban' in out['executive_review']['advice'].lower()
    assert out['norm_conflicts']['status'] == 'NO_MATERIAL_NORM_CONFLICT_IDENTIFIED'


def test_material_tempus_prefers_strong_event_date_ownership_over_procedural_date():
    text = '''
    Pengaduan diterima pada tanggal 5 Maret 2021.
    Teradu nyata-nyata telah resmi mengundurkan diri dan diberhentikan dengan hormat sejak tanggal 16 Januari 2018.
    Teradu ditetapkan sebagai Anggota KPU Kota berdasarkan Surat Keputusan KPU Nomor 1052/PP.06-Kpt/05/KPU/VI/2019 tanggal 11 Juni 2019.
    '''
    selected = select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert selected['value'] == '2018-01-16'


def test_statute_year_and_hearing_date_do_not_become_material_tempus():
    text = (
        'Mobil Honda Jazz tahun 2020 dijadikan agunan. '
        'Surat dakwaan dibacakan dalam persidangan tanggal 31 Agustus 2026. '
        'Perbuatan didakwakan melanggar Undang-Undang Nomor 31 Tahun 1999. '
        'Tanggal atau periode pemberian kredit tidak disebutkan.'
    )
    selected = select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_UNKNOWN'
