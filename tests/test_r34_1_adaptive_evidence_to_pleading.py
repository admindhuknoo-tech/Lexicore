from services.element_reasoning import build_element_reasoning


def _dkpp_ledger():
    return [
        {'label':'SOURCE FACT','statement':'Teradu ditetapkan sebagai Anggota KPU Kota Batu berdasarkan Surat Keputusan KPU tanggal 11 Juni 2019.'},
        {'label':'ALLEGATION','statement':'Pengadu mendalilkan Teradu masih terlibat dalam kepengurusan Lazismu dan hal tersebut melanggar kode etik penyelenggara pemilu.'},
        {'label':'DOCUMENT','statement':'Bukti T-3 Surat Keputusan Lazismu tanggal 16 Januari 2018 menerima pengunduran diri dan memberhentikan dengan hormat Teradu sebagai Sekretaris.'},
        {'label':'DENIAL / LIMITATION','statement':'Teradu menolak dalil rangkap jabatan, telah mengundurkan diri, dan menyatakan kehadiran pada kegiatan hanya sebagai narasumber, bukan pengurus.'},
        {'label':'SOURCE FACT','statement':'Nama Teradu kembali muncul dalam dokumen organisasi pada 2021 lalu dilakukan pengunduran diri kembali dan nama dihapus.'},
        {'label':'ALLEGATION','statement':'Pengadu mempersoalkan kehadiran Teradu dalam kegiatan Lazismu dan menilai ada konflik kepentingan.'},
        {'label':'SOURCE FACT','statement':'Dokumen pendidikan menyebut kegiatan studi pada 2018 sampai 2020 dan perlu diuji apakah mengganggu tugas KPU.'},
        {'label':'DENIAL / LIMITATION','statement':'Tidak ada bukti keuntungan pribadi atau keputusan KPU dipengaruhi kepentingan organisasi.'},
    ]


def test_r34_1_builds_four_electoral_issue_tests_with_element_level_sources():
    out=build_element_reasoning(
        domain_contract={'primary_domain':'electoral_ethics','domain_contract':['electoral_ethics']},
        ledger=_dkpp_ledger(),
        existing_matrix=[],
    )
    issues=out['issue_element_tests']
    assert len(issues)==4
    assert {i['id'] for i in issues}=={
        'organization_status','appearance_affiliation','professional_activity','document_integrity'
    }
    assert all(i['elements'] for i in issues)
    assert all(i['legal_conclusion']=='VERIFICATION_REQUIRED' for i in issues)
    assert all(all(0.0 <= e['mapping_confidence'] <= 0.92 for e in i['elements']) for i in issues)


def test_r34_1_never_auto_marks_elements_proven_or_legal_satisfaction():
    out=build_element_reasoning(
        domain_contract={'primary_domain':'electoral_ethics','domain_contract':['electoral_ethics']},
        ledger=_dkpp_ledger(), existing_matrix=[])
    allowed={'NOT_ESTABLISHED','PARTIALLY_SUPPORTED','COUNTER_EVIDENCE_ONLY','DISPUTED'}
    assert all(e['status'] in allowed for e in out['element_matrix'])
    assert out['element_test_summary']['legal_satisfaction_claimed'] is False
    assert all(i['status'] in allowed for i in out['issue_element_tests'])


def test_r34_1_builds_risk_mitigation_and_pleading_posture_fail_closed():
    out=build_element_reasoning(
        domain_contract={'primary_domain':'electoral_ethics','domain_contract':['electoral_ethics']},
        ledger=_dkpp_ledger(), existing_matrix=[])
    assert len(out['risk_assessment'])==4
    assert out['mitigation_strategy']['verification_required'] is True
    assert out['mitigation_strategy']['corrective_action']
    assert out['pleading_strategy']['output_readiness']=='WORKING_DRAFT_ONLY'
    assert out['pleading_strategy']['requires_professional_verification'] is True
    assert 'REQUEST_PROPORTIONAL_OUTCOME_IF_LIMITED_BREACH_IS_ESTABLISHED' in out['pleading_strategy']['strategy_sequence']


def test_r34_1_civil_and_employment_issue_templates_exist_without_touching_verification_plumbing():
    civil=build_element_reasoning(
        domain_contract={'primary_domain':'civil_contract','domain_contract':['civil_contract']},
        ledger=[{'label':'DOCUMENT','statement':'Perjanjian mengatur pembayaran jatuh tempo, lalu somasi dikirim setelah pembayaran tidak dilakukan.'}],
        existing_matrix=[])
    employment=build_element_reasoning(
        domain_contract={'primary_domain':'employment','domain_contract':['employment']},
        ledger=[{'label':'DOCUMENT','statement':'Pekerja menerima surat PHK setelah perundingan bipartit dan menuntut pesangon.'}],
        existing_matrix=[])
    assert len(civil['issue_element_tests'])==3
    assert len(employment['issue_element_tests'])==3
    assert civil['pleading_strategy']['requires_professional_verification'] is True
    assert employment['pleading_strategy']['requires_professional_verification'] is True
