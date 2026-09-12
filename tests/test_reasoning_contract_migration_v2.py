from services.element_reasoning import build_element_reasoning
from services.reasoning_contract import attach_reasoning_contract, CONTRACT_STAGES
from services.document_posture_resolver import resolve_document_posture


def test_cross_domain_civil_litigation_merges_procedure_land_religious_elements():
    ledger=[
        {'label':'SOURCE FACT','statement':'Para Tergugat mengajukan DUPLIK dan tetap pada eksepsi kompetensi absolut karena substansi sengketa berkaitan dengan hak waris dan harta peninggalan.'},
        {'label':'SOURCE FACT','statement':'Penggugat menyatakan Sertipikat Hak Milik cacat hukum tetapi tidak memohon pembatalan sertipikat tersebut.'},
        {'label':'SOURCE FACT','statement':'Penggugat mendalilkan Perbuatan Melawan Hukum dan kerugian atas objek tanah yang disengketakan.'},
    ]
    out=build_element_reasoning(
        domain_contract={'primary_domain':'civil_procedure','domain_contract':['civil_procedure','land_property','religious_court','civil_contract']},
        ledger=ledger,
    )
    ids={r['id'] for r in out['element_matrix']}
    assert 'absolute_competence' in ids
    assert 'land_right_identity' in ids
    assert 'inheritance_character' in ids
    assert 'pmh_unlawful_act' in ids
    assert 'valid_contract' not in ids
    issue_ids={r['id'] for r in out['issue_element_tests']}
    assert {'procedural_validity','land_title_chain','religious_absolute_forum','pmh_elements'}.issubset(issue_ids)


def test_duplik_preserves_specific_document_stage():
    text='DUPLIK PARA TERGUGAT PERKARA NOMOR 44/Pdt.G/2026/PN.KPn. Dalam eksepsi kompetensi absolut.'
    profile=resolve_document_posture({'ranah_hukum':'PERDATA','posisi_pengguna':'TERGUGAT'}, {'source_text':text})
    assert profile['document_subtype']=='DUPLIK'
    assert profile['document_type']=='Duplik'


def test_reasoning_contract_is_attached_with_all_eleven_stages():
    result={
        'legal_issues':['Apakah kompetensi absolut forum tepat?'],
        'element_matrix':[{
            'element':'Kompetensi absolut forum',
            'status':'NOT_ESTABLISHED',
            'supporting_evidence':[{'source_index':2,'statement':'Duplik mempersoalkan kompetensi absolut.','label':'SOURCE FACT'}],
            'counter_evidence':[],
        }],
        'applicable_law':[{'source':'Hukum acara kandidat','status':'UNVERIFIED','domain':'civil_procedure'}],
        'action_plan':[{'priority':'P1','issue':'Kompetensi absolut','action':'Verifikasi dasar forum dan status para pihak.'}],
        'causation_analysis':{'status':'NEXUS_NOT_ESTABLISHED','reason':'Nexus belum dapat ditetapkan.'},
    }
    attach_reasoning_contract(result)
    assert result['reasoning_contract']['status']=='PASS'
    row=result['legal_reasoning_chain']['chains'][0]
    assert set(CONTRACT_STAGES).issubset(row)
    assert row['causation']['status']=='GAP'
