from services.legal_reasoning_chain import build_reasoning_chain
from services.case_consistency_guard import material_source_ledger


def test_element_not_instantiated_without_admitted_issue_and_law():
    result = {
        'sal_single_source_of_truth': True,
        'sal_governed_pools': {
            'orchestration_status': 'ENFORCED',
            'current_issue_pool': [],
            'candidate_law_pool': [],
            'route_token_ledger': {},
        },
        'element_reasoning': {
            'elements': [{
                'element': 'Cidera janji/wanprestasi atau kegagalan memenuhi prestasi',
                'owner_domain': 'civil_contract',
                'owner_issue_id': 'I1',
                'status': 'NEEDS_EVIDENCE',
            }]
        },
        'legal_issues': ['Apakah terjadi wanprestasi?'],
        'domain_contract': {'primary_domain': 'civil_contract'},
        'source_text': 'rencana somasi dan gugatan',
        'source_ledger': [],
    }
    chain = build_reasoning_chain(result)['chains'][0]
    assert chain['status'] == 'BLOCKED_ROUTE_CONTRACT'
    assert chain['issue']['status'] == 'MISSING'
    assert chain['applicable_law']['status'] == 'MISSING'
    assert chain['legal_elements']['status'] == 'ELEMENT_NOT_INSTANTIATED'
    assert chain['legal_elements']['element'] == ''
    assert chain['evidence']['count'] == 0
    assert chain['alleged_act']['status'] == 'MISSING'


def test_material_trace_preserves_sal_document_reference_label_metadata():
    ledger = [{
        'statement': 'bukti kerugian',
        'label': 'SOURCE FACT',
        'source_classification': 'CASE_FACT',
        'sal_semantic_type': 'DOCUMENT_REFERENCE',
        'sal_admissibility_state': 'LEAD_ONLY',
        'statement_id': 'SAL_STMT_1',
        'evidence': 'bukti kerugian',
    }]
    rows = material_source_ledger(ledger)
    assert len(rows) == 1
    assert rows[0]['sal_semantic_type'] == 'DOCUMENT_REFERENCE'
    assert rows[0]['sal_admissibility_state'] == 'LEAD_ONLY'
    assert rows[0]['sal_statement_id'] == 'SAL_STMT_1'
