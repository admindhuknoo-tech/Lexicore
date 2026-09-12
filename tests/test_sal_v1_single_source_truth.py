from services.semantic_admission import build_statement_contract
from services.sal_source_of_truth import build_governed_pools, pool_for_consumer, route_token_allows
from services.legal_reasoning_chain import build_reasoning_chain


def _row(text, idx, source_classification=None):
    src={'statement':text,'label':'SOURCE FACT','source_index':idx}
    if source_classification:
        src['source_classification']=source_classification
    src['sal_contract']=build_statement_contract(text,index=idx,prefix='T',source_item=src,domain_contract={'primary_domain':'civil_contract','posture':'PRE_LITIGATION_ADVISORY'})
    return src


def test_lead_only_document_reference_never_enters_evidence_pool():
    r={'source_text':'pinjaman wanprestasi','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[_row('surat perjanjian hutang piutang',0)]}
    pools=build_governed_pools(r)
    assert pools['evidence_map_pool']==[]
    assert pools['isolated_document_audit_pool']
    assert not route_token_allows(r,pools['isolated_document_audit_pool'][0],'Evidence Map')


def test_future_bukti_kerugian_never_enters_alleged_act_pool():
    r={'source_text':'Menyiapkan bukti kerugian','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[_row('Menyiapkan bukti kerugian',0)]}
    build_governed_pools(r)
    assert pool_for_consumer(r,'Alleged Act')==[]
    assert pool_for_consumer(r,'Evidence Map')==[]
    assert pool_for_consumer(r,'Action Plan')


def test_bare_bukti_kerugian_reference_never_enters_alleged_act_pool():
    r={'source_text':'wanprestasi pinjaman','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[_row('bukti kerugian',0)]}
    build_governed_pools(r)
    assert pool_for_consumer(r,'Alleged Act')==[]
    assert pool_for_consumer(r,'Evidence Map')==[]


def test_primary_evidence_only_pool():
    r={'source_text':'utang pinjaman','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[
        _row('Mutasi rekening tercatat transfer Rp100000000 tanggal 1 Mei 2024.',0,'ACTUAL_EVIDENTIARY_ITEM'),
        _row('Adanya Surat Perjanjian Nomor 10 tanggal 2 Mei 2024.',1),
    ]}
    pools=build_governed_pools(r)
    assert len(pools['evidence_map_pool'])==1
    assert pools['evidence_map_pool'][0]['semantic_type']=='PRIMARY_EVIDENCE'


def test_mining_law_removed_from_civil_contract_pool():
    r={'source_text':'utang pinjaman wanprestasi somasi','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[],
       'applicable_law':[{'source':'Tata Cara Dan Syarat-Syarat Pengajuan Izin Usaha Pertambangan (IUP)','domain':'Pertambangan','status':'UNVERIFIED'},
                         {'source':'KUHPerdata tentang perikatan dan wanprestasi','domain':'Perdata & Perikatan','status':'UNVERIFIED'}]}
    pools=build_governed_pools(r)
    assert all('Pertambangan' not in x['source'] for x in pools['candidate_law_pool'])
    assert any('Pertambangan' in x['source'] for x in pools['rejected_law_pool'])


def test_chain_has_no_raw_fallback_for_evidence_or_alleged_act():
    ref=_row('surat perjanjian hutang piutang',0)
    r={'source_text':'pinjaman wanprestasi','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[ref],
       'element_matrix':[{'id':'valid_contract','element':'Keberadaan dan keabsahan hubungan/perjanjian yang mengikat para pihak','owner_domain':'civil_contract','owner_issue':'Apakah terdapat hubungan kontraktual yang sah dan kewajiban yang mengikat?','supporting_evidence':[{'source_index':0,'statement':'surat perjanjian hutang piutang'}],'alleged_act':'surat perjanjian hutang piutang','status':'NOT_ESTABLISHED'}],
       'legal_issues':['Apakah terdapat hubungan kontraktual yang sah dan kewajiban yang mengikat?'], 'applicable_law':[]}
    build_governed_pools(r)
    chain=build_reasoning_chain(r)['chains'][0]
    assert chain['evidence']['status']=='MISSING'
    assert chain['alleged_act']['status']=='MISSING'
    assert chain['applicable_law']['status']=='MISSING'


def test_missing_route_token_is_blocked_when_governor_enforced():
    r={'source_text':'x','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[]}
    build_governed_pools(r)
    assert not route_token_allows(r,{'statement':'raw leaked row'},'Evidence Map')
