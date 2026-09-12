from services.material_tempus_extractor import (
    extract_material_tempus_candidates,
    select_material_tempus,
)


def test_explicit_date_without_word_tanggal_is_temporal_anchor():
    result = select_material_tempus('Teradu mengundurkan diri dari kepengurusan 16 Januari 2018.')
    assert result['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert result['value'] == '2018-01-16'


def test_ocr_line_break_between_material_event_and_date_is_recovered():
    text = 'Teradu mengundurkan diri dari kepengurusan organisasi\n16 Januari 2018\nNomor Pengaduan 22/DKPP/2021.'
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert result['value'] == '2018-01-16'


def test_procedural_dates_do_not_compete_with_material_status_date():
    text = (
        'Teradu mengundurkan diri pada 16 Januari 2018. '
        'Pengaduan diajukan pada tanggal 3 April 2021. '
        'Sidang dilaksanakan tanggal 20 Oktober 2021.'
    )
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert result['value'] == '2018-01-16'


def test_unique_conduct_date_outranks_unrelated_status_chronology():
    text = (
        'Teradu diangkat sebagai pengurus pada tanggal 11 Juni 2019. '
        'Pelanggaran dilakukan pada tanggal 3 April 2021. '
        'Teradu diberhentikan pada tanggal 9 September 2021.'
    )
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert result['value'] == '2021-04-03'
    assert result['candidate']['event_tier'] == 2


def test_multiple_competing_conduct_dates_remain_fail_closed():
    text = (
        'Pelanggaran dilakukan pada tanggal 3 April 2021. '
        'Perbuatan dilakukan kembali pada tanggal 5 April 2021.'
    )
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_AMBIGUOUS'
    assert result['value'] is None


def test_multiple_status_dates_remain_ambiguous_when_no_conduct_date():
    text = (
        'Teradu mengundurkan diri pada tanggal 16 Januari 2018. '
        'Teradu ditetapkan sebagai anggota pada tanggal 11 Juni 2019.'
    )
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_AMBIGUOUS'


def test_regulation_and_complaint_only_dates_remain_unknown():
    text = (
        'Undang-Undang Nomor 7 Tahun 2017 diundangkan pada tanggal 16 Agustus 2017. '
        'Nomor Pengaduan 157-P/L-DKPP/VII/2021. Pengaduan diajukan pada tanggal 3 April 2021.'
    )
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_UNKNOWN'
    assert result['value'] is None


def test_candidate_provenance_includes_event_tier_and_context():
    rows = extract_material_tempus_candidates('Pelanggaran dilakukan pada 3 April 2021.')
    material = [row for row in rows if row['role'] == 'material_event']
    assert material
    assert material[0]['event_tier'] == 2
    assert material[0]['context']
    assert 'explicit_temporal_anchor' in material[0]['reasons']


def test_year_only_requires_explicit_temporal_language():
    result = select_material_tempus('Pelanggaran terkait kegiatan organisasi 2021.')
    assert result['status'] == 'MATERIAL_TEMPUS_UNKNOWN'


def test_material_year_with_explicit_temporal_grammar_is_candidate():
    result = select_material_tempus('Pada tahun 2021 dilakukan pelanggaran terhadap kewajiban jabatan.')
    assert result['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert result['value'] == '2021'
    assert result['precision'] == 'year'


def test_r30_credit_agreement_material_date_regression_is_preserved():
    text = (
        'Berita Acara Pemeriksaan tanggal 21 Mei 2026. '
        'Perjanjian Kredit ditandatangani pada tanggal 27 September 2022. '
        'POJK diundangkan tanggal 23 November 2022.'
    )
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert result['value'] == '2022-09-27'


def test_procedural_hearing_date_is_not_handed_to_adjacent_generic_conduct_sentence():
    text = (
        'Mobil Honda Jazz tahun 2020 dijadikan agunan. '
        'Surat dakwaan dibacakan dalam persidangan tanggal 31 Agustus 2026. '
        'Perbuatan didakwakan melanggar Undang-Undang Nomor 31 Tahun 1999. '
        'Tanggal atau periode pemberian kredit tidak disebutkan.'
    )
    result = select_material_tempus(text)
    assert result['status'] == 'MATERIAL_TEMPUS_UNKNOWN'
    assert result['value'] is None
