from services.instrument_identity_contract import evaluate_instrument_identity_contract
from services.element_reasoning import build_element_reasoning


def test_prefetch_semantic_mismatch_is_deferred_when_structure_matches():
    row={
        'title':'UU No. 7 Tahun 2017',
        'url':'https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017',
        'description':'metadata ringkas menyebut lembaga lain dan belum memuat subject lengkap',
    }
    r=evaluate_instrument_identity_contract(
        'UU:7:2017',row,
        expected_text='Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum',
        active_domains=['electoral_ethics'],phase='PREFETCH')
    assert r['type_match'] is True
    assert r['number_year_match'] is True
    assert r['passed'] is True


def test_postfetch_semantic_mismatch_can_fail_closed_after_identity_structure_matches():
    row={
        'title':'UU No. 7 Tahun 2017',
        'url':'https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017',
        'description':'',
    }
    r=evaluate_instrument_identity_contract(
        'UU:7:2017',row,
        expected_text='Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum',
        active_domains=['electoral_ethics'],phase='POSTFETCH',
        official_text='UNDANG-UNDANG NOMOR 7 TAHUN 2017 TENTANG KOMISI PEMBERANTASAN TINDAK PIDANA KORUPSI KPK')
    assert r['type_match'] is True
    assert r['number_year_match'] is True
    assert r['passed'] is False
    assert 'SUBJECT_FAMILY_MISMATCH' in r['reason'] or 'DOMAIN_INCOMPATIBLE' in r['reason']


def test_prefetch_still_hard_rejects_same_number_wrong_instrument_type():
    row={
        'title':'Peraturan KPU No. 7 Tahun 2017',
        'url':'https://jdih.kpu.go.id/peraturan-kpu-no-7-tahun-2017',
        'description':'Pemilihan Umum',
    }
    r=evaluate_instrument_identity_contract(
        'UU:7:2017',row,
        expected_text='Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum',
        active_domains=['electoral_ethics'],phase='PREFETCH')
    assert r['passed'] is False
    assert r['type_match'] is False


def test_exact_case_query_gets_generic_canonical_seed_when_search_recall_is_empty(monkeypatch):
    import services.regulatory_retrieval as rr
    monkeypatch.setattr(rr,'federated_search_many',lambda *a,**k:{'Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum':[]})
    monkeypatch.setattr(rr,'_canonical_official_seed_candidates',lambda key:[('local_corpus',{
        'title':'UU No. 7 Tahun 2017','description':'Pemilihan Umum',
        'url':'https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017',
        'source_name':'JDIH BPK RI / KPU / Bawaslu'})] if key=='UU:7:2017' else [])
    q='Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum'
    out=rr._compact_searches(
        [q],[{'id':'electoral_ethics','role':'PRIMARY'}],None,
        per_source_limit=2,case_exact_queries={q.lower()})
    rows=out['results']
    assert any(r.get('url','').endswith('/uu-no-7-tahun-2017') for r in rows)
    seed=next(r for r in rows if r.get('url','').endswith('/uu-no-7-tahun-2017'))
    assert seed['query_origin']=='EXACT_CASE_REGULATION'
    assert seed['instrument_identity_contract']['passed'] is True


def test_issue_proposition_binding_stops_organization_evidence_from_filling_education_issue():
    ledger=[
        {'label':'ALLEGATION','statement':'Pengadu mendalilkan Teradu masih menjadi pengurus Lazismu dan KNPI.'},
        {'label':'DENIAL / LIMITATION','statement':'Teradu telah mengundurkan diri dari Lazismu dan diberhentikan dengan hormat.'},
        {'label':'SOURCE FACT','statement':'Dokumen pendidikan menunjukkan S2 berlangsung 2018 sampai 2020 dan perlu diuji waktu perkuliahan serta izin.'},
        {'label':'DENIAL / LIMITATION','statement':'Tidak ada bukti perkuliahan mengganggu tugas KPU atau menyebabkan rapat ditinggalkan.'},
    ]
    out=build_element_reasoning(
        domain_contract={'primary_domain':'electoral_ethics','domain_contract':['electoral_ethics']},
        ledger=ledger,existing_matrix=[])
    by_id={x['id']:x for x in out['issue_element_tests']}
    prof=by_id['professional_activity']
    all_statements=' '.join(e['statement'].lower() for e in prof['supporting_evidence']+prof['counter_evidence'])
    assert 'pendidikan' in all_statements or 'perkuliahan' in all_statements
    assert not ('masih menjadi pengurus lazismu' in all_statements and 'pendidikan' not in all_statements)


def test_low_quality_ocr_fragment_does_not_populate_element_matrix():
    ledger=[
        {'label':'SOURCE FACT','statement':'n n edn n edn an ea an anan status pengurus organisasi x'},
        {'label':'DOCUMENT','statement':'Bukti T-3 Surat Keputusan Lazismu menerima pengunduran diri dan memberhentikan dengan hormat Teradu.'},
    ]
    out=build_element_reasoning(
        domain_contract={'primary_domain':'electoral_ethics','domain_contract':['electoral_ethics']},
        ledger=ledger,existing_matrix=[])
    mapped=' '.join(x['statement'].lower() for x in out['evidence_to_element_mapping'])
    assert 'n n edn n edn' not in mapped
