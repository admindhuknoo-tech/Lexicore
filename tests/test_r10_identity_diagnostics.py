from services.regulatory_retrieval import _collect_identity_verification_diagnostics


def test_collects_located_but_unverified_identity_diagnostic():
    rows=[{
        'url':'https://jdih.example/uu31-1999.pdf',
        'query_origin':'EXACT_CASE_REGULATION',
        'requested_provisions':['Pasal 3'],
        'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:31:1999'},
        'positive_law_verification':{
            'identity_confirmed':False,
            'identity':{
                'expected_key':'UU:31:1999',
                'actual_identity_candidates':['UU:20:2001'],
                'match_reason':'OFFICIAL_TEXT_IDENTITY_MISMATCH',
                'expected_identity_source':'case_bound_instrument_key',
            },
            'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
            'provision_text_location':{'located':['Pasal 3']},
            'provision_verification':{'requested':['Pasal 3'],'verified':[],'verified_count':0},
            'fulltext_reconciliation':{
                'source_instrument_key':'UU:31:1999',
                'resolved_instrument_key':'UU:20:2001',
                'identity_aligned':False,
                'provision_binding_preserved':True,
                'resolver_status':'OFFICIAL_FULLTEXT_RESOLVED',
            },
            'final_status':'UNVERIFIED_IDENTITY_MISMATCH',
        },
    }]
    d=_collect_identity_verification_diagnostics(rows)
    assert len(d)==1
    assert d[0]['expected_instrument_key']=='UU:31:1999'
    assert d[0]['resolved_instrument_key']=='UU:20:2001'
    assert d[0]['identity_confirmed'] is False
    assert d[0]['located_provisions']==['Pasal 3']
    assert d[0]['provision_binding_preserved'] is True


def test_does_not_report_verified_provision_as_failure():
    rows=[{
        'url':'https://jdih.example/uu31-1999.pdf',
        'requested_provisions':['Pasal 3'],
        'positive_law_verification':{
            'identity_confirmed':True,
            'identity':{'expected_key':'UU:31:1999','key':'UU:31:1999'},
            'case_nexus_status':'CASE_NEXUS_VERIFIED',
            'provision_text_location':{'located':['Pasal 3']},
            'provision_verification':{'requested':['Pasal 3'],'verified':['Pasal 3'],'verified_count':1},
        },
    }]
    assert _collect_identity_verification_diagnostics(rows)==[]
