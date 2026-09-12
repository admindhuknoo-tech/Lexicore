import json
from pathlib import Path

from services.semantic_admission import (
    build_sal_contract,
    build_statement_contract,
    classify_semantic_type,
    law_subject_matter_admissible,
    validate_and_route_sal_payload,
    validate_payload,
)
from services.document_posture_resolver import resolve_document_posture


def test_schema_anchor_is_valid_and_payload_passes():
    p=build_statement_contract('Apakah benar tanda tangan Saudara?', index=1, prefix='BAP')
    validate_payload(p)
    assert p['semantic_envelope']['semantic_type']=='QUESTION'
    assert p['admission_contract']['admissibility_state']=='REJECTED'
    assert 'Evidence Map' in p['admission_contract']['prohibited_routes']


def test_lely_future_evidence_plan_is_not_evidence():
    p=build_statement_contract('Menyiapkan bukti surat perjanjian hutang piutang - bukti transaksi/transfer - saksi-saksi - bukti kerugian', index=2, prefix='LELY')
    assert p['semantic_envelope']['semantic_type']=='FUTURE_ACTION'
    assert p['admission_contract']['admissibility_state']=='REJECTED'
    assert 'Evidence Map' in p['admission_contract']['prohibited_routes']
    assert p['downstream_migration']['primary_target_node']=='Action Plan'


def test_lely_future_somasi_is_not_historical_fact():
    p=build_statement_contract('Memberikan somasi 1-3x, yang isinya rincian pinjaman yang harus dikembalikan.', index=3, prefix='LELY')
    assert p['semantic_envelope']['semantic_type']=='FUTURE_ACTION'
    assert p['admission_contract']['admissibility_state']=='REJECTED'


def test_bap_question_is_interrogation_context_only():
    p=build_statement_contract('Kapan dokumen lembar pertimbangan/keputusan komite kredit tersebut dibuat?', index=4, prefix='BAP')
    assert p['semantic_envelope']['semantic_type']=='QUESTION'
    assert p['admission_contract']['restricted_routes']==['Interrogation Context']


def test_party_argument_is_limited_not_fact_or_evidence():
    p=build_statement_contract('Tersangka menyatakan bahwa uang tersebut merupakan pinjaman pribadi, bukan suap.', index=5, prefix='BAP')
    assert p['semantic_envelope']['semantic_type']=='PARTY_ARGUMENT'
    assert p['admission_contract']['admissibility_state']=='LIMITED'
    assert 'Alleged Act' in p['admission_contract']['restricted_routes']
    assert 'Evidence Map' in p['admission_contract']['prohibited_routes']


def test_document_reference_is_lead_only():
    p=build_statement_contract('Adanya Surat Perjanjian Nomor 10 tanggal 2 Mei 2024.', index=6, prefix='GEN')
    assert p['semantic_envelope']['semantic_type']=='DOCUMENT_REFERENCE'
    assert p['admission_contract']['admissibility_state']=='LEAD_ONLY'
    assert 'Evidence Map' in p['admission_contract']['prohibited_routes']


def test_actual_primary_evidence_requires_upstream_evidentiary_provenance():
    p=build_statement_contract('Mutasi rekening tercatat transfer Rp100000000 tanggal 1 Mei 2024.', index=7, prefix='BANK', source_item={'source_classification':'ACTUAL_EVIDENTIARY_ITEM'})
    assert p['semantic_envelope']['semantic_type']=='PRIMARY_EVIDENCE'
    assert p['admission_contract']['admissibility_state']=='ADMITTED'
    assert 'Evidence Map' in p['admission_contract']['restricted_routes']


def test_hki_law_rejected_from_plain_debt_contract_subject_matter():
    ok,reason=law_subject_matter_admissible(
        'Syarat dan Tata Cara Permohonan Pencatatan Perjanjian Lisensi Kekayaan Intelektual',
        case_domains=['civil_contract'],
        case_text='utang pinjaman wanprestasi somasi pengembalian pinjaman'
    )
    assert not ok
    assert reason=='SUBJECT_MATTER_MISMATCH_HKI'


def test_hki_law_allowed_when_case_is_actually_hki():
    ok,_=law_subject_matter_admissible(
        'Peraturan tentang pencatatan perjanjian lisensi kekayaan intelektual',
        case_domains=['civil_contract'],
        case_text='sengketa lisensi paten dan kekayaan intelektual'
    )
    assert ok


def test_air_gap_fallback_isolates_invalid_payload():
    p=validate_and_route_sal_payload('{not-json', 'teks sumber anomali')
    assert p['semantic_envelope']['provenance']=='SYSTEM_CRITICAL_FALLBACK'
    assert p['admission_contract']['admissibility_state']=='LEAD_ONLY'
    assert p['admission_contract']['restricted_routes']==['Document Audit']
    assert p['downstream_migration']['next_execution_directive']=='FORCE_MANUAL_PROFESSIONAL_VERIFICATION'


def test_lely_note_posture_is_prelitigation_advisory_not_claim():
    text='''LELY\nHAK PAK ADI YANG BISA DITUNTUTKAN KE PAK AGUS\nPROSES DAN PROSEDUR\n1. Memberikan somasi 1-3x.\n2. Apabila tidak berhasil, dilanjutkan Mediasi di luar sidang.\n3. Apabila tidak berhasil, mengajukan gugatan ke PN. Menyiapkan bukti surat perjanjian hutang piutang.'''
    r=resolve_document_posture({'ranah_hukum':'PERDATA','posisi_pengguna':'BELUM_TERIDENTIFIKASI'},{'source_text':text})
    assert r['posture']=='PRE_LITIGATION_ADVISORY'
    assert 'Pra-Litigasi' in r['document_type']


def test_build_sal_contract_removes_future_and_questions_from_retrieval_seed():
    text='Utang pinjaman telah jatuh tempo.\nApakah sudah dibayar?\nMenyiapkan bukti transfer minggu depan.'
    sal=build_sal_contract(text, domain_contract={'primary_domain':'civil_contract','posture':'PERDATA_SENGKETA_KONTRAK'})
    assert 'Utang pinjaman telah jatuh tempo.' in sal['retrieval_text']
    assert 'Apakah sudah dibayar?' not in sal['retrieval_text']
    assert 'Menyiapkan bukti transfer' not in sal['retrieval_text']


def test_golden_anchor_dataset_contract_expectations():
    root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'golden_datasets'/'SAL-v1.0-edge-cases.json').read_text(encoding='utf-8'))
    assert data['contract']=='SAL-1.0'
    assert len(data['cases']) >= 5
