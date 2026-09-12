from services.document_ocr import OCRDiagnostics
from services.element_reasoning import build_element_reasoning


def test_r34_ocr_majority_unreadable_requires_manual_review_but_preserves_partial_text_contract():
    d=OCRDiagnostics(pages_total=37,pages_native=0,pages_ocr=7,pages_failed=30,characters_ocr=14315)
    out=d.to_dict()
    assert out['manual_review_required'] is True
    assert out['review_status']=='MANUAL_REVIEW_REQUIRED'
    assert out['coverage_ratio']==round(7/37,4)
    assert out['partial_text_preserved'] is True
    assert any('Manual review diperlukan' in w for w in out['warnings'])


def test_r34_electoral_element_matrix_maps_support_counter_and_nexus_without_claiming_legal_satisfaction():
    ledger=[
        {'label':'SOURCE FACT','statement':'Teradu ditetapkan sebagai Anggota KPU Kota Batu berdasarkan Surat Keputusan KPU tanggal 11 Juni 2019.'},
        {'label':'DENIAL / LIMITATION','statement':'Teradu menolak dalil keterlibatan dan menyatakan telah resmi mengundurkan diri dari kepengurusan organisasi.'},
        {'label':'DOCUMENT','statement':'Bukti T-3 Surat Keputusan Lazismu tanggal 16 Januari 2018 menerima pengunduran diri dan memberhentikan dengan hormat Teradu sebagai Sekretaris.'},
        {'label':'ALLEGATION','statement':'Pengadu mendalilkan Teradu masih terlibat dalam kepengurusan Lazismu dan hal tersebut melanggar kode etik penyelenggara pemilu.'},
    ]
    result=build_element_reasoning(
        domain_contract={'primary_domain':'electoral_ethics','domain_contract':['electoral_ethics']},
        ledger=ledger,
        existing_matrix=[],
    )
    matrix=result['element_matrix']
    assert len(matrix)>=5
    by_id={x['id']:x for x in matrix}
    assert by_id['status_timeline']['supporting_evidence'] or by_id['status_timeline']['counter_evidence']
    assert by_id['material_conduct']['supporting_evidence'] or by_id['material_conduct']['counter_evidence']
    assert result['evidence_to_element_mapping']
    assert result['element_test_summary']['legal_satisfaction_claimed'] is False
    assert result['causation_analysis']['status'] in {
        'DISPUTED','PARTIAL_NEXUS_IDENTIFIED','COUNTER_EVIDENCE_PRESENT','NEXUS_NOT_ESTABLISHED'
    }


def test_r34_existing_specialized_matrix_is_preserved_and_enriched_not_replaced():
    existing=[
        {'element':'Kausalitas','prosecution_support':'Persetujuan dapat dihubungkan ke pencairan.','defense_focus':'Uji intervening acts.','status':'DISPUTED'},
        {'element':'Mens rea / tujuan menguntungkan','prosecution_support':'Perlu bukti motif.','defense_focus':'Uji aliran dana.','status':'EVIDENCE NEEDED'},
    ]
    ledger=[
        {'label':'SOURCE FACT','statement':'Keputusan persetujuan kredit diikuti pencairan dan kemudian terjadi gagal bayar.'},
        {'label':'DENIAL / LIMITATION','statement':'Terdapat tindakan debitur setelah pencairan yang dapat menjadi intervening act terhadap kerugian.'},
    ]
    result=build_element_reasoning(
        domain_contract={'primary_domain':'corruption','domain_contract':['corruption','criminal']},
        ledger=ledger,
        existing_matrix=existing,
    )
    assert len(result['element_matrix'])==2
    assert result['element_matrix'][0]['element']=='Kausalitas'
    assert result['element_matrix'][0]['prior_status']=='DISPUTED'
    assert result['element_test_summary']['total']==2
