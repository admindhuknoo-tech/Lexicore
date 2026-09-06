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
    out=verify_document_candidate(row,source_text=text,snapshot={'event_date_candidate':'2020-06-03','procedural_date_candidate':'2026-06-03'})
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


def test_exact_case_tipikor_query_can_promote_nexus_only_after_identity_confirmation():
    from services.positive_law_verification import verify_document_candidate
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'authoritative':True,'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['corruption'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'requested_provisions':['Pasal 3'], 'url':'https://example.go.id/uu-31-1999',
    }
    text=('Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi. '
          'Berlaku mulai 16 Agustus 1999. Status Peraturan: Berlaku. Pasal 3 setiap orang ...')
    out=verify_document_candidate(row,source_text=text,snapshot={'event_date_candidate':'2022-05-01','procedural_date_candidate':'2026-08-31'})
    assert out['identity_confirmed'] is True
    assert out['case_nexus_status']=='CASE_NEXUS_VERIFIED'
    assert out['tempus_status']=='TEMPUS_VERIFIED'
    assert out['final_status']=='VERIFIED_APPLICABLE'
    assert out['provision_verification']['verified']==['Pasal 3']


def test_exact_case_typo_identity_is_not_silently_repaired():
    from services.positive_law_verification import verify_document_candidate
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query':'Undang-Undang Nomor 31 Tahun 2099 tentang Pemberantasan Tindak Pidana Korupsi',
        'authoritative':True,'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['corruption'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
    }
    text=('Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi. '
          'Berlaku mulai 16 Agustus 1999. Status Peraturan: Berlaku.')
    out=verify_document_candidate(row,source_text=text,snapshot={'event_date_candidate':'2022-05-01'})
    assert out['identity_confirmed'] is False
    assert out['case_nexus_status']!='CASE_NEXUS_VERIFIED'
    assert out['final_status']!='VERIFIED_APPLICABLE'


def test_substantive_norm_never_uses_procedural_date_as_tempus_fallback():
    from services.positive_law_verification import verify_document_candidate
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'authoritative':True,'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['corruption'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
    }
    text=('Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi. '
          'Berlaku mulai 16 Agustus 1999. Status Peraturan: Berlaku.')
    out=verify_document_candidate(row,source_text=text,snapshot={'procedural_date_candidate':'2026-08-31'})
    assert out['identity_confirmed'] is True
    assert out['tempus_anchor'] is None
    assert out['tempus_status']=='TEMPUS_UNVERIFIED'
    assert out['final_status']=='POTENTIALLY_APPLICABLE'


def test_exact_case_query_domain_mapping_requires_exact_identity_and_subject_overlap():
    from services.regulatory_retrieval import _exact_case_query_domains
    domains=[{'id':'corruption','role':'PRIMARY'},{'id':'financial_services','role':'SECONDARY'}]
    assert _exact_case_query_domains('Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',domains)==['corruption']
    assert _exact_case_query_domains('Undang-Undang Nomor 31 Tahun 1999',domains)==[]
    assert _exact_case_query_domains('berita korupsi hari ini',domains)==[]


def test_ojk_slash_identity_is_recognized_without_relaxing_identity_gate():
    from services.positive_law_verification import regulation_identity
    assert regulation_identity('POJK Nomor 4/POJK.03/2015 tentang Tata Kelola BPR')['key']=='POJK:4:2015'
    assert regulation_identity('SEOJK No. 11/SEOJK.03/2023 BMPK BPR')['key']=='SEOJK:11:2023'


def test_explicit_effective_on_promulgation_uses_verified_promulgation_date():
    from services.positive_law_verification import extract_status_metadata
    text=('Undang-Undang Nomor 99 Tahun 2020. Undang-Undang ini mulai berlaku pada tanggal diundangkan. '
          'Diundangkan pada tanggal 17 Desember 2020. Status Peraturan: Berlaku.')
    out=extract_status_metadata(text)
    assert out['promulgation_date']=='2020-12-17'
    assert out['effective_date']=='2020-12-17'
    assert out['legal_status']=='IN_FORCE'


def test_exact_case_query_provenance_does_not_trust_generated_qualified_queries():
    from services.regulatory_retrieval import _case_exact_regulation_queries
    case=['Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi']
    generated=['Undang-Undang Nomor 1 Tahun 2023 tentang Kitab Undang-Undang Hukum Pidana']
    out=_case_exact_regulation_queries(case,generated)
    assert 'undang-undang nomor 31 tahun 1999 tentang pemberantasan tindak pidana korupsi' in out
    assert not any('nomor 1 tahun 2023' in x for x in out)


def test_revoked_instrument_can_still_be_in_force_before_repeal_year():
    text=(
        'Peraturan Pemerintah Nomor 10 Tahun 1961. '
        'Berlaku mulai 23 Maret 1961. '
        'Dicabut dengan Peraturan Pemerintah Nomor 24 Tahun 1997.'
    )
    row={'title':'PP Nomor 10 Tahun 1961','query':'PP Nomor 10 Tahun 1961',
         'authoritative':True,'case_nexus_status':'CASE_NEXUS_VERIFIED'}
    out=verify_document_candidate(row,source_text=text,snapshot={'event_date_candidate':'1995-01-01'})
    assert out['legal_status']=='REVOKED'
    assert out['tempus_status']=='TEMPUS_VERIFIED'
    assert out['status_at_tempus']=='IN_FORCE_BEFORE_REPEAL'
    assert out['final_status']=='VERIFIED_APPLICABLE'


def test_revoked_instrument_is_not_applicable_after_repeal_year():
    text=(
        'Peraturan Pemerintah Nomor 10 Tahun 1961. '
        'Berlaku mulai 23 Maret 1961. '
        'Dicabut dengan Peraturan Pemerintah Nomor 24 Tahun 1997.'
    )
    row={'title':'PP Nomor 10 Tahun 1961','query':'PP Nomor 10 Tahun 1961',
         'authoritative':True,'case_nexus_status':'CASE_NEXUS_VERIFIED'}
    out=verify_document_candidate(row,source_text=text,snapshot={'event_date_candidate':'2001-01-01'})
    assert out['tempus_status']=='REVOKED_AT_TEMPUS'
    assert out['final_status']=='VERIFIED_NOT_APPLICABLE'


def test_amending_law_title_does_not_mean_the_amending_law_is_itself_amended():
    text=(
        'Undang-Undang Nomor 3 Tahun 2006 tentang Perubahan Atas '
        'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama. '
        'Berlaku mulai 20 Maret 2006. Status Peraturan: Berlaku.'
    )
    meta=extract_status_metadata(text)
    assert meta['amends_other_instrument'] is True
    assert meta['amended'] is False
    assert meta['legal_status']=='IN_FORCE'


def test_historical_article_version_blocks_false_current_text_applicability():
    text=(
        'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama. '
        'Berlaku mulai 29 Desember 1989. Status Peraturan: Berlaku. '
        'Diubah dengan Undang-Undang Nomor 3 Tahun 2006. '
        'Pasal 49 Pengadilan Agama bertugas dan berwenang.'
    )
    row={'title':'UU Nomor 7 Tahun 1989 tentang Peradilan Agama',
         'query':'UU Nomor 7 Tahun 1989 tentang Peradilan Agama Pasal 49',
         'authoritative':True,'case_nexus_status':'CASE_NEXUS_VERIFIED',
         'requested_provisions':['Pasal 49']}
    out=verify_document_candidate(row,source_text=text,snapshot={'event_date_candidate':'2000-01-01'})
    assert out['provision_verification']['status']=='PROVISION_VERIFIED'
    assert out['provision_temporal_version']['status']=='HISTORICAL_PROVISION_VERSION_REQUIRED'
    assert out['final_status']=='HISTORICAL_PROVISION_VERSION_REQUIRED'


def test_multi_instrument_provision_binding_does_not_spray_orphan_pasals():
    from services.regulatory_retrieval import _attach_requested_provisions
    rows=[
        {'title':'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama',
         'query':'Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama'},
        {'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
         'query':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi'},
    ]
    qualified=[
        'Undang-Undang Nomor 7 Tahun 1989 Pasal 49',
        'Undang-Undang Nomor 31 Tahun 1999 Pasal 3',
    ]
    exact={r['query'].lower() for r in rows}
    out=_attach_requested_provisions(rows,['Pasal 49','Pasal 3'],[],qualified_queries=qualified,case_exact_queries=exact)
    assert out[0]['requested_provisions']==['Pasal 49']
    assert out[1]['requested_provisions']==['Pasal 3']


def test_exact_case_regulation_is_prioritized_in_retrieval_funnel(monkeypatch):
    import services.regulatory_retrieval as rr
    domains=[{'id':'corruption','role':'PRIMARY','source_ids':['bpk']}]
    query='Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi'
    monkeypatch.setattr(rr,'federated_search_many',lambda *a,**k:{query:[{
        'source_id':'bpk','source_name':'BPK','authoritative':True,'reachable':True,
        'results':[{'title':'Undang-Undang Nomor 31 Tahun 1999','url':'https://peraturan.bpk.go.id/x','score':1}]
    }]})
    out=rr._compact_searches([query],domains,2000,case_exact_queries={query.lower()})
    row=out['results'][0]
    assert row['query_origin']=='EXACT_CASE_REGULATION'
    assert row['relevance_score'] >= 0.38
    assert 'corruption' in row['case_nexus_domains']


def test_fulltext_resolver_detects_pdf_magic_when_server_uses_octet_stream(monkeypatch):
    import legal_sources as ls
    from io import BytesIO
    from reportlab.pdfgen import canvas
    buf=BytesIO(); c=canvas.Canvas(buf)
    c.drawString(72,760,'Undang-Undang Nomor 31 Tahun 1999')
    c.drawString(72,730,'Pasal 3 setiap orang ...')
    c.save(); pdf=buf.getvalue()
    out=ls.resolve_official_fulltext(
        'https://peraturan.bpk.go.id/download?id=123', pdf,
        'application/octet-stream', requested_provisions=['Pasal 3'])
    assert out['resolved'] is True
    assert out['resolver_status'] == 'DIRECT_PDF_TEXT'
    assert 'Pasal 3' in out['text']


def test_domain_rule_regulation_can_promote_nexus_after_official_identity_confirmation():
    from services.positive_law_verification import verify_document_candidate
    row={
        'title':'Peraturan Otoritas Jasa Keuangan Nomor 13/POJK.03/2015 tentang Penerapan Manajemen Risiko bagi BPR',
        'query':'POJK BPR manajemen risiko kredit',
        'authoritative':True,'query_origin':'DOMAIN_RULE_REGULATION',
        'case_nexus_domains':['financial_services'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'requested_provisions':['Pasal 2'], 'url':'https://ojk.go.id/pojk-13-2015.pdf',
    }
    text=('Peraturan Otoritas Jasa Keuangan Nomor 13/POJK.03/2015 tentang Penerapan Manajemen Risiko bagi BPR. '
          'Pasal 2 BPR wajib menerapkan Manajemen Risiko secara efektif.')
    out=verify_document_candidate(row,source_text=text,snapshot={})
    assert out['identity_confirmed'] is True
    assert out['case_nexus_status']=='CASE_NEXUS_VERIFIED'
    assert out['provision_verification']['verified']==['Pasal 2']
    assert out['final_status']!='VERIFIED_APPLICABLE'  # tempus/status remain fail-closed


def test_identity_normalization_accepts_official_pdf_heading_layout_and_dash_variants():
    text=(
        'UNDANG – UNDANG REPUBLIK INDONESIA\n'
        'NOMOR 31\nTAHUN 1999\n'
        'TENTANG PEMBERANTASAN TINDAK PIDANA KORUPSI\n'
        'Pasal 3 Setiap orang yang dengan tujuan tertentu ...'
    )
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query':'UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query_origin':'KNOWN_REGULATION',
        'case_nexus_domains':['corruption'],
        'authoritative':True,
        'requested_provisions':['Pasal 3'],
    }
    out=verify_document_candidate(row, source_text=text, snapshot={})
    assert out['identity_confirmed'] is True
    assert out['case_nexus_status']=='CASE_NEXUS_VERIFIED'
    assert out['provision_text_location']['located_count']==1
    assert out['provision_verification']['verified_count']==1


def test_text_location_is_recorded_even_when_instrument_gate_remains_closed():
    text=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 20 TAHUN 2001. '
        'Pasal 3 Ketentuan contoh untuk pengujian locator.'
    )
    row={
        'title':'UU Nomor 31 Tahun 1999',
        'query':'UU Nomor 31 Tahun 1999',
        'query_origin':'KNOWN_REGULATION',
        'case_nexus_domains':['corruption'],
        'authoritative':True,
        'requested_provisions':['Pasal 3'],
    }
    out=verify_document_candidate(row, source_text=text, snapshot={})
    assert out['identity_confirmed'] is False
    assert out['provision_text_location']['located_count']==1
    assert out['provision_text_location']['status']=='PROVISION_TEXT_LOCATED'
    assert out['provision_verification']['status']=='PROVISION_BLOCKED_BY_INSTRUMENT_GATE'
    assert out['provision_verification']['verified_count']==0


def test_case_bound_provision_can_close_nexus_after_official_identity_even_for_discovery_origin():
    text=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999 '
        'TENTANG PEMBERANTASAN TINDAK PIDANA KORUPSI. '
        'Pasal 3 Setiap orang yang dengan tujuan tertentu ...'
    )
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query':'pemberantasan tindak pidana korupsi penyalahgunaan kewenangan',
        'query_origin':'DISCOVERY',
        'case_nexus_domains':[],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'authoritative':True,
        'requested_provisions':['Pasal 3'],
        'provision_binding_provenance':{
            'case_bound':True, 'exact_case_text':['Pasal 3'],
            'qualified_case_citation':[], 'instrument_key':'UU:31:1999',
        },
    }
    # The official title supplies the expected instrument identity when the
    # discovery query itself is not regulation-qualified.
    out=verify_document_candidate(row, source_text=text, snapshot={})
    assert out['identity_confirmed'] is True
    assert out['case_nexus_status']=='CASE_NEXUS_VERIFIED'
    assert out['provision_verification']['verified']==['Pasal 3']


def test_unbound_discovery_hit_stays_fail_closed_even_when_article_number_matches():
    text=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999. '
        'Pasal 3 Ketentuan contoh.'
    )
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999',
        'query':'korupsi kerugian negara',
        'query_origin':'DISCOVERY',
        'case_nexus_domains':[],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'authoritative':True,
        'requested_provisions':['Pasal 3'],
        'provision_binding_provenance':{'case_bound':False},
    }
    out=verify_document_candidate(row, source_text=text, snapshot={})
    assert out['identity_confirmed'] is True
    assert out['case_nexus_status']=='CASE_NEXUS_UNCERTAIN'
    assert out['provision_verification']['status']=='PROVISION_BLOCKED_BY_INSTRUMENT_GATE'

def test_case_bound_identity_precedes_generic_discovery_title_during_verification():
    from services.positive_law_verification import verify_document_candidate
    row={
        'title':'Undang-Undang Nomor 20 Tahun 2001 tentang Perubahan UU Tipikor',
        'query':'korupsi penyalahgunaan kewenangan',
        'query_origin':'DISCOVERY',
        'case_nexus_domains':[],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'authoritative':True,
        'requested_provisions':['Pasal 3'],
        'provision_binding_provenance':{
            'case_bound':True,'exact_case_text':['Pasal 3'],
            'qualified_case_citation':[],'instrument_key':'UU:31:1999',
        },
    }
    text=('UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999 '
          'TENTANG PEMBERANTASAN TINDAK PIDANA KORUPSI. Pasal 3 Ketentuan contoh.')
    out=verify_document_candidate(row,source_text=text,snapshot={})
    assert out['identity_confirmed'] is True
    assert out['identity']['expected_key']=='UU:31:1999'
    assert out['identity']['expected_identity_source']=='CASE_BOUND_INSTRUMENT_KEY'
    assert out['case_nexus_status']=='CASE_NEXUS_VERIFIED'
    assert out['provision_verification']['verified_count']==1


def test_fulltext_resolver_prefers_identity_aligned_attachment_over_more_article_hits(monkeypatch):
    import legal_sources as ls
    html=(b'<html><body>'
          b'<a href="/wrong.pdf">download lampiran A</a>'
          b'<a href="/right.pdf">download lampiran B</a>'
          b'</body></html>')
    wrong=b'%PDF-fake'
    right=b'%PDF-fake2'
    def fake_fetch(url,timeout=5):
        return {'reachable':True,'official_host':True,'final_url':url,'content_type':'application/pdf','body': wrong if 'wrong' in url else right}
    def fake_extract(body):
        if body==wrong:
            return ('UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 20 TAHUN 2001. '
                    'Pasal 3 x. Pasal 18 y. Pasal 9 z.')
        return ('UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999. '
                'Pasal 3 ketentuan yang diminta.')
    monkeypatch.setattr(ls,'fetch_official_document',fake_fetch)
    monkeypatch.setattr(ls,'_extract_pdf_text',fake_extract)
    out=ls.resolve_official_fulltext(
        'https://jdih.example.go.id/detail/tipikor',html,'text/html',
        requested_provisions=['Pasal 3','Pasal 18','Pasal 9'],max_candidates=3,
        expected_identity_key='UU:31:1999')
    assert out['resolved'] is True
    assert out['source_url'].endswith('/right.pdf')
    assert out['resolved_identity_key']=='UU:31:1999'
    assert out['identity_aligned'] is True

def test_resolved_exact_identity_rebinds_lawyer_facing_metadata(monkeypatch):
    import services.regulatory_retrieval as rr

    wrong_title='Perubahan atas Peraturan Komisi Pemberantasan Korupsi Nomor 01 Tahun 2014'
    row={
        'title':wrong_title,
        'url':'https://peraturan.bpk.go.id/Details/wrong-search-hit',
        'source_id':'bpk','source_name':'BPK','authoritative':True,
        'query':'Undang-Undang Nomor 20 Tahun 2001',
        'query_origin':'KNOWN_REGULATION','case_nexus_domains':['corruption'],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN','relevance_score':0.9,
        'requested_provisions':['Pasal 3'],
        'provision_binding_provenance':{
            'case_bound':True,'exact_case_text':['Pasal 3'],
            'qualified_case_citation':[],'instrument_key':'UU:20:2001',
        },
    }
    row['document_classification']=rr.classify_legal_document_candidate(row)

    monkeypatch.setattr(rr,'fetch_official_document',lambda url,timeout=5:{
        'reachable':True,'official_host':True,'final_url':url,
        'content_type':'text/html','body':b'<html>detail</html>'})
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':True,'source_url':'https://peraturan.bpk.go.id/Download/33263/UU%20Nomor%2020%20Tahun%202001.pdf',
        'content_type':'application/pdf',
        'text':'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 20 TAHUN 2001. Pasal 3 ketentuan contoh.',
        'resolver_status':'ATTACHMENT_PDF_TEXT','resolved_identity_key':'UU:20:2001',
        'identity_candidates':['UU:20:2001'],'identity_aligned':True,
    })

    out=rr._verify_positive_law_results([row],snapshot={},max_documents=10)[0]
    assert out['positive_law_verification']['identity_confirmed'] is True
    assert out['canonical_instrument_key']=='UU:20:2001'
    assert out['canonical_title']=='Undang-Undang Nomor 20 Tahun 2001'
    assert out['title']=='Undang-Undang Nomor 20 Tahun 2001'
    assert out['discovery_title']==wrong_title
    assert out['url'].endswith('UU%20Nomor%2020%20Tahun%202001.pdf')

def test_fulltext_resolver_does_not_treat_referenced_base_law_as_primary_identity(monkeypatch):
    import legal_sources as ls
    pdf=b'%PDF-fake-amendment'
    amendment_text=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 20 TAHUN 2001 '
        'TENTANG PERUBAHAN ATAS UNDANG-UNDANG NOMOR 31 TAHUN 1999 '
        'TENTANG PEMBERANTASAN TINDAK PIDANA KORUPSI. Pasal 3 ketentuan contoh.'
    )
    monkeypatch.setattr(ls,'_extract_pdf_text',lambda body: amendment_text)
    out=ls.resolve_official_fulltext(
        'https://peraturan.bpk.go.id/Download/33263/UU%20Nomor%2020%20Tahun%202001.pdf',
        pdf,'application/pdf',requested_provisions=['Pasal 3'],
        expected_identity_key='UU:31:1999')
    assert out['resolved'] is False
    assert out['identity_aligned'] is False
    assert out['resolved_identity_key']=='UU:20:2001'
    assert out['identity_candidates'][:2]==['UU:20:2001','UU:31:1999']
    assert out['resolver_status']=='EXPECTED_IDENTITY_NOT_FOUND'
