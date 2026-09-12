from services.semantic_admission import build_statement_contract
from services.sal_source_of_truth import build_governed_pools, enforce_governed_consumers, governed_summary_lines, pool_for_consumer
from services.legal_reasoning_chain import build_reasoning_chain


def _row(text, idx, domain='civil_contract', source_classification=None):
    row={'statement':text,'label':'SOURCE FACT','source_index':idx}
    if source_classification:
        row['source_classification']=source_classification
    row['sal_contract']=build_statement_contract(
        text,index=idx,prefix='PA',source_item=row,
        domain_contract={'primary_domain':domain,'posture':'PRE_LITIGATION_ADVISORY'},
        posture='PRE_LITIGATION_ADVISORY'
    )
    return row


def test_remedy_phrase_never_enters_alleged_act_positive_pool():
    r={'source_text':'Ganti rugi materiil dan immateriil','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[_row('Ganti rugi (materiil dan immateriil)',1)]}
    build_governed_pools(r)
    assert pool_for_consumer(r,'Alleged Act') == []


def test_actor_plus_current_act_is_required_for_alleged_act():
    r={'source_text':'Debitur belum membayar pinjaman','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[_row('Debitur belum membayar pinjaman yang telah jatuh tempo.',1)]}
    build_governed_pools(r)
    assert len(pool_for_consumer(r,'Alleged Act')) == 1


def test_current_issue_requires_same_domain_source_law_clash():
    r={'source_text':'Debitur belum membayar pinjaman yang telah jatuh tempo.','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[_row('Debitur belum membayar pinjaman yang telah jatuh tempo.',1)],'legal_issues':['Apakah terjadi wanprestasi?']}
    build_governed_pools(r); enforce_governed_consumers(r)
    assert pool_for_consumer(r,'Issue') == []
    assert r['legal_issues'] == []
    assert r['current_issue_gate'] == 'BLOCKED_ROUTE_CONTRACT'


def test_current_issue_can_open_with_same_domain_source_law_citation():
    fact=_row('Debitur belum membayar pinjaman yang telah jatuh tempo.',1)
    law=_row('Pasal 1238 KUHPerdata mengenai keadaan lalai dalam perikatan.',2)
    r={'source_text':'pinjaman wanprestasi','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[fact,law],'legal_issues':['Apakah terjadi wanprestasi?']}
    build_governed_pools(r); enforce_governed_consumers(r)
    assert pool_for_consumer(r,'Issue')
    assert r['legal_issues'] == ['Apakah terjadi wanprestasi?']


def test_employment_outsourcing_norm_rejected_from_contract_case():
    r={'source_text':'utang pinjaman wanprestasi','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[],
       'applicable_law':[{'source':'Syarat-Syarat Penyerahan Sebagian Pelaksanaan Pekerjaan Kepada Perusahaan Lain','domain':'Ketenagakerjaan','status':'UNVERIFIED'},
                         {'source':'KUHPerdata tentang perikatan dan wanprestasi','domain':'Perdata & Perikatan','status':'UNVERIFIED'}]}
    pools=build_governed_pools(r)
    assert any('Penyerahan Sebagian' in x['source'] for x in pools['rejected_law_pool'])
    assert all('Penyerahan Sebagian' not in x['source'] for x in pools['candidate_law_pool'])
    assert any('KUHPerdata' in x['source'] for x in pools['candidate_law_pool'])


def test_governed_summary_never_calls_future_action_fact():
    rows=[_row('Menyiapkan bukti transfer minggu depan.',1),_row('Ganti rugi materiil dan immateriil',2)]
    r={'source_text':'x','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':rows,'legal_issues':[]}
    build_governed_pools(r); enforce_governed_consumers(r)
    lines=governed_summary_lines(r)
    assert any(x.startswith('Fakta kunci: belum ada') for x in lines)
    assert any(x.startswith('Rencana tindakan:') and 'Menyiapkan bukti' in x for x in lines)
    assert not any(x.startswith('Fakta kunci:') and 'Menyiapkan bukti' in x for x in lines)


def test_chain_blocks_template_issue_when_current_issue_pool_empty():
    r={'source_text':'Ganti rugi materiil','domain_contract':{'primary_domain':'civil_contract'},'source_ledger':[_row('Ganti rugi materiil',1)],
       'element_matrix':[{'id':'loss_nexus','element':'Kerugian dan hubungan kausal dengan pelanggaran kewajiban','owner_domain':'civil_contract','owner_issue':'Apakah kerugian mempunyai hubungan kausal?','alleged_act':'Ganti rugi materiil','status':'NOT_ESTABLISHED'}],
       'legal_issues':['Apakah kerugian mempunyai hubungan kausal?'],'applicable_law':[]}
    build_governed_pools(r); enforce_governed_consumers(r)
    chain=build_reasoning_chain(r)['chains'][0]
    assert chain['issue']['status']=='MISSING'
    assert chain['alleged_act']['status']=='MISSING'
    assert chain['status']=='BLOCKED_ROUTE_CONTRACT'
