from services.case_domain_classifier import classify_case


def test_inheritance_damage_keeps_merits_and_secondary_lanes():
    text = (
        'Ada seorang duda dengan 1 anak kandung. Ayah punya sawah bersertifikat lalu menikah lagi '
        'dan meninggal. Ibu tiri ingin menguasai sawah dan merobek sertifikat. '
        'Pertanyaan legitime portie dan langkah kuasa hukum anak kandung.'
    )
    r = classify_case(text)
    assert r['primary_domain'] == 'inheritance'
    assert r['posture'] == 'WARIS_LITIGASI'
    assert 'land_property' in r['domain_contract']
    assert 'criminal' in r['domain_contract']


def test_replik_inheritance_keeps_procedure_secondary():
    text = (
        'REPLIK perkara perdata. Penggugat menolak eksepsi obscuur libel dan plurium litis consortium. '
        'Sengketa mengenai Sertipikat Hak Milik dan pembagian waris.'
    )
    r = classify_case(text)
    assert r['primary_domain'] == 'inheritance'
    assert r['posture'] == 'PERDATA_LITIGASI'
    assert 'civil_procedure' in r['domain_contract']
    assert 'land_property' in r['domain_contract']


def test_wanprestasi_pleading_is_contract_not_procedure_primary():
    r = classify_case(
        'Penggugat mengajukan gugatan wanprestasi berdasarkan perjanjian karena tergugat tidak membayar.'
    )
    assert r['primary_domain'] == 'civil_contract'
    assert r['posture'] == 'PERDATA_LITIGASI'
    assert 'civil_procedure' in r['domain_contract']


def test_religious_court_is_forum_lane_when_inheritance_merits_exist():
    r = classify_case(
        'Sengketa waris Islam diajukan ke Pengadilan Agama mengenai ahli waris dan pembagian waris.'
    )
    assert r['primary_domain'] == 'inheritance'
    assert 'religious_court' in r['domain_contract']


def test_generic_inheritance_remains_fail_closed():
    r = classify_case('Persoalan warisan keluarga perlu dianalisis.')
    assert r['primary_domain'] == 'general_legal'
    assert r['posture'] == 'GENERAL_LEGAL'
