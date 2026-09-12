from exporters.common import _case_export_sections


def _sample_result():
    return {
        'title':'DKPP adaptive projection test',
        'input_type':'document',
        'filename':'ALL_DKPP.pdf',
        'document_reading':{'status':'COMPLETE','segments_read':1,'segments_total':1,'characters':1200},
        'professional_verification':'PENDING',
        'case_working_paper':{
            'working_paper_percentage':{'percentage':27,'confidence':'LOW','disclaimer':'Bukan prediksi.'},
            'evidence_map':{'legal_basis':{'citation':'Regulasi Pemilu','note':'uji sumber resmi'},'rows':[]},
            'legal_construction':{'synthesis':'Etik penyelenggara','chains':[]},
            'action_plan':[],
        },
        'issue_element_tests':[
            {
                'id':'organization_status',
                'issue':'Apakah status kepengurusan masih aktif?',
                'status':'DISPUTED',
                'legal_conclusion':'VERIFICATION_REQUIRED',
                'elements':[
                    {
                        'id':'status_timeline','description':'Status dan tempus kepengurusan',
                        'status':'DISPUTED','mapping_confidence':0.71,
                        'supporting_evidence':[{'source_index':2,'statement':'Nama tercantum dalam struktur 2021.'}],
                        'counter_evidence':[{'source_index':3,'statement':'Pengunduran diri dan nama kemudian dihapus.'}],
                    }
                ],
            }
        ],
        'element_matrix':[{'id':'status_timeline','element':'Status dan tempus kepengurusan','status':'DISPUTED'}],
        'element_test_summary':{'assessed':1,'total':1,'percentage':100,'legal_satisfaction_claimed':False},
        'evidence_to_element_mapping':[
            {'element_id':'status_timeline','element':'Status dan tempus kepengurusan','source_index':2,'role':'SUPPORT','statement':'Nama tercantum dalam struktur 2021.','score':5.2},
            {'element_id':'status_timeline','element':'Status dan tempus kepengurusan','source_index':3,'role':'COUNTER','statement':'Pengunduran diri dan nama kemudian dihapus.','score':6.1},
        ],
        'causation_analysis':{'status':'DISPUTED','element_id':'nexus_impact','reason':'Nexus perlu bukti primer.'},
        'risk_assessment':[{'classification':'MATERIAL_IF_PROVEN','issue':'Apakah status kepengurusan masih aktif?','basis':'1 support; 1 counter','mapping_confidence':0.71}],
        'mitigation_strategy':{'intent':'BAD_FAITH_NOT_ESTABLISHED_FROM_CURRENT_LEDGER','impact':'ACTUAL_IMPACT_NOT_ESTABLISHED_FROM_CURRENT_LEDGER','proportionality':'ASSESS_AFTER_ELEMENT_AND_IMPACT_VERIFICATION','corrective_action':[{'source_index':3,'statement':'Nama kemudian dihapus.'}]},
        'pleading_strategy':{'strategy_sequence':['DISTINGUISH_AMBIGUOUS_FACT_AND_CAPACITY','SHOW_CORRECTIVE_ACTION','REQUEST_PROPORTIONAL_OUTCOME_IF_LIMITED_BREACH_IS_ESTABLISHED'],'output_readiness':'WORKING_DRAFT_ONLY','requires_professional_verification':True,'note':'Tidak mengubah status fakta.'},
        'material_source_ledger':[],
        'applicable_law':[],
        'regulatory_matches':[],
        'case_regulatory_snapshot':{},
        'norm_conflicts':{},
        'coverage_note':'PENDING',
    }


def test_r34_2_projects_adaptive_reasoning_as_dedicated_export_sections():
    _, sections=_case_export_sections(_sample_result())
    titles=[title for title,_ in sections]
    assert 'Element-by-Element Analysis' in titles
    assert 'Evidence-to-Element Matrix / Counter-Evidence' in titles
    assert 'Hubungan Kausal dan Dampak' in titles
    assert 'Risiko dan Mitigasi' in titles
    assert 'Strategi Penyusunan Dokumen' in titles


def test_r34_2_element_projection_contains_support_counter_and_fail_closed_status():
    _, sections=_case_export_sections(_sample_result())
    data=dict(sections)
    text='\n'.join(data['Element-by-Element Analysis'])
    assert 'ISSUE 1:' in text
    assert 'ELEMENT:' in text
    assert 'SUPPORT #2:' in text
    assert 'COUNTER #3:' in text
    assert 'VERIFICATION_REQUIRED' in text
    assert 'Mapping sumber bukan kesimpulan' in text


def test_r34_2_projection_does_not_mutate_readiness_or_verification_state():
    x=_sample_result()
    before=(x['case_working_paper']['working_paper_percentage']['percentage'], x['professional_verification'])
    _case_export_sections(x)
    after=(x['case_working_paper']['working_paper_percentage']['percentage'], x['professional_verification'])
    assert before==after==(27,'PENDING')


def test_r34_2_pdf_and_docx_export_accept_adaptive_sections():
    from exporters.case_pdf import export_case_pdf
    from exporters.case_docx import export_case_docx
    x=_sample_result()
    pdf=export_case_pdf(x)
    docx=export_case_docx(x)
    assert pdf.getvalue().startswith(b'%PDF')
    assert docx.getvalue().startswith(b'PK')
