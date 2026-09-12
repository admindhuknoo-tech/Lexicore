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


def test_r22_exact_lock_failure_report_uses_post_recovery_state_not_legacy_mismatch():
    rows=[{
        'url':'https://peraturan.bpk.go.id/Details/legacy-uu5',
        'query_origin':'EXACT_CASE_REGULATION',
        'requested_provisions':['Pasal 3'],
        'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:31:1999'},
        'fulltext_resolution':{
            'resolved':False,
            'expected_identity_key':'UU:31:1999',
            'resolver_status':'EXPECTED_IDENTITY_EXACT_CANDIDATE_FAILED',
            'recovery_exact_lock':True,
            'recovery_candidate_trace':[{
                'title_identity':'UU:31:1999',
                'reason':'EXACT_TITLE_IDENTITY',
                'title':'UU No. 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi',
            }],
        },
        'positive_law_verification':{
            'identity_confirmed':False,
            'identity':{
                'expected_key':'UU:31:1999',
                'key':'UU:5:2017',
                'actual_identity_candidates':['UU:5:2017','UU:30:2002'],
                'match_reason':'OFFICIAL_TEXT_IDENTITY_MISMATCH',
            },
            'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
            'provision_text_location':{'located':['Pasal 3']},
            'provision_verification':{'requested':['Pasal 3'],'verified':[],'verified_count':0},
            'fulltext_reconciliation':{
                'source_instrument_key':'UU:31:1999',
                'resolved_instrument_key':'UU:5:2017',
                'identity_aligned':False,
                'provision_binding_preserved':True,
                'resolver_status':'OFFICIAL_TEXT_IDENTITY_MISMATCH',
            },
            'final_status':'UNVERIFIED_IDENTITY_MISMATCH',
        },
    }]
    d=_collect_identity_verification_diagnostics(rows)
    assert len(d)==1
    assert d[0]['expected_instrument_key']=='UU:31:1999'
    assert d[0]['resolved_instrument_key']==''
    assert d[0]['identity_confirmed'] is False
    assert d[0]['identity_match_reason']=='EXPECTED_IDENTITY_EXACT_CANDIDATE_FAILED'
    assert d[0]['exact_lock_active'] is True
    assert 'UU:5:2017' not in d[0]['identity_candidates']
    assert d[0]['identity_candidates']==['UU:31:1999']


def test_r22_exact_lock_success_report_uses_exact_identity():
    rows=[{
        'url':'https://peraturan.bpk.go.id/Details/legacy-uu5',
        'requested_provisions':['Pasal 3'],
        'provision_binding_provenance':{'case_bound':True,'instrument_key':'UU:31:1999'},
        'fulltext_resolution':{
            'resolved':True,
            'identity_aligned':True,
            'expected_identity_key':'UU:31:1999',
            'resolved_identity_key':'UU:31:1999',
            'resolver_status':'RECOVERED_EXACT_IDENTITY_DIRECT_PDF_TEXT',
            'recovery_exact_lock':True,
            'recovery_candidate_trace':[{'title_identity':'UU:31:1999','reason':'EXACT_TITLE_IDENTITY'}],
        },
        'positive_law_verification':{
            'identity_confirmed':False,  # stale legacy state must not drive report
            'identity':{'expected_key':'UU:31:1999','key':'UU:5:2017','match_reason':'OFFICIAL_TEXT_IDENTITY_MISMATCH'},
            'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
            'provision_text_location':{'located':['Pasal 3']},
            'provision_verification':{'requested':['Pasal 3'],'verified':[],'verified_count':0},
            'fulltext_reconciliation':{'source_instrument_key':'UU:31:1999','resolved_instrument_key':'UU:5:2017'},
        },
    }]
    d=_collect_identity_verification_diagnostics(rows)
    assert d[0]['resolved_instrument_key']=='UU:31:1999'
    assert d[0]['identity_confirmed'] is True
    assert d[0]['exact_lock_active'] is True
    assert d[0]['identity_match_reason'].startswith('RECOVERED_EXACT_IDENTITY')


def test_r22_no_exact_lock_preserves_legacy_diagnostic():
    rows=[{
        'url':'https://peraturan.bpk.go.id/Details/legacy-uu5',
        'requested_provisions':['Pasal 3'],
        'fulltext_resolution':{
            'resolved':False,
            'resolver_status':'EXPECTED_IDENTITY_RECOVERY_FAILED',
            'recovery_exact_lock':False,
        },
        'positive_law_verification':{
            'identity_confirmed':False,
            'identity':{'expected_key':'UU:31:1999','key':'UU:5:2017','actual_identity_candidates':['UU:5:2017'],'match_reason':'OFFICIAL_TEXT_IDENTITY_MISMATCH'},
            'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
            'provision_text_location':{'located':['Pasal 3']},
            'provision_verification':{'requested':['Pasal 3'],'verified':[],'verified_count':0},
        },
    }]
    d=_collect_identity_verification_diagnostics(rows)
    assert d[0]['resolved_instrument_key']=='UU:5:2017'
    assert d[0]['exact_lock_active'] is False
