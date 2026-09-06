from services.legal_review_engine import build_professional_review


def test_professional_review_eksepsi_mult_pass_guard():
    text='''
    EKSEPSI Perkara 92/PID.SUS.TPK/2026/PN.SBY. Terdakwa Elya Dwi Admoko.
    Perbuatan dianggap melanggar Pasal 603 UU Nomor 1 Tahun 2003 jo UU Nomor 31 Tahun 2099
    sebagaimana diubah dengan UU Nomor 20 Tahun 2021. Terdakwa adalah Direktur Utama PD BPR.
    Pemberian kredit Rp255.000.000 melebihi plafon dan dijamin Honda Jazz tahun 2020.
    SK Walikota Nomor 188/591/HK/410.010.2/2021 tanggal 05 September 2011.
    Eksepsi menyatakan Pengadilan Tipikor tidak berwenang karena perkara seharusnya penggelapan
    atas barang fidusia dan menyebut Error in Persona.
    '''
    result={
      'source_text':text,
      'source_ledger':[{'label':'SOURCE FACT','statement':'Pemberian kredit melebihi plafon dan dijamin kendaraan.'}],
      'evidentiary_gaps':['Laporan audit kerugian aktual belum tersedia.'],
      'reasoning_guard':{
        'flags':{'fiduciary_nexus':True,'objection_context':True},
        'tempus':{'status':'TEMPUS_INSUFFICIENT','note':'Tempus belum cukup.'},
        'citation_anomalies':[{'source_text':'UU Nomor 31 Tahun 2099','candidate_normalization':'Kandidat: UU Nomor 31 Tahun 1999','instruction':'Cocokkan dokumen asli.'}],
        'boundary_checks':[{'code':'FORUM_VS_MERITS','finding':'Forum dan merits harus dipisahkan.','required_check':'Uji dakwaan asli.'}],
      },
      'evidence_hygiene':{'raw_source_items':10,'user_visible_material_items':3,'classification_counts':{'DOCUMENT_METADATA':4,'CASE_FACT':3}},
      'case_regulatory_snapshot':{'retrieval_funnel':{'verified_applicable':0}},
    }
    review=build_professional_review(result,text)
    assert review['engine']=='LEXICORE_PROFESSIONAL_REVIEW_V1'
    assert review['policy']=='MULTI_PASS_FAIL_CLOSED'
    assert review['document_structure']['document_type']=='EKSEPSI_OR_OBJECTION'
    types={f['type'] for f in review['findings']}
    assert 'TEMPUS_GAP' in types
    assert 'LEGAL_CITATION_ANOMALY' in types
    assert 'NUMBER_DATE_INCONSISTENCY' in types
    assert 'FORUM_VS_MERITS' in types
    assert 'EVIDENTIARY_GAP' in types
    assert review['review_status']=='HOLD_FOR_VERIFICATION'
    assert review['strategic_recommendation']['approach']=='REBUILD_OBJECTION_AROUND_FORMAL_DEFECTS'
    assert any('forum' in x.lower() or 'formil' in x.lower() for x in review['strategic_recommendation']['priorities'])


def test_professional_review_does_not_turn_metadata_into_strength():
    text='''Penasehat hukum beralamat di Jl. Kertarejasa, telp 0341-454415, email counsel@example.com.
    Gugatan wanprestasi atas perjanjian sewa tertulis.'''
    result={
      'source_text':text,
      'source_ledger':[
        {'label':'SOURCE FACT','statement':'Jl. Kertarejasa telp 0341-454415 email counsel@example.com'},
        {'label':'DOCUMENT','statement':'Perjanjian sewa tanggal 1 Januari 2026'},
      ],
      'reasoning_guard':{'flags':{},'tempus':{'status':'TEMPUS_NOT_TRIGGERED'},'citation_anomalies':[],'boundary_checks':[]},
      'evidence_hygiene':{'raw_source_items':2,'user_visible_material_items':1,'classification_counts':{'DOCUMENT_METADATA':1,'ACTUAL_EVIDENTIARY_ITEM':1}},
      'case_regulatory_snapshot':{'retrieval_funnel':{'verified_applicable':0}},
    }
    review=build_professional_review(result,text)
    joined=' '.join(review['strengths']).lower()
    assert 'alamat' not in joined
    assert 'telepon' not in joined
    assert 'email' not in joined
