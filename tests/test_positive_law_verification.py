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
    assert out['final_status']=='VERIFICATION_REQUIRED'


def test_r25_status_semantics_explicit_in_force_amended_beats_unscoped_repeal_reference():
    text=(
        'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi. '
        'Status Peraturan: Berlaku. Diubah dengan Undang-Undang Nomor 20 Tahun 2001. '
        'Catatan hubungan lain: dicabut dengan peraturan lain pada bagian yang tidak menjadi status instrumen ini.'
    )
    meta=extract_status_metadata(text)
    assert meta['amended'] is True
    assert meta['legal_status']=='AMENDED_IN_FORCE'
    assert meta['revoked'] is False


def test_r25_tempus_unknown_cannot_be_promoted_to_not_applicable():
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'authoritative':True,'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['corruption'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
    }
    text=(
        'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi. '
        'Berlaku mulai 16 Agustus 1999. Status Peraturan: Berlaku. '
        'Diubah dengan Undang-Undang Nomor 20 Tahun 2001. Pasal 3.'
    )
    out=verify_document_candidate(row,source_text=text,snapshot={})
    assert out['identity_confirmed'] is True
    assert out['tempus_anchor'] is None
    assert out['tempus_status']=='TEMPUS_UNVERIFIED'
    assert out['tempus_applicable'] is None
    assert out['final_status']=='VERIFICATION_REQUIRED'


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

# RC18 R16 — surgical identity-parser hardening ported without replacing the
# established fail-closed verification pipeline.
def test_r16_reg_identity_handles_type_bound_slash_shorthand():
    from services.positive_law_verification import _reg_identity
    assert _reg_identity('UU 8/1999 tentang Perlindungan Konsumen')['key']=='UU:8:1999'


def test_r16_reg_identity_handles_reversed_tahun_nomor_layout():
    from services.positive_law_verification import _reg_identity
    assert _reg_identity('Peraturan Pemerintah Tahun : 1997 Nomor : 24 tentang Pendaftaran Tanah')['key']=='PP:24:1997'


def test_r16_reg_identity_does_not_treat_date_as_slash_identity():
    from services.positive_law_verification import _reg_identity
    assert _reg_identity('UU tentang Contoh, ditetapkan pada 20/03/2006 di Jakarta')['key'] is None


def test_r16_reg_identity_tolerates_zero_width_and_soft_hyphen_noise():
    from services.positive_law_verification import _reg_identity
    noisy='Un\u00addang\u200b-Undang Nomor\u00a0 7 Tahun 1989 tentang Peradilan Agama'
    assert _reg_identity(noisy)['key']=='UU:7:1989'


def test_r16_identity_matching_canonicalizes_leading_zero_only():
    from services.positive_law_verification import _identity_matches
    row={'title':'PP No. 08 Tahun 1999','query':'PP No. 08 Tahun 1999'}
    match,_=_identity_matches(row,'Peraturan Pemerintah Nomor 8 Tahun 1999 tentang Contoh')
    assert match is True

# RC18 R19 — exact official identity recovery without weakening fulltext gates.
def test_r19_exact_query_variants_are_identity_bound():
    from services.official_identity_resolver import exact_query_variants
    assert exact_query_variants('UU:31:1999') == [
        'Undang-Undang Nomor 31 Tahun 1999', 'UU 31/1999', 'UU:31:1999']


def test_r19_ranker_rejects_explicit_wrong_title_identity():
    from services.official_identity_resolver import rank_candidates
    rows=[
        ('bpk', {'title':'UU No. 5 Tahun 2017 tentang Pemajuan Kebudayaan','snippet':'mengubah referensi UU 31/1999','url':'https://x/wrong'}),
        ('bpk', {'title':'UU No. 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi','url':'https://x/right'}),
    ]
    ranked=rank_candidates('UU:31:1999',rows)
    assert [r.row['url'] for r in ranked] == ['https://x/right']
    assert ranked[0].reason == 'EXACT_TITLE_IDENTITY'


def test_r19_local_corpus_seeds_exact_tipikor_official_url():
    import services.regulatory_retrieval as rr
    seeds=rr._canonical_official_seed_candidates('UU:31:1999')
    assert seeds
    source,row=seeds[0]
    assert source=='local_corpus'
    assert '31 Tahun 1999' in row['title']
    assert row['url'].startswith('https://')


def test_r19_recovery_tries_exact_corpus_seed_before_wrong_search_hits(monkeypatch):
    import services.regulatory_retrieval as rr
    exact_url='https://peraturan.bpk.go.id/Details/45350/uu-no-31-tahun-1999'
    wrong_url='https://peraturan.bpk.go.id/Details/wrong-5-2017'
    monkeypatch.setattr(rr,'_canonical_official_seed_candidates',lambda expected:[('local_corpus',{
        'title':'UU No. 31 Tahun 1999','url':exact_url,'relevance_score':99.0})])
    monkeypatch.setattr(rr,'federated_search_many',lambda queries,**kwargs:{q:[{'source_id':'bpk','results':[{
        'title':'UU No. 5 Tahun 2017','url':wrong_url,'snippet':'UU 31/1999'}]}] for q in queries})
    fetched=[]
    def fake_fetch(url,timeout=4):
        fetched.append(url)
        return {'reachable':True,'official_host':True,'final_url':url,'body':b'<html>x</html>','content_type':'text/html'}
    monkeypatch.setattr(rr,'fetch_official_document',fake_fetch)
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':True,'identity_aligned':True,'resolved_identity_key':'UU:31:1999',
        'source_url':exact_url,'text':'UNDANG-UNDANG NOMOR 31 TAHUN 1999 Pasal 3',
        'resolver_status':'DETAIL_HTML_TEXT'})
    out=rr._recover_expected_official_fulltext('UU:31:1999',['Pasal 3'],time_budget_seconds=4.0)
    assert out['resolved'] is True
    assert out['identity_aligned'] is True
    assert fetched[0] == exact_url
    assert wrong_url not in fetched
    assert out['recovery_rank_reason']=='EXACT_TITLE_IDENTITY'

# RC18 R20 — exact-candidate lock: legacy mismatches cannot run ahead of, or
# replace, an exact metadata candidate in the same recovery pass.
def test_r20_exact_candidate_lock_blocks_legacy_fallback_after_exact_failure(monkeypatch):
    import services.regulatory_retrieval as rr
    exact_url='https://peraturan.bpk.go.id/Details/45350/uu-no-31-tahun-1999'
    ambiguous_url='https://peraturan.bpk.go.id/Details/ambiguous'
    monkeypatch.setattr(rr,'_canonical_official_seed_candidates',lambda expected:[('local_corpus',{
        'title':'UU No. 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'url':exact_url,'relevance_score':99.0})])
    monkeypatch.setattr(rr,'federated_search_many',lambda queries,**kwargs:{q:[{'source_id':'bpk','results':[
        {'title':'Dokumen pemberantasan korupsi','url':ambiguous_url,'snippet':'UU 31/1999','relevance_score':99.0}
    ]}] for q in queries})
    fetched=[]
    def fake_fetch(url,timeout=4):
        fetched.append(url)
        if url == exact_url:
            return {'reachable':True,'official_host':True,'final_url':url,
                    'body':b'%PDF-fake','content_type':'application/pdf'}
        raise AssertionError('legacy/ambiguous candidate must not be fetched while exact lock is active')
    monkeypatch.setattr(rr,'fetch_official_document',fake_fetch)
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':False,'identity_aligned':False,'resolved_identity_key':'UU:20:2001',
        'source_url':exact_url,'text':'','resolver_status':'EXPECTED_IDENTITY_NOT_FOUND'})
    out=rr._recover_expected_official_fulltext('UU:31:1999',['Pasal 3'],time_budget_seconds=4.0)
    assert out['resolved'] is False
    assert out['resolver_status']=='EXPECTED_IDENTITY_EXACT_CANDIDATE_FAILED'
    assert out['recovery_exact_lock'] is True
    assert out['recovery_exact_candidate_count'] >= 1
    assert fetched == [exact_url]
    assert all(x.get('reason') == 'EXACT_TITLE_IDENTITY' for x in out['recovery_candidate_trace'])


def test_r20_recovery_trace_keeps_exact_candidate_first(monkeypatch):
    import services.regulatory_retrieval as rr
    exact_url='https://x/exact'
    monkeypatch.setattr(rr,'_canonical_official_seed_candidates',lambda expected:[('local_corpus',{
        'title':'UU No. 31 Tahun 1999','url':exact_url,'relevance_score':99.0})])
    monkeypatch.setattr(rr,'federated_search_many',lambda queries,**kwargs:{q:[] for q in queries})
    monkeypatch.setattr(rr,'fetch_official_document',lambda url,timeout=4:{
        'reachable':True,'official_host':True,'final_url':url,'body':b'%PDF-fake','content_type':'application/pdf'})
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':True,'identity_aligned':True,'resolved_identity_key':'UU:31:1999',
        'source_url':exact_url,'text':'UNDANG-UNDANG NOMOR 31 TAHUN 1999 Pasal 3',
        'resolver_status':'DIRECT_PDF_TEXT'})
    out=rr._recover_expected_official_fulltext('UU:31:1999',['Pasal 3'],time_budget_seconds=4.0)
    assert out['resolved'] is True
    assert out['recovery_exact_lock'] is True
    assert out['recovery_candidate_trace'][0]['title_identity']=='UU:31:1999'
    assert out['recovery_attempted_urls'][0] == exact_url


# RC18 R21 — exact-lock recovery failure must replace stale legacy mismatch.
def test_r21_recovery_propagation_invariant_success_replaces_legacy():
    import services.regulatory_retrieval as rr
    recovered={'resolved':True,'recovery_exact_lock':True,'resolver_status':'RECOVERED_EXACT_IDENTITY'}
    legacy={'resolved':True,'identity_aligned':False,'resolved_identity_key':'UU:5:2017'}
    assert rr._recovery_result_should_replace_legacy(recovered, legacy) is True


def test_r21_recovery_propagation_invariant_exact_failure_replaces_explicit_mismatch():
    import services.regulatory_retrieval as rr
    recovered={
        'resolved':False,
        'resolver_status':'EXPECTED_IDENTITY_EXACT_CANDIDATE_FAILED',
        'recovery_exact_lock':True,
    }
    legacy={'resolved':True,'identity_aligned':False,'resolved_identity_key':'UU:5:2017'}
    assert rr._recovery_result_should_replace_legacy(recovered, legacy) is True


def test_r21_recovery_propagation_invariant_no_exact_lock_keeps_legacy():
    import services.regulatory_retrieval as rr
    recovered={
        'resolved':False,
        'resolver_status':'EXPECTED_IDENTITY_RECOVERY_FAILED',
        'recovery_exact_lock':False,
    }
    legacy={'resolved':True,'identity_aligned':False,'resolved_identity_key':'UU:5:2017'}
    assert rr._recovery_result_should_replace_legacy(recovered, legacy) is False


def test_r21_legacy_result_without_identity_aligned_remains_backward_compatible():
    import services.regulatory_retrieval as rr
    recovered={'resolved':False,'recovery_exact_lock':True}
    legacy={'resolved':True,'source_url':'https://example.test/official.pdf'}
    assert rr._recovery_result_should_replace_legacy(recovered, legacy) is False

# RC18 R23 — exact-case verification must not be starved by general discovery.
def test_r23_scheduler_allows_exact_case_recovery_inside_reserved_slice():
    import services.regulatory_retrieval as rr
    remaining=[0.80]  # below legacy 1.25-second gate
    scheduler=rr._VerificationScheduler(lambda: remaining[0], {'UU:31:1999'}, reserve_seconds=4.0)
    row={
        'query_origin':'EXACT_CASE_REGULATION',
        'query':'Undang-Undang Nomor 31 Tahun 1999',
        'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:31:1999'},
    }
    assert scheduler.can_run_recovery(row) is True
    assert scheduler.can_run_fulltext(row) is True
    assert 0.35 <= scheduler.recovery_budget(row) <= 0.80


def test_r23_scheduler_blocks_non_exact_when_only_reserved_slice_remains():
    import services.regulatory_retrieval as rr
    remaining=[4.50]
    scheduler=rr._VerificationScheduler(lambda: remaining[0], {'UU:31:1999'}, reserve_seconds=4.0)
    row={
        'query_origin':'DISCOVERY',
        'query':'Undang-Undang Nomor 5 Tahun 2017',
    }
    # 4.5 seconds remains, but 4.0 seconds is still reserved for the pending
    # exact-case identity plus the normal 1.25s safety gate.
    assert scheduler.can_run_recovery(row) is False
    assert scheduler.can_run_fulltext(row) is False


def test_r23_scheduler_releases_reserve_after_exact_case_processed():
    import services.regulatory_retrieval as rr
    remaining=[4.50]
    scheduler=rr._VerificationScheduler(lambda: remaining[0], {'UU:31:1999'}, reserve_seconds=4.0)
    exact={
        'query_origin':'EXACT_CASE_REGULATION',
        'query':'Undang-Undang Nomor 31 Tahun 1999',
        'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:31:1999'},
    }
    general={'query_origin':'DISCOVERY','query':'Undang-Undang Nomor 5 Tahun 2017'}
    scheduler.mark_exact_processed(exact)
    assert scheduler.can_run_recovery(general) is True

# RC18 R24 — structured official URL identity must override an amendment title
# that names the base/amended instrument.
def test_r24_bpk_amendment_title_uses_url_primary_identity():
    from services.official_identity_resolver import rank_candidates
    rows=[
        ('bpk', {
            'title':'Perubahan Atas Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
            'url':'https://peraturan.bpk.go.id/Details/44900/uu-no-20-tahun-2001',
        }),
        ('local_corpus', {
            'title':'UU No. 31 Tahun 1999 jo UU No. 20 Tahun 2001',
            'url':'https://peraturan.bpk.go.id/Details/45350/uu-no-31-tahun-1999',
            'relevance_score':99.0,
        }),
    ]
    ranked=rank_candidates('UU:31:1999',rows)
    assert len(ranked) == 1
    assert ranked[0].title_identity == 'UU:31:1999'
    assert ranked[0].row['url'].endswith('/uu-no-31-tahun-1999')
    assert ranked[0].reason == 'EXACT_TITLE_IDENTITY'


def test_r24_bpk_amending_law_is_exact_for_its_own_url_identity():
    from services.official_identity_resolver import rank_candidates
    rows=[('bpk', {
        'title':'Perubahan Atas Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'url':'https://peraturan.bpk.go.id/Details/44900/uu-no-20-tahun-2001',
    })]
    ranked=rank_candidates('UU:20:2001',rows)
    assert len(ranked) == 1
    assert ranked[0].title_identity == 'UU:20:2001'
    assert ranked[0].reason == 'EXACT_TITLE_IDENTITY'


def test_r24_non_structured_url_keeps_existing_title_identity_behavior():
    from services.official_identity_resolver import rank_candidates
    rows=[('bpk', {
        'title':'UU No. 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'url':'https://example.go.id/detail?id=45350',
    })]
    ranked=rank_candidates('UU:31:1999',rows)
    assert len(ranked) == 1
    assert ranked[0].title_identity == 'UU:31:1999'


# R26 — provision completion for UU 31/1999 without changing frozen identity/tempus/budget layers.
def test_r26_statute_pdf_outranks_uji_materi_for_requested_provisions(monkeypatch):
    import legal_sources as ls
    html=(
        b'<html><body>'
        b'<a href="/DownloadUjiMateri/229/putusan_mkri_123PUU-XXIII2025.pdf">Uji Materi 1</a>'
        b'<a href="/DownloadUjiMateri/235/putusan_mkri_71-PUU-XXIII-2025_compressed.pdf">Uji Materi 2</a>'
        b'<a href="/Download/99999/UU%20Nomor%2031%20Tahun%201999.pdf">UU Nomor 31 Tahun 1999</a>'
        b'</body></html>'
    )
    def fake_fetch(url, timeout=5):
        return {
            'reachable': True, 'official_host': True, 'final_url': url,
            'content_type': 'application/pdf', 'body': url.encode('utf-8')
        }
    def fake_extract(body):
        url=body.decode('utf-8')
        if '/Download/99999/' in url:
            return (
                'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999. '
                'Pasal 2 ayat (1) ketentuan. Pasal 3 ketentuan. '
                'Pasal 9 ketentuan. Pasal 18 ketentuan.'
            )
        return 'PUTUSAN MAHKAMAH KONSTITUSI. Pasal 3. Pasal 18.'
    monkeypatch.setattr(ls, 'fetch_official_document', fake_fetch)
    monkeypatch.setattr(ls, '_extract_pdf_text', fake_extract)
    out=ls.resolve_official_fulltext(
        'https://peraturan.bpk.go.id/Details/45350/uu-no-31-tahun-1999',
        html, 'text/html',
        requested_provisions=['Pasal 2 ayat (1)','Pasal 3','Pasal 9','Pasal 18'],
        max_candidates=2, expected_identity_key='UU:31:1999'
    )
    assert out['resolved'] is True
    assert out['identity_aligned'] is True
    assert '/Download/99999/' in out['source_url']
    from services.positive_law_verification import verify_provisions
    verified=verify_provisions(
        ['Pasal 2 ayat (1)','Pasal 3','Pasal 9','Pasal 18'],
        out['text'], out['source_url']
    )
    assert verified['verified_count'] == 4
    assert verified['verified'] == ['Pasal 2 ayat (1)','Pasal 3','Pasal 9','Pasal 18']


def test_r26_uji_materi_links_are_not_preferred_over_statute_pdf():
    import legal_sources as ls
    statute=ls._fulltext_link_score(
        'https://peraturan.bpk.go.id/Download/99999/UU%20Nomor%2031%20Tahun%201999.pdf',
        'UU Nomor 31 Tahun 1999', ['Pasal 9','Pasal 18']
    )
    uji=ls._fulltext_link_score(
        'https://peraturan.bpk.go.id/DownloadUjiMateri/229/putusan_mkri_123PUU-XXIII2025.pdf',
        'Uji Materi', ['Pasal 9','Pasal 18']
    )
    assert statute > uji


def test_r28_post_verification_status_preserves_amended_without_touching_identity_or_provisions():
    from services.positive_law_verification import verify_document_candidate, apply_post_verification_status_semantics
    row={
        'title':'Undang-Undang Nomor 31 Tahun 1999',
        'query':'Undang-Undang Nomor 31 Tahun 1999',
        'authoritative':True,'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['corruption'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'requested_provisions':['Pasal 2 ayat (1)','Pasal 3','Pasal 9','Pasal 18'],
        'provision_binding_provenance':{'case_bound':True},
        'url':'https://peraturan.bpk.go.id/Download/33850/UU%20Nomor%2031%20Tahun%201999.pdf',
    }
    text=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999. '
        'Pasal 2 ayat (1). Pasal 3. Pasal 9. Pasal 18. '
        'Catatan hubungan: sebagian ketentuan dicabut dengan peraturan lain.'
    )
    base=verify_document_candidate(row,source_text=text,snapshot={})
    assert base['identity_confirmed'] is True
    assert base['provision_verification']['verified_count']==4
    out=apply_post_verification_status_semantics(base,row)
    assert out['identity_confirmed'] is True
    assert out['provision_verification']['verified_count']==4
    assert out['legal_status']=='AMENDED_IN_FORCE'
    assert out['revoked'] is False
    assert out['tempus_status']=='TEMPUS_UNVERIFIED'
    assert out['tempus_applicable'] is None
    assert out['final_status']=='VERIFICATION_REQUIRED'
    assert out['status_semantics_source']=='LOCAL_CORPUS_METADATA_POST_VERIFICATION'


def test_r28_status_semantics_does_not_promote_unverified_identity():
    from services.positive_law_verification import apply_post_verification_status_semantics
    original={
        'identity_confirmed':False,
        'legal_status':'REVOKED',
        'tempus_status':'TEMPUS_UNVERIFIED',
        'final_status':'UNVERIFIED',
    }
    out=apply_post_verification_status_semantics(original, {'title':'Undang-Undang Nomor 31 Tahun 1999'})
    assert out == original

# R36 — provision locator completeness for large/split official statute PDFs.
def test_r36_provision_locator_tolerates_pdf_whitespace_for_pasal_3():
    from services.positive_law_verification import locate_provisions, verify_provisions
    text=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 7 TAHUN 2017. '
        'BAB II ASAS, PRINSIP, DAN TUJUAN. Pasal\n\u00a0 3\n'
        'Dalam menyelenggarakan Pemilu, Penyelenggara Pemilu harus memenuhi prinsip.'
    )
    located=locate_provisions(['Pasal 3'], text, 'https://peraturan.bpk.go.id/Download/26738/x.pdf')
    verified=verify_provisions(['Pasal 3'], text, 'https://peraturan.bpk.go.id/Download/26738/x.pdf')
    assert located['located_count'] == 1
    assert located['located'] == ['Pasal 3']
    assert verified['verified_count'] == 1
    assert verified['verified'] == ['Pasal 3']


def test_r36_official_pdf_request_uses_pdf_cap_without_changing_timeout(monkeypatch):
    import legal_sources as ls

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    class FakeResponse:
        status=200
        headers=Headers({'Content-Type':'application/pdf'})
        def __init__(self):
            self.read_size=None
        def geturl(self):
            return 'https://peraturan.bpk.go.id/Download/26738/UU_Nomor_7_Tahun_2017_-_Batang_Tubuh_-_Hal._1-150.pdf'
        def read(self, size=-1):
            self.read_size=size
            return b'%PDF-1.7\n%%EOF'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    fake=FakeResponse()
    seen={}
    def fake_urlopen(req, timeout=None, context=None):
        seen['timeout']=timeout
        return fake
    monkeypatch.setattr(ls, 'urlopen', fake_urlopen)
    monkeypatch.setattr(ls.ssl, 'create_default_context', lambda *a, **k: object())
    status, final_url, ctype, body=ls._request(
        'https://peraturan.bpk.go.id/Download/26738/UU_Nomor_7_Tahun_2017_-_Batang_Tubuh_-_Hal._1-150.pdf',
        timeout=5,
    )
    assert status == 200
    assert fake.read_size == ls.MAX_PDF_BODY
    assert fake.read_size > ls.MAX_BODY
    assert seen['timeout'] == 5
    assert body.startswith(b'%PDF-')


def test_r36_html_request_keeps_original_generic_cap(monkeypatch):
    import legal_sources as ls

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    class FakeResponse:
        status=200
        headers=Headers({'Content-Type':'text/html; charset=utf-8'})
        def __init__(self): self.read_size=None
        def geturl(self): return 'https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017'
        def read(self, size=-1): self.read_size=size; return b'<html></html>'
        def __enter__(self): return self
        def __exit__(self, *args): return False

    fake=FakeResponse()
    monkeypatch.setattr(ls, 'urlopen', lambda *a, **k: fake)
    monkeypatch.setattr(ls.ssl, 'create_default_context', lambda *a, **k: object())
    ls._request('https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017', timeout=5)
    assert fake.read_size == ls.MAX_BODY

# R37 — split-statute attachment ranking: statute body must outrank annex PDFs
# without increasing max_candidates.
def test_r37_batang_tubuh_outranks_lampiran_for_provision_verification():
    import legal_sources as ls
    body=ls._fulltext_link_score(
        'https://peraturan.bpk.go.id/Download/26738/UU_Nomor_7_Tahun_2017_-_Batang_Tubuh_-_Hal._1-150.pdf',
        'Download', ['Pasal 3']
    )
    annex=ls._fulltext_link_score(
        'https://peraturan.bpk.go.id/Download/26741/UU_Nomor_7_Tahun_2017_-_Lampiran_I.pdf',
        'Download', ['Pasal 3']
    )
    assert body > annex


def test_r37_resolver_reaches_split_statute_body_with_max_candidates_2(monkeypatch):
    import legal_sources as ls
    html=b'''<html><body>
      <a href="/Download/26741/UU_Nomor_7_Tahun_2017_-_Lampiran_I.pdf">Download</a>
      <a href="/Download/26742/UU_Nomor_7_Tahun_2017_-_Lampiran_II.pdf">Download</a>
      <a href="/Download/26743/UU_Nomor_7_Tahun_2017_-_Lampiran_III.pdf">Download</a>
      <a href="/Download/26744/UU_Nomor_7_Tahun_2017_-_Lampiran_IV.pdf">Download</a>
      <a href="/Download/26738/UU_Nomor_7_Tahun_2017_-_Batang_Tubuh_-_Hal._1-150.pdf">Download</a>
      <a href="/Download/26739/UU_Nomor_7_Tahun_2017_-_Batang_Tubuh_-_Hal._151-317.pdf">Download</a>
    </body></html>'''
    fetched=[]
    def fake_fetch(url, timeout=None):
        fetched.append(url)
        return {
            'reachable': True, 'official_host': True, 'final_url': url,
            'content_type': 'application/octet-stream', 'body': url.encode('utf-8')
        }
    def fake_extract(body):
        url=body.decode('utf-8')
        if 'Hal._1-150' in url:
            return 'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 7 TAHUN 2017. BAB II. Pasal 3 ketentuan.'
        if 'Hal._151-317' in url:
            return 'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 8 TAHUN 1981. Pasal 3 ketentuan lain.'
        return 'LAMPIRAN PEMILU.'
    monkeypatch.setattr(ls, 'fetch_official_document', fake_fetch)
    monkeypatch.setattr(ls, '_extract_pdf_text', fake_extract)
    out=ls.resolve_official_fulltext(
        'https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017',
        html, 'text/html', requested_provisions=['Pasal 3'],
        max_candidates=2, expected_identity_key='UU:7:2017'
    )
    assert out['resolved'] is True
    assert out['identity_aligned'] is True
    assert 'Hal._1-150' in out['source_url']
    assert any('Hal._1-150' in u for u in fetched)
    assert not any('Lampiran_I' in u for u in fetched)
    from services.positive_law_verification import verify_provisions
    verified=verify_provisions(['Pasal 3'], out['text'], out['source_url'])
    assert verified['verified_count'] == 1
    assert verified['verified'] == ['Pasal 3']

# R38 — legal-role-aware attachment resolution for enactment laws.
def test_r38_incorporation_parser_requires_confirmed_parent_and_explicit_enactment_formula():
    import legal_sources as ls
    detail=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015 '
        'TENTANG PENETAPAN PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG '
        'NOMOR 1 TAHUN 2014 TENTANG PEMILIHAN GUBERNUR, BUPATI, DAN WALIKOTA '
        'MENJADI UNDANG-UNDANG.'
    )
    assert ls._incorporated_instrument_keys_from_detail_text(detail,'UU:1:2015') == ['PERPU:1:2014']
    assert ls._incorporated_instrument_keys_from_detail_text(detail,'UU:10:2015') == []
    generic=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015. '
        'Referensi Peraturan Pemerintah Pengganti Undang-Undang Nomor 1 Tahun 2014.'
    )
    assert ls._incorporated_instrument_keys_from_detail_text(generic,'UU:1:2015') == []


def test_r38_enactment_law_reserves_annex_slot_and_accepts_only_verified_incorporated_identity(monkeypatch):
    import legal_sources as ls
    html=b'''<html><body>
      UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015 TENTANG
      PENETAPAN PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 1 TAHUN 2014
      TENTANG PEMILIHAN GUBERNUR, BUPATI, DAN WALIKOTA MENJADI UNDANG-UNDANG.
      <a href="/Download/parent-body.pdf">Batang Tubuh</a>
      <a href="/Download/operative-lampiran.pdf">Lampiran</a>
      <a href="/Download/other-lampiran.pdf">Lampiran lain</a>
    </body></html>'''
    fetched=[]
    def fake_fetch(url,timeout=5):
        fetched.append(url)
        return {'reachable':True,'official_host':True,'final_url':url,
                'content_type':'application/pdf','body':url.encode()}
    def fake_extract(body):
        url=body.decode()
        if 'parent-body' in url:
            return 'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015. Pasal 1 penetapan.'
        if 'operative-lampiran' in url:
            return ('PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG REPUBLIK INDONESIA '
                    'NOMOR 1 TAHUN 2014. Pasal 2 asas pemilihan.')
        return 'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 99 TAHUN 2015. Pasal 2 salah.'
    monkeypatch.setattr(ls,'fetch_official_document',fake_fetch)
    monkeypatch.setattr(ls,'_extract_pdf_text',fake_extract)
    out=ls.resolve_official_fulltext(
        'https://peraturan.bpk.go.id/Details/example/uu-no-1-tahun-2015',html,'text/html',
        requested_provisions=['Pasal 2'],max_candidates=2,expected_identity_key='UU:1:2015')
    assert out['resolved'] is True
    assert out['identity_aligned'] is True
    assert out['resolved_identity_key']=='UU:1:2015'
    assert out['text_identity_key']=='PERPU:1:2014'
    assert out['legal_role']=='INCORPORATED_INSTRUMENT'
    assert out['relationship_verified'] is True
    assert out['incorporated_identity_key']=='PERPU:1:2014'
    assert any('parent-body' in u for u in fetched)
    assert any('operative-lampiran' in u for u in fetched)
    assert not any('other-lampiran' in u for u in fetched)
    verified=ls.re.search(r'\bPasal\s+2\b',out['text'],ls.re.I)
    assert verified is not None


def test_r38_direct_parent_body_wins_when_both_parent_and_incorporated_text_contain_requested_article(monkeypatch):
    import legal_sources as ls
    html=b'''<html><body>
      UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015 TENTANG
      PENETAPAN PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 1 TAHUN 2014
      TENTANG PEMILIHAN GUBERNUR, BUPATI, DAN WALIKOTA MENJADI UNDANG-UNDANG.
      <a href="/Download/parent-body.pdf">Batang Tubuh</a>
      <a href="/Download/operative-lampiran.pdf">Lampiran</a>
    </body></html>'''
    monkeypatch.setattr(ls,'fetch_official_document',lambda url,timeout=5:{
        'reachable':True,'official_host':True,'final_url':url,'content_type':'application/pdf','body':url.encode()})
    monkeypatch.setattr(ls,'_extract_pdf_text',lambda body:(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015. Pasal 2 mulai berlaku.'
        if 'parent-body' in body.decode() else
        'PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 1 TAHUN 2014. Pasal 2 asas.'
    ))
    out=ls.resolve_official_fulltext(
        'https://peraturan.bpk.go.id/Details/example/uu-no-1-tahun-2015',html,'text/html',
        requested_provisions=['Pasal 2'],max_candidates=2,expected_identity_key='UU:1:2015')
    assert out['resolved'] is True
    assert out['text_identity_key']=='UU:1:2015'
    assert out['legal_role']=='BODY'
    assert out['relationship_verified'] is False


def test_r38_unrelated_annex_identity_remains_fail_closed(monkeypatch):
    import legal_sources as ls
    html=b'''<html><body>
      UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015 TENTANG
      PENETAPAN PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 1 TAHUN 2014
      TENTANG PEMILIHAN GUBERNUR, BUPATI, DAN WALIKOTA MENJADI UNDANG-UNDANG.
      <a href="/Download/wrong-lampiran.pdf">Lampiran</a>
    </body></html>'''
    monkeypatch.setattr(ls,'fetch_official_document',lambda url,timeout=5:{
        'reachable':True,'official_host':True,'final_url':url,'content_type':'application/pdf','body':b'x'})
    monkeypatch.setattr(ls,'_extract_pdf_text',lambda body:
        'PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 2 TAHUN 2014. Pasal 2 salah.')
    out=ls.resolve_official_fulltext(
        'https://peraturan.bpk.go.id/Details/example/uu-no-1-tahun-2015',html,'text/html',
        requested_provisions=['Pasal 2'],max_candidates=2,expected_identity_key='UU:1:2015')
    # The parent detail remains available as identity provenance, but the wrong
    # annex cannot become the provision source or an incorporated resolution.
    assert out['legal_role'] != 'INCORPORATED_INSTRUMENT'
    assert out.get('relationship_verified') is False
    assert out.get('incorporated_identity_key') is None


def test_r38_pipeline_uses_incorporated_text_for_provision_only_and_preserves_parent_lifecycle(monkeypatch):
    import services.regulatory_retrieval as rr
    row={
        'title':'UU No. 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota',
        'url':'https://peraturan.bpk.go.id/Details/example/uu-no-1-tahun-2015',
        'source_id':'bpk','source_name':'BPK','authoritative':True,
        'query':'Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota',
        'query_origin':'EXACT_CASE_REGULATION','case_nexus_domains':['electoral_ethics'],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN','relevance_score':1.0,
        'requested_provisions':['Pasal 2'],
        'provision_binding_provenance':{
            'case_bound':True,'exact_case_text':['Pasal 2'],
            'qualified_case_citation':['Pasal 2 UU 1 Tahun 2015'],
            'instrument_key':'UU:1:2015',
        },
    }
    row['document_classification']=rr.classify_legal_document_candidate(row)
    parent_html=(
        'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota. '
        'Status Peraturan: Berlaku. Tanggal Berlaku 02 Februari 2015.'
    ).encode()
    monkeypatch.setattr(rr,'fetch_official_document',lambda url,timeout=5:{
        'reachable':True,'official_host':True,'final_url':url,'content_type':'text/html','body':parent_html})
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':True,'source_url':'https://peraturan.bpk.go.id/Download/example/Lampiran-UU-1-2015.pdf',
        'content_type':'application/pdf',
        'text':'PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 1 TAHUN 2014. Tanggal Berlaku 02 Oktober 2014. Pasal 2 asas pemilihan.',
        'resolver_status':'ATTACHMENT_PDF_TEXT','resolved_identity_key':'UU:1:2015',
        'text_identity_key':'PERPU:1:2014','identity_candidates':['PERPU:1:2014'],
        'identity_aligned':True,'legal_role':'INCORPORATED_INSTRUMENT',
        'incorporated_identity_key':'PERPU:1:2014',
        'incorporation_parent_identity_key':'UU:1:2015','relationship_verified':True,
    })
    out=rr._verify_positive_law_results([row],snapshot={},max_documents=10)[0]
    pv=out['positive_law_verification']
    assert pv['identity_confirmed'] is True
    assert pv['effective_date']=='2015-02-02'
    assert pv['provision_verification']['verified_count']==1
    assert pv['provision_verification']['verified']==['Pasal 2']
    assert pv['fulltext_reconciliation']['legal_role']=='INCORPORATED_INSTRUMENT'
    assert pv['fulltext_reconciliation']['incorporated_instrument_key']=='PERPU:1:2014'
    assert pv['fulltext_reconciliation']['relationship_verified'] is True


def test_r41_actual_candidate_identity_prevents_case_bound_provision_contamination():
    import services.regulatory_retrieval as rr
    rows=[
        {
            'title':'Undang-Undang Nomor 1 Tahun 2015',
            'url':'https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015',
            'query':'Undang-Undang Nomor 1 Tahun 2015',
            'query_origin':'EXACT_CASE_REGULATION',
        },
        {
            'title':'Undang-Undang Nomor 10 Tahun 2016',
            'url':'https://peraturan.bpk.go.id/Details/37311/uu-no-10-tahun-2016',
            'query':'Undang-Undang Nomor 1 Tahun 2015',
            'query_origin':'EXACT_CASE_REGULATION',
        },
        {
            'title':'Undang-Undang Nomor 8 Tahun 2015',
            'url':'https://peraturan.bpk.go.id/Details/38208/uu-no-8-tahun-2015',
            'query':'Undang-Undang Nomor 1 Tahun 2015',
            'query_origin':'EXACT_CASE_REGULATION',
        },
    ]
    bound=rr._attach_requested_provisions(
        rows,['Pasal 2'],[],qualified_queries=[],
        case_exact_queries={'Undang-Undang Nomor 1 Tahun 2015'},
        case_binding_map={'UU:1:2015':['Pasal 2']},
    )
    assert bound[0]['requested_provisions']==['Pasal 2']
    assert bound[0]['provision_binding_provenance']['instrument_key']=='UU:1:2015'
    assert bound[0]['provision_binding_provenance']['identity_alignment']=='DIRECT_MATCH'
    assert bound[1]['requested_provisions']==[]
    assert bound[1]['provision_binding_provenance']['instrument_key']=='UU:10:2016'
    assert bound[1]['provision_binding_provenance']['identity_alignment']=='MISMATCH'
    assert bound[2]['requested_provisions']==[]
    assert bound[2]['provision_binding_provenance']['instrument_key']=='UU:8:2015'
    assert rr._is_exact_case_verification_row(bound[1]) is False
    assert rr._is_exact_case_verification_row(bound[2]) is False


def test_r41_verified_fulltext_row_wins_monotonic_canonical_merge():
    import services.regulatory_retrieval as rr
    stale={
        'title':'Undang-Undang Nomor 1 Tahun 2015',
        'url':'https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015',
        'query':'Undang-Undang Nomor 1 Tahun 2015',
        'query_origin':'EXACT_CASE_REGULATION',
        'canonical_instrument_key':'UU:1:2015',
        'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:1:2015'},
        'positive_law_verification':{
            'identity_confirmed':True,'case_nexus_status':'CASE_NEXUS_VERIFIED',
            'provision_verification':{'status':'PROVISION_UNVERIFIED','requested':['Pasal 2'],'verified':[],'unverified':['Pasal 2'],'verified_count':0,'requested_count':1},
        },
    }
    verified={
        **stale,
        'url':'https://peraturan.bpk.go.id/Download/26438/UU%20Nomor%201%20Tahun%202015.pdf',
        'fulltext_resolution':{'resolved':True},
        'positive_law_verification':{
            'identity_confirmed':True,'case_nexus_status':'CASE_NEXUS_VERIFIED','text_retrieved':True,
            'provision_verification':{'status':'PROVISION_VERIFIED','requested':['Pasal 2'],'verified':['Pasal 2'],'unverified':[],'verified_count':1,'requested_count':1},
        },
    }
    out=rr._consolidate_exact_case_rows([stale,verified])
    assert len(out)==1
    pv=out[0]['positive_law_verification']['provision_verification']
    assert pv['verified_count']==1
    assert pv['requested_count']==1
    assert pv['verified']==['Pasal 2']
    assert out[0]['canonical_merge_applied'] is True


def test_r41_mismatched_actual_identities_are_not_collapsed_into_expected_bucket():
    import services.regulatory_retrieval as rr
    rows=[]
    for number,year in [('1','2015'),('10','2016'),('8','2015')]:
        rows.append({
            'title':f'Undang-Undang Nomor {number} Tahun {year}',
            'url':f'https://peraturan.bpk.go.id/Details/example/uu-no-{number}-tahun-{year}',
            'query':'Undang-Undang Nomor 1 Tahun 2015',
            'query_origin':'EXACT_CASE_REGULATION',
            'positive_law_verification':{},
        })
    out=rr._consolidate_exact_case_rows(rows)
    # Only the actual UU 1/2015 row qualifies as exact-case.  Wrong-identity hits
    # remain independent discovery rows under their own identities.
    keys=[rr._candidate_actual_identity_key(r) for r in out]
    assert keys==['UU:1:2015','UU:10:2016','UU:8:2015']
    assert sum(1 for r in out if rr._is_exact_case_verification_row(r))==1


def test_r42_unverified_exact_case_candidate_is_preserved_for_identity_fetch():
    import services.regulatory_retrieval as rr
    row={
        "title":"Download",
        "url":"https://peraturan.bpk.go.id/Download/example/document.pdf",
        "query":"Undang-Undang Nomor 1 Tahun 2015",
        "query_origin":"EXACT_CASE_REGULATION",
        "authoritative":True,
        "provision_binding_provenance":{
            "case_bound":True,"instrument_key":"UU:1:2015",
            "exact_case_text":["Pasal 2"],
        },
    }
    assert rr._candidate_actual_identity_key(row) is None
    assert rr._identity_alignment_state(row) == "UNVERIFIED"
    assert rr._is_exact_case_verification_row(row) is True
    assert rr._verification_identity_key(row) == "UU:1:2015"


def test_r42_proven_mismatch_is_rejected_from_exact_case_bucket():
    import services.regulatory_retrieval as rr
    row={
        "title":"Undang-Undang Nomor 10 Tahun 2016",
        "url":"https://peraturan.bpk.go.id/Details/37311/uu-no-10-tahun-2016",
        "query":"Undang-Undang Nomor 1 Tahun 2015",
        "query_origin":"EXACT_CASE_REGULATION",
        "provision_binding_provenance":{
            "case_bound":False,"instrument_key":"UU:10:2016",
        },
    }
    assert rr._identity_alignment_state(row) == "MISMATCH"
    assert rr._is_exact_case_verification_row(row) is False
    assert rr._verification_identity_key(row).startswith("MISMATCH:UU:10:2016<-UU:1:2015:")


def test_r42_direct_match_can_canonicalize_after_actual_identity_is_known():
    import services.regulatory_retrieval as rr
    row={
        "title":"Undang-Undang Nomor 1 Tahun 2015",
        "url":"https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015",
        "query":"Undang-Undang Nomor 1 Tahun 2015",
        "query_origin":"EXACT_CASE_REGULATION",
        "provision_binding_provenance":{"case_bound":True,"instrument_key":"UU:1:2015"},
    }
    assert rr._identity_alignment_state(row) == "DIRECT_MATCH"
    assert rr._is_exact_case_verification_row(row) is True
    assert rr._verification_identity_key(row) == "UU:1:2015"


def test_integrated_closure_unverified_exact_candidate_survives_contract_at_selection_and_processing(monkeypatch):
    """One decision must govern both queue selection and processing.

    Regression covered: R42 preserved an UNVERIFIED exact candidate while
    building the fetch queue, but the processing loop re-applied the raw
    identity contract and rejected the same row before fetch.
    """
    import services.regulatory_retrieval as rr

    row={
        'title':'Download',
        'url':'https://peraturan.bpk.go.id/Download/example/uu1.pdf',
        'source_id':'bpk','source_name':'BPK','authoritative':True,
        'query':'Undang-Undang Nomor 1 Tahun 2015',
        'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['electoral_ethics'],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'relevance_score':1.0,
        'requested_provisions':['Pasal 2'],
        'provision_binding_provenance':{
            'case_bound':True,
            'instrument_key':'UU:1:2015',
            'exact_case_text':['Pasal 2'],
        },
    }
    row['document_classification']={
        'legal_instrument_candidate':True,
        'reason':'test exact case candidate',
    }

    def fake_contract(*args, **kwargs):
        if str(kwargs.get('phase') or '').upper() == 'POSTFETCH':
            return {'passed':True,'reason':'POSTFETCH_OFFICIAL_TEXT_CONFIRMED'}
        return {'passed':False,'reason':'AMBIGUOUS_PREFETCH_METADATA'}
    monkeypatch.setattr(rr,'evaluate_instrument_identity_contract',fake_contract)
    fetched=[]
    monkeypatch.setattr(rr,'fetch_official_document',lambda url,timeout=5:(
        fetched.append(url) or {
            'reachable':True,'official_host':True,'final_url':url,
            'content_type':'application/pdf','body':b'pdf',
        }
    ))
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':True,'source_url':row['url'],'content_type':'application/pdf',
        'text':'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015. Pasal 2 asas.',
        'resolver_status':'ATTACHMENT_PDF_TEXT','resolved_identity_key':'UU:1:2015',
        'text_identity_key':'UU:1:2015','identity_aligned':True,'legal_role':'BODY',
    })
    monkeypatch.setattr(rr,'verify_document_candidate',lambda candidate,source_text,snapshot:{
        'official_source_confirmed':True,'text_retrieved':True,'identity_confirmed':True,
        'legal_status':'IN_FORCE','tempus_status':'TEMPUS_UNVERIFIED',
        'case_nexus_status':'CASE_NEXUS_VERIFIED','final_status':'VERIFICATION_REQUIRED',
        'professional_verification':'PENDING',
        'provision_text_location':{
            'status':'PROVISION_TEXT_LOCATED','requested':['Pasal 2'],'located':['Pasal 2'],'not_located':[],'citations':[]
        },
        'provision_verification':{
            'status':'PROVISION_VERIFIED','requested':['Pasal 2'],'verified':['Pasal 2'],'unverified':[],
            'verified_count':1,'requested_count':1,'citations':[]
        },
    })
    monkeypatch.setattr(rr,'apply_post_verification_status_semantics',lambda pv,candidate:pv)

    out=rr._verify_positive_law_results([row],snapshot={},max_documents=10,time_budget_seconds=8)[0]
    assert fetched == [row['url']]
    assert out['prefetch_identity_decision']['alignment']=='UNVERIFIED'
    assert out['prefetch_identity_decision']['preserved_unverified_exact'] is True
    assert out['positive_law_verification']['fetch_attempted'] is True
    assert out['positive_law_verification']['identity_confirmed'] is True
    assert out['positive_law_verification']['provision_verification']['verified_count']==1


def test_integrated_closure_proven_exact_mismatch_stays_rejected_even_if_contract_passes(monkeypatch):
    import services.regulatory_retrieval as rr
    row={
        'title':'Undang-Undang Nomor 10 Tahun 2016',
        'url':'https://peraturan.bpk.go.id/Details/37311/uu-no-10-tahun-2016',
        'source_id':'bpk','source_name':'BPK','authoritative':True,
        'query':'Undang-Undang Nomor 1 Tahun 2015',
        'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['electoral_ethics'],
        'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'relevance_score':1.0,
        'requested_provisions':[],
        'provision_binding_provenance':{'case_bound':False,'instrument_key':'UU:10:2016'},
        'document_classification':{'legal_instrument_candidate':True,'reason':'test'},
    }
    monkeypatch.setattr(rr,'evaluate_instrument_identity_contract',lambda *a,**k:{'passed':True,'reason':'test'})
    fetched=[]
    monkeypatch.setattr(rr,'fetch_official_document',lambda url,timeout=5:(fetched.append(url) or {}))
    out=rr._verify_positive_law_results([row],snapshot={},max_documents=10,time_budget_seconds=8)[0]
    assert rr._identity_alignment_state(row)=='MISMATCH'
    assert fetched == []
    assert out['positive_law_verification']['identity_contract_rejected'] is True
    assert out['prefetch_identity_decision']['reason']=='PROVEN_EXACT_CASE_IDENTITY_MISMATCH'


def test_integrated_closure_two_case_bound_exact_instruments_both_reach_fetch_and_keep_provisions(monkeypatch):
    """End-to-end scheduler invariant for two exact case citations.

    One candidate is directly identifiable before fetch and the other is
    case-bound but UNVERIFIED. Both must survive to official verification; the
    latter must not disappear simply because its metadata contract is ambiguous.
    """
    import services.regulatory_retrieval as rr

    rows=[
        {
            'title':'Undang-Undang Nomor 7 Tahun 2017',
            'url':'https://peraturan.bpk.go.id/Download/example/uu7.pdf',
            'source_id':'bpk','source_name':'BPK','authoritative':True,
            'query':'Undang-Undang Nomor 7 Tahun 2017',
            'query_origin':'EXACT_CASE_REGULATION',
            'case_nexus_domains':['electoral_ethics'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
            'relevance_score':1.0,'requested_provisions':['Pasal 3'],
            'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:7:2017','exact_case_text':['Pasal 3']},
            'document_classification':{'legal_instrument_candidate':True,'reason':'test'},
        },
        {
            'title':'Download',
            'url':'https://peraturan.bpk.go.id/Download/example/uu1.pdf',
            'source_id':'bpk','source_name':'BPK','authoritative':True,
            'query':'Undang-Undang Nomor 1 Tahun 2015',
            'query_origin':'EXACT_CASE_REGULATION',
            'case_nexus_domains':['electoral_ethics'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
            'relevance_score':1.0,'requested_provisions':['Pasal 2'],
            'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:1:2015','exact_case_text':['Pasal 2']},
            'document_classification':{'legal_instrument_candidate':True,'reason':'test'},
        },
    ]

    def fake_contract(expected_key, candidate, **kwargs):
        if str(kwargs.get('phase') or '').upper() == 'POSTFETCH':
            return {'passed':True,'reason':'official text confirmed'}
        if candidate.get('title') == 'Download':
            return {'passed':False,'reason':'ambiguous prefetch metadata'}
        return {'passed':True,'reason':'direct metadata match'}
    monkeypatch.setattr(rr,'evaluate_instrument_identity_contract',fake_contract)

    fetched=[]
    monkeypatch.setattr(rr,'fetch_official_document',lambda url,timeout=5:(
        fetched.append(url) or {'reachable':True,'official_host':True,'final_url':url,'content_type':'application/pdf','body':url.encode()}
    ))
    def fake_resolve(url, body, content_type, requested_provisions=None, **kwargs):
        if 'uu7' in url:
            return {'resolved':True,'source_url':url,'content_type':'application/pdf',
                    'text':'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 7 TAHUN 2017. Pasal 3 asas.',
                    'resolver_status':'ATTACHMENT_PDF_TEXT','resolved_identity_key':'UU:7:2017',
                    'text_identity_key':'UU:7:2017','identity_aligned':True,'legal_role':'BODY'}
        return {'resolved':True,'source_url':url,'content_type':'application/pdf',
                'text':'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015. Pasal 2 asas.',
                'resolver_status':'ATTACHMENT_PDF_TEXT','resolved_identity_key':'UU:1:2015',
                'text_identity_key':'UU:1:2015','identity_aligned':True,'legal_role':'BODY'}
    monkeypatch.setattr(rr,'resolve_official_fulltext',fake_resolve)

    def fake_verify(candidate, source_text, snapshot):
        requested=list(candidate.get('requested_provisions') or [])
        return {
            'official_source_confirmed':True,'text_retrieved':True,'identity_confirmed':True,
            'legal_status':'IN_FORCE','tempus_status':'TEMPUS_UNVERIFIED',
            'case_nexus_status':'CASE_NEXUS_VERIFIED','final_status':'VERIFICATION_REQUIRED',
            'professional_verification':'PENDING',
            'provision_text_location':{'status':'PROVISION_TEXT_LOCATED','requested':requested,'located':requested,'not_located':[],'citations':[]},
            'provision_verification':{'status':'PROVISION_VERIFIED','requested':requested,'verified':requested,'unverified':[],
                                      'verified_count':len(requested),'requested_count':len(requested),'citations':[]},
        }
    monkeypatch.setattr(rr,'verify_document_candidate',fake_verify)
    monkeypatch.setattr(rr,'apply_post_verification_status_semantics',lambda pv,candidate:pv)

    out=rr._verify_positive_law_results(rows,snapshot={},max_documents=10,time_budget_seconds=8)
    assert set(fetched)=={rows[0]['url'],rows[1]['url']}
    by_key={r.get('canonical_instrument_key') or rr._candidate_actual_identity_key(r) or rr._expected_identity_key_for_fulltext(r):r for r in out}
    assert by_key['UU:7:2017']['positive_law_verification']['provision_verification']['verified']==['Pasal 3']
    assert by_key['UU:1:2015']['positive_law_verification']['provision_verification']['verified']==['Pasal 2']


def test_integrated_final_detail_html_is_not_provision_capable_when_requested_article_missing():
    import services.regulatory_retrieval as rr
    detail={
        'resolved':True,'identity_aligned':True,'resolved_identity_key':'UU:1:2015',
        'source_url':'https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015',
        'resolver_status':'DETAIL_HTML_TEXT',
        'text':'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015 metadata status perubahan.',
    }
    assert rr._resolved_fulltext_satisfies_provision_contract(detail,['Pasal 2']) is False
    detail['text'] += ' Pasal 2 ketentuan.'
    assert rr._resolved_fulltext_satisfies_provision_contract(detail,['Pasal 2']) is True


def test_integrated_final_exact_recovery_runs_when_aligned_detail_html_lacks_requested_article(monkeypatch):
    """Identity-aligned metadata HTML must not block exact fulltext recovery."""
    import services.regulatory_retrieval as rr

    detail_url='https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015'
    pdf_url='https://peraturan.bpk.go.id/Download/26438/UU%20Nomor%201%20Tahun%202015.pdf'
    row={
        'title':'Undang-Undang Nomor 1 Tahun 2015',
        'url':detail_url,
        'source_id':'bpk','source_name':'BPK','authoritative':True,
        'query':'Undang-Undang Nomor 1 Tahun 2015',
        'query_origin':'EXACT_CASE_REGULATION',
        'case_nexus_domains':['electoral_ethics'],'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
        'relevance_score':1.0,'requested_provisions':['Pasal 2'],
        'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:1:2015','exact_case_text':['Pasal 2']},
        'document_classification':{'legal_instrument_candidate':True,'reason':'test'},
    }
    monkeypatch.setattr(rr,'evaluate_instrument_identity_contract',lambda *a,**k:{'passed':True,'reason':'test'})
    monkeypatch.setattr(rr,'fetch_official_document',lambda url,timeout=5:{
        'reachable':True,'official_host':True,'final_url':url,
        'content_type':'text/html','body':b'<html>UU Nomor 1 Tahun 2015 status metadata</html>',
    })
    monkeypatch.setattr(rr,'resolve_official_fulltext',lambda *a,**k:{
        'resolved':True,'source_url':detail_url,'content_type':'text/html',
        'text':'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015 status metadata.',
        'resolver_status':'DETAIL_HTML_TEXT','resolved_identity_key':'UU:1:2015',
        'text_identity_key':'UU:1:2015','identity_aligned':True,'legal_role':'DETAIL',
    })
    recover_calls=[]
    monkeypatch.setattr(rr,'_recover_expected_official_fulltext',lambda *a,**k:(
        recover_calls.append((a,k)) or {
            'resolved':True,'source_url':pdf_url,'content_type':'application/pdf',
            'text':'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 1 TAHUN 2015. Pasal 2 asas.',
            'resolver_status':'RECOVERED_EXACT_IDENTITY_ATTACHMENT_PDF_TEXT',
            'resolved_identity_key':'UU:1:2015','text_identity_key':'UU:1:2015',
            'identity_aligned':True,'legal_role':'BODY','recovery_exact_lock':True,
        }
    ))
    monkeypatch.setattr(rr,'apply_post_verification_status_semantics',lambda pv,candidate:pv)

    out=rr._verify_positive_law_results([row],snapshot={},max_documents=10,time_budget_seconds=8)[0]
    pv=out['positive_law_verification']
    assert recover_calls
    assert out['fulltext_resolution']['source_url']==pdf_url
    assert pv['provision_verification']['verified_count']==1
    assert pv['provision_verification']['verified']==['Pasal 2']
    assert pv['provision_source_url']==pdf_url


def test_integrated_exact_case_jobs_are_built_independent_of_discovery(monkeypatch):
    import services.regulatory_retrieval as rr
    bindings=[
        {'identity':{'key':'UU:7:2017'},'query':'Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum','provisions':['Pasal 3']},
        {'identity':{'key':'UU:1:2015'},'query':'Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota','provisions':['Pasal 2']},
    ]
    seeds={
        'UU:7:2017':('local_corpus',{'title':'Undang-Undang Nomor 7 Tahun 2017','url':'https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017','source_name':'BPK'}),
        'UU:1:2015':('local_corpus',{'title':'Undang-Undang Nomor 1 Tahun 2015','url':'https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015','source_name':'BPK'}),
    }
    monkeypatch.setattr(rr,'_canonical_official_seed_candidates',lambda key:[seeds[key]] if key in seeds else [])
    rows=rr._build_exact_case_verification_rows(bindings,[{'id':'electoral_ethics','role':'PRIMARY'}],2021)
    assert len(rows)==2
    by_key={r['expected_identity_key']:r for r in rows}
    assert by_key['UU:7:2017']['requested_provisions']==['Pasal 3']
    assert by_key['UU:1:2015']['requested_provisions']==['Pasal 2']
    assert all(r['query_origin']=='EXACT_CASE_REGULATION' for r in rows)
    assert all(r['exact_verification_job'] is True for r in rows)
    assert all(r['provision_binding_provenance']['case_bound'] is True for r in rows)
    assert all(r['provision_binding_provenance']['verification_job']=='DETERMINISTIC_EXACT_CASE_CITATION' for r in rows)


def test_integrated_exact_job_row_stays_eligible_while_actual_identity_unverified(monkeypatch):
    import services.regulatory_retrieval as rr
    binding={'identity':{'key':'UU:1:2015'},'query':'Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota','provisions':['Pasal 2']}
    monkeypatch.setattr(rr,'_canonical_official_seed_candidates',lambda key:[('local_corpus',{
        'title':'Undang-Undang Nomor 1 Tahun 2015','url':'https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015','source_name':'BPK'})])
    row=rr._build_exact_case_verification_rows([binding],[{'id':'electoral_ethics','role':'PRIMARY'}],2021)[0]
    monkeypatch.setattr(rr,'evaluate_instrument_identity_contract',lambda *a,**k:{'passed':True,'reason':'unverified metadata allowed'})
    decision=rr._prefetch_identity_decision(row, row['instrument_identity_contract'] if row.get('instrument_identity_contract') else {'passed':True})
    assert decision['eligible'] is True
    assert decision['alignment'] in ('UNVERIFIED','DIRECT_MATCH')
