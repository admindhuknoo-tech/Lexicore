from services.document_posture_resolver import resolve_document_posture
from services.element_reasoning import evidence_proposition_admissibility
from services.reasoning_contract import attach_reasoning_contract, validate_reasoning_contract
from services.legal_reasoning_chain import _issue_for_element, _governing_law_compatible


def test_bap_tersangka_is_not_decision():
    text = """KEJAKSAAN NEGERI BLITAR\nBERITA ACARA PEMERIKSAAN TERSANGKA\nSurat Perintah Penyidikan Nomor PRINT-01/2026\nSurat Penetapan Tersangka Nomor 06/2026"""
    r=resolve_document_posture({'ranah_hukum':'PIDANA','posisi_pengguna':'TERSANGKA'},{'source_text':text})
    assert r['posture']=='BAP_TERSANGKA'
    assert r['document_type']=='Berita Acara Pemeriksaan Tersangka'


def test_contextual_facts_do_not_prove_tipikor_elements():
    bad=[
        ('Saya mengerti sehubungan dengan adanya Surat Panggilan Tersangka','Perbuatan melawan hukum/penyalahgunaan kewenangan'),
        ('debitur melakukan pembayaran pinjaman pokok pada akhir perjanjian','Perbuatan melawan hukum/penyalahgunaan kewenangan'),
        ('Bank Perkreditan Rakyat dengan persetujuan Dewan Pengawas','Mens rea / tujuan menguntungkan'),
        ('Kapan dokumen lembar pertimbangan komite kredit tersebut dibuat?','Personal responsibility'),
    ]
    for text,name in bad:
        ok,_=evidence_proposition_admissibility(text, element_name=name, owner_domain='criminal')
        assert not ok


def test_actual_proposition_can_pass():
    ok,_=evidence_proposition_admissibility('Direktur dengan sadar menyetujui kredit untuk menguntungkan pihak terafiliasi', element_name='Mens rea / tujuan menguntungkan', owner_domain='criminal')
    assert ok


def test_tempus_issue_never_owns_causation_element():
    issues=['Tempus delicti dan ketentuan peralihan harus diverifikasi sebelum menetapkan norma pidana materiil yang berlaku.','Apakah terdapat hubungan kausal langsung antara keputusan pihak yang dianalisis dengan kerugian?']
    owner=_issue_for_element({'element':'Kausalitas'},issues)
    assert 'kausal' in owner.lower()
    assert 'tempus' not in owner.lower()


def test_banking_context_law_not_governing_tipikor_loss():
    assert not _governing_law_compatible({'element':'Kerugian keuangan negara/daerah nyata'},'Apakah ada kerugian negara?',{'source':'UU Perbankan','domain':'Perbankan'})
    assert _governing_law_compatible({'element':'Kerugian keuangan negara/daerah nyata'},'Apakah ada kerugian negara?',{'source':'UU Pemberantasan Tindak Pidana Korupsi','domain':'Tipikor'})


def test_semantic_contract_hard_violation_is_fail_not_hold():
    chain={'chains':[{
        'chain_id':'E1','binding_context':{'chain_id':'E1','issue_key':'issue:tempus','element_key':'element:kausalitas'},
        'issue':{'value':'Tempus delicti harus diverifikasi','status':'MAPPED'},
        'applicable_law':{'selected':None,'status':'MISSING'},
        'legal_elements':{'element':'Kausalitas','status':'MAPPED'},
        'alleged_act':{'value':'','status':'MISSING'},
        'evidence':{'items':[],'status':'MISSING'},
        'counter_evidence':{'items':[],'status':'MISSING'},
        'element_test':{'status':'NOT_ESTABLISHED','gate':'HOLD'},
        'causation':{'value':'','status':'GAP'},
        'risk':{'value':'','status':'MAPPED'},
        'procedural_merits_classification':{'value':'MERITS','status':'MAPPED'},
        'recommended_action':{'actions':[],'status':'MISSING'},
    }]}
    r=validate_reasoning_contract(chain)
    assert r['status']=='PASS'
    assert r['semantic_status']=='FAIL'
    assert any(v['status']=='ISSUE_ELEMENT_MISMATCH_TEMPUS_CAUSATION' for v in r['hard_semantic_violations'])
