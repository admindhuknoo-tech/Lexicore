from services.positive_law_verification import (
    extract_status_metadata, verify_document_candidate, verify_tempus,
)


def test_explicit_bpk_style_in_force_and_tempus():
    text=(
        'Undang-Undang (UU) Nomor 7 Tahun 1989 tentang Peradilan Agama. '
        'Berlaku mulai 29 Desember 1989. Status Peraturan. Diubah dengan '
        'Undang-Undang Nomor 3 Tahun 2006.'
    )
    row={'title':'UU Nomor 7 Tahun 1989 tentang Peradilan Agama',
         'query':'UU Peradilan Agama Pasal 49 kewenangan absolut','authoritative':True,
         'case_nexus_status':'CASE_NEXUS_VERIFIED'}
    out=verify_document_candidate(row,source_text=text,snapshot={'procedural_date_candidate':'2026-06-03'})
    assert out['identity_confirmed'] is True
    assert out['legal_status']=='AMENDED_IN_FORCE'
    assert out['effective_date']=='1989-12-29'
    assert out['tempus_status']=='TEMPUS_VERIFIED'
    assert out['final_status']=='VERIFIED_APPLICABLE'


def test_repeal_without_repeal_date_is_fail_closed():
    text=('Peraturan Pemerintah Nomor 10 Tahun 1961. Berlaku mulai 23 Maret 1961. '
          'Dicabut dengan Peraturan Pemerintah Nomor 24 Tahun 1997. Ketentuan Peralihan.')
    row={'title':'PP No. 10 Tahun 1961','query':'PP 10 Tahun 1961','authoritative':True}
    out=verify_document_candidate(row,source_text=text,snapshot={'event_date_candidate':'1995-01-01'})
    assert out['legal_status']=='REVOKED'
    assert out['final_status']!='VERIFIED_APPLICABLE'


def test_missing_effective_date_never_verifies_tempus():
    x=verify_tempus(effective_date=None,anchor_value='2026-06-03',revoked=False,transitional_rule_found=False)
    assert x['status']=='TEMPUS_UNVERIFIED'
    assert x['applicable'] is None


def test_official_news_is_rejected_as_non_legal_content():
    from services.positive_law_verification import classify_legal_document_candidate
    row={
        'title':'JDIH Kementerian ATR/BPN Terima Kunjungan Kerja Pengelola JDIH Kabupaten Banyuwangi',
        'query':'PP pendaftaran tanah sertipikat hak milik',
        'authoritative':True,
    }
    out=classify_legal_document_candidate(row)
    assert out['legal_instrument_candidate'] is False
    assert out['document_class']=='NON_LEGAL_CONTENT'


def test_exact_known_regulation_is_admitted_and_nexus_can_verify():
    from services.positive_law_verification import classify_legal_document_candidate
    row={
        'title':'Peraturan Pemerintah Nomor 24 Tahun 1997 tentang Pendaftaran Tanah',
        'query':'Peraturan Pemerintah Nomor 24 Tahun 1997 Pendaftaran Tanah',
        'authoritative':True,
        'case_nexus_status':'CASE_NEXUS_VERIFIED',
    }
    gate=classify_legal_document_candidate(row)
    assert gate['legal_instrument_candidate'] is True
    text=(
        'Peraturan Pemerintah Republik Indonesia Nomor 24 Tahun 1997 tentang Pendaftaran Tanah. '
        'Tanggal Berlaku 8 Oktober 1997. Status Peraturan: Berlaku.'
    )
    out=verify_document_candidate(row,source_text=text,snapshot={'procedural_date_candidate':'2026-06-03'})
    assert out['identity_confirmed'] is True
    assert out['legal_status']=='IN_FORCE'
    assert out['tempus_status']=='TEMPUS_VERIFIED'
    assert out['case_nexus_status']=='CASE_NEXUS_VERIFIED'
    assert out['final_status']=='VERIFIED_APPLICABLE'


def test_verified_status_and_tempus_are_counted_independently_from_final():
    from services.regulatory_retrieval import _summarize_positive_law_verification
    rows=[
        {'positive_law_verification':{
            'identity_confirmed':True,'legal_status':'IN_FORCE',
            'tempus_status':'TEMPUS_VERIFIED','final_status':'VERIFIED_APPLICABLE'}},
        {'positive_law_verification':{
            'identity_confirmed':True,'legal_status':'IN_FORCE',
            'tempus_status':'TEMPUS_VERIFIED','final_status':'VERIFIED_NOT_RELEVANT'}},
        {'positive_law_verification':{
            'identity_confirmed':False,'legal_status':'IN_FORCE',
            'tempus_status':'TEMPUS_VERIFIED','final_status':'UNVERIFIED_IDENTITY_MISMATCH'}},
    ]
    out=_summarize_positive_law_verification(rows)
    assert out['positive_law_verified']==2
    assert out['tempus_verified']==2
    assert out['verified_applicable']==1


def test_case_nexus_exact_query_does_not_preverify_search_hit():
    from services.positive_law_verification import evaluate_case_nexus
    row={
        'title':'Perubahan Atas Undang-Undang Nomor 5 Tahun 1986 tentang Peradilan Tata Usaha Negara',
        'query':'Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama',
    }
    out=evaluate_case_nexus(row,['religious_court','civil_procedure'])
    assert out['status']=='NO_CASE_NEXUS'


def test_known_regulation_nexus_promotes_only_after_identity_confirmation():
    from services.positive_law_verification import evaluate_case_nexus, verify_document_candidate
    row={
        'title':'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama',
        'query':'Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama',
        'authoritative':True,
        'query_origin':'KNOWN_REGULATION',
        'case_nexus_domains':['religious_court'],
    }
    pre=evaluate_case_nexus(row,['religious_court','civil_procedure'])
    assert pre['status']=='CASE_NEXUS_UNCERTAIN'
    row['case_nexus_status']=pre['status']
    text=(
        'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama. '
        'Berlaku mulai 29 Desember 1989. Status Peraturan: Berlaku.'
    )
    out=verify_document_candidate(row,source_text=text,snapshot={'procedural_date_candidate':'2026-06-03'})
    assert out['identity_confirmed'] is True
    assert out['case_nexus_status']=='CASE_NEXUS_VERIFIED'
    assert out['final_status']=='VERIFIED_APPLICABLE'


def test_corpus_online_filter_rejects_official_news(monkeypatch):
    import services.legal_research_service as svc
    monkeypatch.setattr(svc,'federated_search',lambda *a,**k:[{
        'source_id':'atr_bpn','source_name':'JDIH ATR/BPN','authoritative':True,
        'results':[{'title':'Sosialisasi JDIH Kementerian ATR/BPN di Kanwil BPN Provinsi Jawa Barat','url':'https://example.go.id/news','score':0.9}]
    }])
    rows,rejected=svc._online_rows('acara perdata',12)
    assert rows==[]
    assert rejected==1


def test_semantic_cleanup_no_case_nexus_uses_not_relevant_final(monkeypatch):
    import services.regulatory_retrieval as rr
    row={
        'title':'Perubahan Atas Undang-Undang Nomor 5 Tahun 1986 tentang Peradilan Tata Usaha Negara',
        'query':'Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama',
        'url':'https://example.go.id/legal','authoritative':True,
        'case_nexus_status':'NO_CASE_NEXUS',
        'document_classification':{'legal_instrument_candidate':True},
    }
    monkeypatch.setattr(rr,'fetch_official_document',lambda *a,**k:{
        'reachable':True,'official_host':True,'content_type':'text/html',
        'body':b'Perubahan Atas Undang-Undang Nomor 5 Tahun 1986. Berlaku mulai 1 Januari 2005. Status Peraturan: Berlaku.'
    })
    out=rr._verify_positive_law_results([row],{'procedural_date_candidate':'2026-06-03'},1)[0]
    v=out['positive_law_verification']
    assert v['identity_confirmed'] is False
    assert v['case_nexus_status']=='NO_CASE_NEXUS'
    assert v['final_status']=='VERIFIED_NOT_RELEVANT'


def test_article_level_verification_finds_exact_pasals_in_official_text():
    from services.positive_law_verification import verify_provisions
    text=(
        'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama. '
        'Pasal 49 Pengadilan Agama bertugas dan berwenang memeriksa perkara tertentu. '
        'Pasal 50 ketentuan berikutnya.'
    )
    out=verify_provisions(['Pasal 49'],text,'https://example.go.id/uu-7-1989')
    assert out['status']=='PROVISION_VERIFIED'
    assert out['verified']==['Pasal 49']
    assert out['verified_count']==1
    assert out['citations'][0]['source_url']=='https://example.go.id/uu-7-1989'


def test_article_level_verification_is_fail_closed_when_article_absent():
    from services.positive_law_verification import verify_provisions
    out=verify_provisions(['Pasal 49'],'Undang-Undang Nomor 7 Tahun 1989. Status Peraturan: Berlaku.','https://example.go.id/x')
    assert out['status']=='PROVISION_UNVERIFIED'
    assert out['verified_count']==0
    assert out['unverified']==['Pasal 49']


def test_local_matched_article_seeds_pasals_for_official_candidate():
    from services.regulatory_retrieval import _attach_requested_provisions
    rows=[{'title':'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama','query':'Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama'}]
    local=[{'regulation':{'nomor':'UU No. 7 Tahun 1989','tentang':'Peradilan Agama'},'matched_articles':[{'pasal':'Pasal 49 (sebagaimana diubah)'}]}]
    out=_attach_requested_provisions(rows,[],local)
    assert out[0]['requested_provisions']==['Pasal 49']


def test_verifier_exposes_provision_verification_without_changing_applicability_logic():
    from services.positive_law_verification import verify_document_candidate
    row={
        'title':'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama',
        'query':'Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama',
        'authoritative':True,'query_origin':'KNOWN_REGULATION',
        'case_nexus_domains':['religious_court'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'requested_provisions':['Pasal 49'],'url':'https://example.go.id/uu-7-1989',
    }
    text=('Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama. '
          'Berlaku mulai 29 Desember 1989. Status Peraturan: Berlaku. '
          'Pasal 49 Pengadilan Agama bertugas dan berwenang.')
    out=verify_document_candidate(row,source_text=text,snapshot={'procedural_date_candidate':'2026-06-03'})
    assert out['final_status']=='VERIFIED_APPLICABLE'
    assert out['provision_verification']['status']=='PROVISION_VERIFIED'
    assert out['provision_verification']['verified']==['Pasal 49']


def test_fulltext_resolver_follows_official_pdf_attachment(monkeypatch):
    import legal_sources as ls
    from io import BytesIO
    from reportlab.pdfgen import canvas
    buf=BytesIO(); c=canvas.Canvas(buf)
    c.drawString(72,760,'Undang-Undang Nomor 3 Tahun 2006 tentang Peradilan Agama')
    c.drawString(72,730,'Pasal 49 Pengadilan Agama bertugas dan berwenang.')
    c.save(); pdf=buf.getvalue()
    monkeypatch.setattr(ls,'fetch_official_document',lambda url,timeout=5:{
        'reachable':True,'official_host':True,'content_type':'application/pdf',
        'body':pdf,'final_url':'https://jdih.example.go.id/files/uu3-2006.pdf'
    })
    html=b'<html><body><a href="/files/uu3-2006.pdf">Download PDF Naskah</a></body></html>'
    out=ls.resolve_official_fulltext('https://jdih.example.go.id/detail/uu3',html,'text/html',requested_provisions=['Pasal 49'])
    assert out['resolved'] is True
    assert out['resolver_status']=='ATTACHMENT_PDF_TEXT'
    assert 'Pasal 49' in out['text']
    assert out['source_url'].endswith('uu3-2006.pdf')


def test_positive_law_pipeline_retries_provision_on_resolved_fulltext(monkeypatch):
    import services.regulatory_retrieval as rr
    row={
        'title':'Perubahan atas Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama',
        'query':'Undang-Undang Nomor 3 Tahun 2006 Perubahan Undang-Undang Nomor 7 Tahun 1989 Peradilan Agama',
        'url':'https://peraturan.example.go.id/detail/uu3-2006','authoritative':True,
        'query_origin':'KNOWN_REGULATION','case_nexus_domains':['religious_court'],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN','requested_provisions':['Pasal 49'],
        'document_classification':{'legal_instrument_candidate':True},
    }
    detail=(b'Undang-Undang Nomor 3 Tahun 2006. Berlaku mulai 20 Maret 2006. '
            b'Status Peraturan: Berlaku. Diubah dengan Undang-Undang Nomor 50 Tahun 2009.')
    monkeypatch.setattr(rr,'fetch_official_document',lambda *a,**k:{
        'reachable':True,'official_host':True,'content_type':'text/html','body':detail,
        'final_url':'https://peraturan.example.go.id/detail/uu3-2006','connectivity_status':'REACHABLE','error':None
    })
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':True,'source_url':'https://peraturan.example.go.id/files/uu3-2006.pdf',
        'content_type':'application/pdf','resolver_status':'ATTACHMENT_PDF_TEXT',
        'attempted_urls':['x'],'candidate_links_found':1,
        'text':'Undang-Undang Nomor 3 Tahun 2006. Pasal 49 Pengadilan Agama bertugas dan berwenang.'
    })
    out=rr._verify_positive_law_results([row],{'procedural_date_candidate':'2026-06-03'},1)[0]
    pv=out['positive_law_verification']['provision_verification']
    assert pv['status']=='PROVISION_VERIFIED'
    assert pv['verified']==['Pasal 49']
    assert pv['citations'][0]['source_url'].endswith('uu3-2006.pdf')
    assert out['fulltext_resolution']['resolver_status']=='ATTACHMENT_PDF_TEXT'
