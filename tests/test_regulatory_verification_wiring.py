from services.regulatory_retrieval import (
    _extract_case_regulation_bindings,
    _case_binding_provision_map,
    _attach_requested_provisions,
    _summarize_positive_law_verification,
)
from legal_sources import public_secondary_source_registry


def test_exact_case_text_binds_multiple_articles_to_same_instrument():
    text = (
        "KEDUA Perbuatan Terdakwa dianggap melanggar Pasal 3 jo Pasal 18 "
        "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi."
    )
    bindings = _extract_case_regulation_bindings(text)
    assert bindings
    row = next(x for x in bindings if x["identity"]["key"] == "UU:31:1999")
    assert row["provisions"] == ["Pasal 3", "Pasal 18"]
    assert row["provenance"] == "EXACT_CASE_TEXT"


def test_requested_provisions_are_attached_by_exact_instrument_identity():
    text = (
        "Perbuatan didakwakan melanggar Pasal 3 jo Pasal 18 "
        "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi."
    )
    binding_map = _case_binding_provision_map(text)
    results = [{
        "title": "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "query": "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "url": "https://peraturan.bpk.go.id/",
        "authoritative": True,
    }]
    attached = _attach_requested_provisions(
        results, [], [], qualified_queries=[],
        case_exact_queries={"uu nomor 31 tahun 1999 tentang pemberantasan tindak pidana korupsi"},
        case_binding_map=binding_map,
    )
    assert attached[0]["requested_provisions"] == ["Pasal 3", "Pasal 18"]


def test_hukumonline_is_secondary_and_never_authoritative():
    rows = public_secondary_source_registry()
    ho = next(x for x in rows if x["id"] == "hukumonline")
    assert ho["authoritative"] is False
    assert ho["source_kind"] == "secondary_legal_research"


def test_common_republk_typo_still_binds_case_citation_without_silent_year_correction():
    text = (
        "jo Pasal 20 huruf a UU Republk Indonesia Nomor 1 Tahun 2023 "
        "Tentang Kitab Undang-Undang Hukum Pidana jo Undang-Undang Nomor 1 Tahun 2026 "
        "Tentang Penyesuaian Pidana."
    )
    bindings = _extract_case_regulation_bindings(text)
    b2023 = next(x for x in bindings if x["identity"]["key"] == "UU:1:2023")
    b2026 = next(x for x in bindings if x["identity"]["key"] == "UU:1:2026")
    assert b2023["provisions"] == ["Pasal 20 huruf a"]
    assert b2026["provisions"] == []


def test_provision_requested_counter_survives_identity_or_network_failure():
    rows = [{
        "requested_provisions": ["Pasal 3", "Pasal 18"],
        "positive_law_verification": {
            "identity_confirmed": False,
            "legal_status": "UNVERIFIED",
            "tempus_status": "TEMPUS_UNVERIFIED",
            "final_status": "UNVERIFIED",
        },
    }]
    out = _summarize_positive_law_verification(rows)
    assert out["provision_requested"] == 2
    assert out["provision_verified"] == 0
    assert out["positive_law_verified"] == 0


def test_local_subject_match_does_not_propagate_pasals_to_different_instrument():
    results = [{
        "title": "UU Nomor 20 Tahun 2001 tentang Perubahan atas UU Tipikor",
        "query": "UU Nomor 20 Tahun 2001 tentang Perubahan atas UU Tipikor",
        "url": "https://peraturan.bpk.go.id/",
        "authoritative": True,
    }]
    local_matches = [{
        "regulation": {"nomor": "UU Nomor 31 Tahun 1999", "tentang": "Pemberantasan Tindak Pidana Korupsi"},
        "matched_articles": [{"pasal": "Pasal 3"}, {"pasal": "Pasal 18"}],
    }]
    attached = _attach_requested_provisions(
        results, [], local_matches, qualified_queries=[], case_exact_queries=set(), case_binding_map={}
    )
    assert attached[0]["requested_provisions"] == []


def test_html_detail_reruns_identity_against_resolved_official_fulltext(monkeypatch):
    import services.regulatory_retrieval as rr

    results = [{
        "title": "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "query": "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "url": "https://peraturan.bpk.go.id/Details/47181/uu-no-31-tahun-1999",
        "authoritative": True,
        "requested_provisions": ["Pasal 3"],
        "document_classification": {"legal_instrument_candidate": True, "reason": "test"},
        "case_nexus_status": "CASE_NEXUS_VERIFIED",
    }]

    monkeypatch.setattr(rr, "fetch_official_document", lambda *a, **k: {
        "reachable": True, "official_host": True, "content_type": "text/html",
        "body": b"<html><body>metadata only</body></html>", "final_url": results[0]["url"],
        "connectivity_status": "REACHABLE", "error": None,
    })
    monkeypatch.setattr(rr, "resolve_official_fulltext", lambda *a, **k: {
        "resolved": True,
        "source_url": "https://peraturan.bpk.go.id/Download/official.pdf",
        "content_type": "application/pdf",
        "text": "UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999. Pasal 3 Setiap orang ...",
        "resolver_status": "ATTACHMENT_PDF_TEXT",
        "attempted_urls": [results[0]["url"]],
    })

    enriched = rr._verify_positive_law_results(results, snapshot={}, max_documents=2)
    pv = enriched[0]["positive_law_verification"]
    assert pv["identity_confirmed"] is True
    assert pv["provision_verification"]["verified_count"] == 1
    assert pv["provision_source_status"] == "ATTACHMENT_PDF_TEXT"


def test_summary_counts_unique_instrument_provision_pairs_not_duplicate_search_hits():
    rows = [
        {
            "query": "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
            "requested_provisions": ["Pasal 3", "Pasal 18"],
            "positive_law_verification": {"identity_confirmed": False},
        },
        {
            "query": "UU Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
            "requested_provisions": ["Pasal 3", "Pasal 18"],
            "positive_law_verification": {"identity_confirmed": False},
        },
    ]
    out = _summarize_positive_law_verification(rows)
    assert out["provision_requested"] == 2


def test_verification_budget_prefers_identity_aligned_requested_instrument(monkeypatch):
    import services.regulatory_retrieval as rr

    bad = {
        "title": "Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "query": "Undang-Undang Nomor 31 Tahun 2099 tentang Pemberantasan Tindak Pidana Korupsi",
        "url": "https://peraturan.bpk.go.id/bad",
        "authoritative": True,
        "query_origin": "EXACT_CASE_REGULATION",
        "case_nexus_status": "CASE_NEXUS_UNCERTAIN",
        "case_nexus_domains": ["corruption"],
        "requested_provisions": ["Pasal 3"],
        "document_classification": {"legal_instrument_candidate": True},
        "relevance_score": 0.99,
    }
    good = {
        "title": "Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "query": "Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "url": "https://peraturan.bpk.go.id/good",
        "authoritative": True,
        "query_origin": "KNOWN_REGULATION",
        "case_nexus_status": "CASE_NEXUS_UNCERTAIN",
        "case_nexus_domains": ["corruption"],
        "requested_provisions": ["Pasal 3"],
        "document_classification": {"legal_instrument_candidate": True},
        "relevance_score": 0.80,
    }
    seen=[]
    def fake_fetch(url, timeout=5):
        seen.append(url)
        text=("Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi. "
              "Status Peraturan: Berlaku. Pasal 3 setiap orang ...")
        return {"reachable":True,"official_host":True,"content_type":"text/html",
                "body":text.encode(),"final_url":url,"connectivity_status":"REACHABLE","error":None}
    monkeypatch.setattr(rr, "fetch_official_document", fake_fetch)
    monkeypatch.setattr(rr, "resolve_official_fulltext", lambda *a, **k: {"resolved":False,"text":"","source_url":a[0],"resolver_status":"DETAIL_HTML_ONLY"})
    out=rr._verify_positive_law_results([bad,good], snapshot={}, max_documents=1)
    assert seen == [good["url"]]
    assert out[1]["positive_law_verification"]["identity_confirmed"] is True
    assert out[1]["positive_law_verification"]["provision_verification"]["verified_count"] == 1


def test_verification_budget_keeps_direct_pdf_fallback_for_same_instrument(monkeypatch):
    import services.regulatory_retrieval as rr

    base={
        "title":"Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "query":"Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "authoritative":True,
        "query_origin":"KNOWN_REGULATION",
        "case_nexus_status":"CASE_NEXUS_UNCERTAIN",
        "case_nexus_domains":["corruption"],
        "requested_provisions":["Pasal 3"],
        "document_classification":{"legal_instrument_candidate":True},
        "relevance_score":0.9,
    }
    detail=dict(base, url="https://peraturan.bpk.go.id/Details/45350/uu-no-31-tahun-1999")
    pdf=dict(base, url="https://peraturan.bpk.go.id/Home/Download/33850/UU%20Nomor%2031%20Tahun%201999.pdf")
    seen=[]
    def fake_fetch(url, timeout=5):
        seen.append(url)
        if url.endswith('.pdf'):
            text=("UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999 "
                  "TENTANG PEMBERANTASAN TINDAK PIDANA KORUPSI Pasal 3 setiap orang ...")
            return {"reachable":True,"official_host":True,"content_type":"application/pdf",
                    "body":b"%PDF-fake","final_url":url,"connectivity_status":"REACHABLE","error":None}
        return {"reachable":True,"official_host":True,"content_type":"text/html",
                "body":b"metadata page","final_url":url,"connectivity_status":"REACHABLE","error":None}
    monkeypatch.setattr(rr, "fetch_official_document", fake_fetch)
    monkeypatch.setattr(rr, "resolve_official_fulltext", lambda url, body, ctype, **k: {
        "resolved":url.endswith('.pdf'),
        "text":(("UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999 "
                 "TENTANG PEMBERANTASAN TINDAK PIDANA KORUPSI Pasal 3 setiap orang ...") if url.endswith('.pdf') else ""),
        "source_url":url,
        "resolver_status":"DIRECT_PDF_TEXT" if url.endswith('.pdf') else "DETAIL_HTML_ONLY",
    })
    out=rr._verify_positive_law_results([detail,pdf], snapshot={}, max_documents=1)
    assert pdf['url'] in seen
    assert any((r.get('positive_law_verification') or {}).get('provision_verification',{}).get('verified_count') == 1 for r in out)


def test_domain_rule_queries_cover_active_domains_beyond_known_regulation_table():
    from services.regulatory_retrieval import _domain_rule_query_domains
    domains=[{'id':'financial_services','role':'PRIMARY'},{'id':'corruption','role':'SECONDARY'}]
    assert _domain_rule_query_domains('POJK BPR manajemen risiko kredit', domains)==['financial_services']
    assert _domain_rule_query_domains('UU Tipikor penyalahgunaan kewenangan kerugian negara', domains)==['corruption']


def test_domain_rule_origin_has_verification_priority_over_discovery():
    from services import regulatory_retrieval as rr
    base={
        "title":"Undang-Undang Nomor 31 Tahun 1999",
        "query":"Undang-Undang Nomor 31 Tahun 1999",
        "url":"https://peraturan.bpk.go.id/example",
        "authoritative":True,
        "requested_provisions":["Pasal 3"],
        "case_nexus_status":"CASE_NEXUS_UNCERTAIN",
        "relevance_score":0.8,
    }
    domain=dict(base, query_origin="DOMAIN_RULE_REGULATION")
    discovery=dict(base, query_origin="DISCOVERY")
    assert rr._verification_candidate_priority(domain) > rr._verification_candidate_priority(discovery)


def test_domain_rule_origin_is_not_zero_rank_in_compact_search_contract():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/"services"/"regulatory_retrieval.py").read_text(encoding="utf-8")
    assert '"DOMAIN_RULE_REGULATION":2' in src
    assert "'DOMAIN_RULE_REGULATION':2" in src


def test_known_regulation_registry_covers_all_non_civil_procedure_domains():
    import services.regulatory_retrieval as rr
    domain_ids={r['id'] for r in rr.DOMAIN_RULES}
    assert set(rr.KNOWN_REGULATION_QUERIES) == domain_ids
    assert rr.KNOWN_REGULATION_QUERIES['civil_procedure'] == ()
    populated={k for k,v in rr.KNOWN_REGULATION_QUERIES.items() if v}
    assert len(populated) == len(domain_ids) - 1
    for required in (
        'financial_services','employment','corruption','criminal','civil_contract',
        'corporate','constitutional','regional_government','consumer','data_privacy',
        'bankruptcy','arbitration','administrative','public_information','investment',
    ):
        assert rr.KNOWN_REGULATION_QUERIES[required]


def test_bpr_tipikor_tempus_keeps_priority_after_known_registry_expansion():
    import services.regulatory_retrieval as rr
    text=(
        'Berita Acara Pemeriksaan tersangka mantan Direksi Perumda BPR. '
        'Persetujuan kredit debitur, komite kredit, BMPK, prinsip kehati-hatian, '
        'dugaan korupsi dan penyalahgunaan kewenangan serta Pasal 603. '
        'Perjanjian kredit terjadi pada tahun 2022.'
    )
    domains=rr.detect_domains(text)
    queries=rr.build_case_queries(
        text, 'BAP Kredit BPR', provision_refs=['Pasal 603'], domains=domains,
        qualified_queries=['Perdata & Perikatan perjanjian utang piutang'], max_queries=10,
    )
    assert any('tempus delicti 2022' in q for q in queries)
    assert len(queries) <= 10


def test_summary_separates_text_located_from_legally_verified_provisions():
    rows=[{
        'title':'UU Nomor 31 Tahun 1999',
        'query':'UU Nomor 31 Tahun 1999',
        'requested_provisions':['Pasal 3'],
        'positive_law_verification':{
            'identity_confirmed':False,
            'provision_text_location':{
                'requested':['Pasal 3'],'located':['Pasal 3'],
                'located_count':1,'requested_count':1,
            },
            'provision_verification':{
                'requested':['Pasal 3'],'verified':[],
                'verified_count':0,'requested_count':1,
                'status':'PROVISION_BLOCKED_BY_INSTRUMENT_GATE',
            },
            'legal_status':'STATUS_UNCERTAIN',
            'tempus_status':'TEMPUS_UNVERIFIED',
            'final_status':'UNVERIFIED',
        },
    }]
    out=_summarize_positive_law_verification(rows)
    assert out['provision_requested']==1
    assert out['provision_located']==1
    assert out['provision_verified']==0


def test_requested_provision_attachment_preserves_case_binding_provenance():
    rows=[{
        'title':'UU Nomor 31 Tahun 1999', 'query':'UU Nomor 31 Tahun 1999',
        'url':'https://example.go.id/uu31',
    }]
    attached=_attach_requested_provisions(
        rows, [], [], case_binding_map={'UU:31:1999':['Pasal 3','Pasal 18']}
    )
    assert attached[0]['requested_provisions']==['Pasal 3','Pasal 18']
    prov=attached[0]['provision_binding_provenance']
    assert prov['case_bound'] is True
    assert prov['instrument_key']=='UU:31:1999'
    assert prov['exact_case_text']==['Pasal 3','Pasal 18']


def test_r11_generated_qualified_queries_do_not_create_case_binding_when_source_map_exists():
    from services.regulatory_retrieval import _attach_requested_provisions
    rows=[{
        'title':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
        'query':'Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
    }]
    out=_attach_requested_provisions(
        rows, ['Pasal 3','Pasal 18'], [],
        qualified_queries=['Undang-Undang Nomor 31 Tahun 1999 Pasal 3 Pasal 18'],
        case_exact_queries={rows[0]['query'].lower()},
        case_binding_map={'UU:31:1999':['Pasal 18']},
    )
    assert out[0]['requested_provisions']==['Pasal 18']
    assert out[0]['provision_binding_provenance']['exact_case_text']==['Pasal 18']
    assert out[0]['provision_binding_provenance']['generated_research_refs']==['Pasal 3']


def test_r11_text_verification_is_separate_from_case_nexus_gate():
    from services.positive_law_verification import verify_document_candidate
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
    text='UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 31 TAHUN 1999. Pasal 3 Ketentuan contoh.'
    out=verify_document_candidate(row, source_text=text, snapshot={})
    assert out['identity_confirmed'] is True
    assert out['provision_text_verification']['status']=='PROVISION_VERIFIED'
    assert out['provision_verification']['status']=='PROVISION_BLOCKED_BY_INSTRUMENT_GATE'
    assert out['case_nexus_status']=='CASE_NEXUS_UNCERTAIN'


def test_r11_fulltext_resolver_rejects_wrong_instrument_even_with_matching_pasals(monkeypatch):
    import legal_sources
    html=b'<html><a href="/wrong.pdf">download</a></html>'
    wrong=(b'%PDF-FAKE')
    monkeypatch.setattr(legal_sources, 'fetch_official_document', lambda url, timeout=5: {
        'reachable':True,'official_host':True,'content_type':'application/pdf','body':wrong,'final_url':url
    })
    monkeypatch.setattr(legal_sources, '_extract_pdf_text', lambda body: 'UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 20 TAHUN 2001 Pasal 3 Pasal 18')
    out=legal_sources.resolve_official_fulltext(
        'https://peraturan.example/detail',''.join(chr(x) for x in html).encode('latin1'),'text/html',
        requested_provisions=['Pasal 3'], expected_identity_key='UU:31:1999', max_candidates=8)
    assert out['resolved'] is False
    assert out['identity_aligned'] is False
    assert out['resolver_status']=='EXPECTED_IDENTITY_NOT_FOUND'
