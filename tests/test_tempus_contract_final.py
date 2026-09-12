from services.material_tempus_extractor import select_material_tempus


def test_single_material_date_preserves_legacy_selection_basis():
    text=(
        'Teradu mengundurkan diri dari kepengurusan organisasi pada tanggal 16 Januari 2018. '
        'Pengaduan kemudian diajukan pada tanggal 3 April 2021.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert selected['value'] == '2018-01-16'
    assert selected['selection_basis'] == 'UNIQUE_MATERIAL_EVENT_DATE'


def test_two_equal_status_dates_fail_closed_with_legacy_basis():
    text=(
        'Teradu mengundurkan diri pada tanggal 16 Januari 2018. '
        'Teradu kemudian ditetapkan sebagai Anggota KPU pada tanggal 11 Juni 2019.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_AMBIGUOUS'
    assert selected['value'] is None
    assert selected['selection_basis'] == 'MULTIPLE_COMPETING_MATERIAL_EVENT_DATES'


def test_two_competing_credit_dates_fail_closed_even_if_scores_differ():
    text=(
        'Pemberian kredit terjadi pada tanggal 10 Januari 2021. '
        'Pencairan kredit terjadi pada tanggal 15 Februari 2022.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_AMBIGUOUS'
    assert selected['value'] is None
    assert selected['selection_basis'] == 'MULTIPLE_COMPETING_MATERIAL_EVENT_DATES'


def test_strong_lifecycle_ownership_can_resolve_benchmark_without_domain_rule():
    text=(
        'Pengaduan diterima pada tanggal 5 Maret 2021. '
        'Teradu nyata-nyata telah resmi mengundurkan diri dan diberhentikan dengan hormat sejak tanggal 16 Januari 2018. '
        'Teradu ditetapkan sebagai Anggota KPU Kota berdasarkan Surat Keputusan KPU Nomor 1052/PP.06-Kpt/05/KPU/VI/2019 tanggal 11 Juni 2019.'
    )
    selected=select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert selected['value'] == '2018-01-16'
    assert selected['selection_basis'] == 'STRONGEST_EVENT_DATE_OWNERSHIP'
