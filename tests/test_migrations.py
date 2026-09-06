import os
import sqlite3
from pathlib import Path

from services.backup_service import create_database_backup
from database import EXPECTED_COLUMNS, _migrate_schema, schema_drift


def test_additive_migration_heals_stale_client_schema(tmp_path):
    db = tmp_path / 'old.db'
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE client_communications (id INTEGER PRIMARY KEY, message TEXT)')
    conn.commit()
    before = schema_drift(conn)
    assert 'client_communications' in before
    changed = _migrate_schema(conn)
    assert 'client_communications.client_name' in changed
    assert 'client_communications.subject' in changed
    after = schema_drift(conn)
    # Other application tables are absent by design in this focused unit test;
    # the stale client table itself must no longer report missing columns.
    assert 'client_communications' not in after
    conn.close()


def test_sqlite_backup_is_real_snapshot(tmp_path):
    db = tmp_path / 'lexicore.db'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)')
    conn.execute("INSERT INTO sample(value) VALUES('original')")
    conn.commit(); conn.close()
    backup = create_database_backup(str(db), reason='pytest', backup_dir=str(tmp_path / 'backups'))
    assert backup and Path(backup).exists()
    check = sqlite3.connect(backup)
    assert check.execute('SELECT value FROM sample').fetchone()[0] == 'original'
    check.close()



def test_dynamic_case_regulatory_domain_and_query_routing(monkeypatch):
    import services.regulatory_retrieval as rr
    calls=[]
    def fake_search_many(queries, direct_ids=(), per_source_limit=4, max_workers=6, time_budget_seconds=30.0):
        calls.append((tuple(queries), tuple(direct_ids), max_workers, time_budget_seconds))
        result=[{
            'source_id':'kemnaker','source_name':'JDIH Kementerian Ketenagakerjaan',
            'authoritative':True,'reachable':True,'http_status':200,
            'results':[{'title':'PP 35 Tahun 2021 - PHK dan PKWT','url':'https://jdih.kemnaker.go.id/peraturan/test','score':8}],
        }]
        return {q: result for q in queries}
    monkeypatch.setattr(rr,'federated_search_many',fake_search_many)
    text='Karyawan mengalami PHK tanpa pesangon setelah bekerja dengan PKWT dan meminta hak ketenagakerjaan.'
    payload=rr.retrieve_for_case_dynamic(text=text,title='Sengketa PHK',provision_refs=[],qualified_queries=[],local_seed_matches=[],online=True)
    assert payload['mode'].startswith('HYBRID_LOCAL_OFFICIAL')
    assert payload['official_results_count'] >= 1
    assert any(d['id']=='employment' for d in payload['domains'])
    assert calls and any('kemnaker' in ids for _,ids,_,_ in calls)
    assert payload['cache_policy']=='CASE_SCOPED_METADATA_ONLY'


def test_dynamic_case_regulatory_bare_article_is_not_query():
    from services.regulatory_retrieval import build_case_queries, detect_domains
    text='Perkara kredit BPR dengan dugaan pelanggaran Pasal 603.'
    q=build_case_queries(text,'Kasus BPR',provision_refs=['Pasal 603'],domains=detect_domains(text),qualified_queries=[])
    assert 'Pasal 603' not in q


def test_bpr_case_precision_prioritizes_financial_and_corruption_domains():
    import services.regulatory_retrieval as rr
    text = (
        'Berita Acara Pemeriksaan tersangka mantan Direksi Perumda BPR. '
        'Perkara berkaitan dengan persetujuan kredit debitur, komite kredit, BMPK, '
        'prinsip kehati-hatian, dugaan korupsi dan penyalahgunaan kewenangan serta Pasal 603. '
        'Perjanjian kredit dan utang disebut sebagai bagian dari dokumen kredit pada tahun 2022.'
    )
    domains = rr.detect_domains(text)
    assert domains[0]['id'] == 'corruption'
    assert any(d['id'] == 'financial_services' for d in domains[:3])
    civil = next((d for d in domains if d['id'] == 'civil_contract'), None)
    assert not civil or civil['confidence'] < domains[0]['confidence']
    queries = rr.build_case_queries(text, 'BAP Kredit BPR', provision_refs=['Pasal 603'], domains=domains,
                                    qualified_queries=['Perdata & Perikatan perjanjian utang piutang'])
    assert any('BPR' in q and ('tata kelola' in q or 'risiko' in q or 'kredit' in q) for q in queries)
    assert not any(q.lower().startswith('perdata & perikatan') for q in queries)
    assert any('tempus delicti 2022' in q for q in queries)


def test_retrieval_funnel_filters_post_event_results(monkeypatch):
    import services.regulatory_retrieval as rr
    def fake_search_many(queries, direct_ids=(), per_source_limit=4, max_workers=6, time_budget_seconds=30.0):
        result=[{
            'source_id':'ojk','source_name':'OJK','authoritative':True,'reachable':True,'http_status':200,
            'results':[
                {'title':'POJK No. 4 Tahun 2015 Tata Kelola BPR','url':'https://ojk.go.id/2015','score':8},
                {'title':'POJK No. 9 Tahun 2024 Tata Kelola BPR','url':'https://ojk.go.id/2024','score':8},
            ],
        }]
        return {q: result for q in queries}
    monkeypatch.setattr(rr, 'federated_search_many', fake_search_many)
    p = rr.retrieve_for_case_dynamic(
        text='Direksi Perumda BPR menyetujui kredit pada tahun 2022 dengan isu tata kelola dan manajemen risiko.',
        title='Kredit BPR', online=True, provision_refs=[], qualified_queries=[], local_seed_matches=[])
    assert p['event_year_candidate'] == 2022
    assert p['retrieval_funnel']['materially_relevant'] >= 1
    assert any(r['temporal_status'] == 'POST_EVENT_REFERENCE' for b in p['search_bundles'] for s in b['sources'] for r in s['results'] if '2024' in r['title'])
    assert p['retrieval_funnel']['temporal_not_excluded'] <= p['retrieval_funnel']['materially_relevant']


# --------------------------------------------------------------------------
# v1.3.6 comprehensive audit / domain-contract + persistent corpus guards
# --------------------------------------------------------------------------

def test_case_posture_bpr_tipikor_keeps_contract_supporting_only():
    from services.case_domain_classifier import classify_case
    text=(
        'Berita Acara Pemeriksaan Tersangka dalam dugaan Tindak Pidana Korupsi pada Perumda BPR. '
        'Direktur Utama menyetujui fasilitas kredit setelah ditemukan penyimpangan prosedur, analisa 5C, '
        'isu penyalahgunaan kewenangan dan kerugian keuangan daerah. Dokumen juga memuat Perjanjian Kredit.'
    )
    c=classify_case(text)
    assert c['posture']=='PIDANA_KHUSUS_PENYIDIKAN'
    assert c['primary_domain']=='corruption'
    assert {'financial_services','criminal','regional_government'}.issubset(set(c['domain_contract']))
    assert 'civil_contract' in c['supporting_only']


def test_case_posture_pure_credit_default_stays_civil_or_financial_not_tipikor():
    from services.case_domain_classifier import classify_case
    text=(
        'Bank swasta menagih debitur berdasarkan perjanjian kredit. Debitur menunggak delapan bulan dan telah disomasi. '
        'Tidak ada penyidikan, tidak ada fraud internal, tidak ada penyalahgunaan kewenangan, dan tidak ada kerugian keuangan negara.'
    )
    c=classify_case(text)
    assert c['primary_domain'] in {'civil_contract','financial_services'}
    assert c['primary_domain']!='corruption'


def test_case_posture_land_pleading_contract_excludes_banking_criminal():
    from services.case_domain_classifier import classify_case
    text=(
        'Jawaban Tergugat atas Gugatan Perbuatan Melawan Hukum. Diajukan eksepsi obscuur libel, plurium litis consortium, '
        'kompetensi absolut Pengadilan Agama, Sertipikat Hak Milik, Surat Ukur, SKPT dan riwayat pendaftaran tanah.'
    )
    c=classify_case(text)
    active=set(c['domain_contract'])
    assert c['primary_domain'] in {'civil_procedure','land_property','religious_court'}
    assert 'financial_services' not in active
    assert 'criminal' not in active


def test_persistent_regulatory_corpus_schema_and_sync():
    from database import init_database, RegulatoryCorpusManager, SCHEMA_VERSION
    result=init_database()
    assert SCHEMA_VERSION >= 4
    assert result['schema_version'] == SCHEMA_VERSION
    rows=RegulatoryCorpusManager.all(500)
    assert len(rows) >= 39
    assert any(r.get('id')=='uu_keuangan_negara_17_2003' for r in rows)
    assert any(r.get('id')=='pp_bumd_54_2017' for r in rows)


def test_offline_case_retrieval_uses_sqlite_corpus():
    from database import init_database
    from services.regulatory_retrieval import retrieve_for_case_dynamic
    init_database()
    text=(
        'Berita Acara Pemeriksaan Tersangka dugaan tindak pidana korupsi dalam pemberian fasilitas kredit Perumda BPR. '
        'Direktur Utama, komite kredit, prinsip kehati-hatian, penyalahgunaan kewenangan dan kerugian keuangan daerah tahun 2022.'
    )
    p=retrieve_for_case_dynamic(text=text,title='BAP BPR',provision_refs=[],qualified_queries=[],local_seed_matches=[],retrieval_mode='offline')
    assert p['retrieval_mode']=='offline'
    assert p['local_database_count'] > 0
    titles=' '.join((x.get('regulation') or {}).get('tentang','') for x in p['local_database_results']).lower()
    assert any(k in titles for k in ('korupsi','perbankan','bank perkreditan','bank perekonomian','keuangan negara','badan usaha milik daerah'))
    assert 'ketenagakerjaan' not in titles


def test_land_litigation_offline_corpus_excludes_arbitration_without_arbitration_issue():
    from database import init_database
    from services.regulatory_retrieval import retrieve_for_case_dynamic
    init_database()
    text=(
        'Jawaban Tergugat atas Gugatan Penggugat. Eksepsi obscuur libel dan plurium litis consortium. '
        'Sengketa mengenai Sertipikat Hak Milik, SKPT, Surat Ukur dan kompetensi absolut Pengadilan Agama.'
    )
    p=retrieve_for_case_dynamic(text=text,title='Tanah',provision_refs=[],qualified_queries=[],local_seed_matches=[],retrieval_mode='offline')
    titles=' '.join((x.get('regulation') or {}).get('tentang','') for x in p['local_database_results']).lower()
    assert 'arbitrase' not in titles
    assert 'ketenagakerjaan' not in titles
    assert 'bank perkreditan rakyat' not in titles and 'bank perekonomian rakyat' not in titles


def test_tempus_uses_procedural_date_for_kuhap_but_material_date_for_substantive_norms():
    from exporters.common import _tempus_status
    snap={'event_date_candidate':'2022-09-27','procedural_date_candidate':'2026-05-21','event_year_candidate':2022}
    kuhap={'nomor':'UU No. 20 Tahun 2025 / KUHAP','tentang':'Kitab Undang-Undang Hukum Acara Pidana','effective_date':'2026-01-02','domain_tags':['acara pidana']}
    kuhp={'nomor':'UU No. 1 Tahun 2023','tentang':'Kitab Undang-Undang Hukum Pidana','effective_date':'2026-01-02','domain_tags':['pidana materiil']}
    assert _tempus_status(kuhap,snap) == ('POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE','PROCEDURAL_DATE')
    assert _tempus_status(kuhp,snap) == ('POST_TEMPUS_REQUIRES_TRANSITIONAL_ANALYSIS','MATERIAL_EVENT_DATE')


def test_case_metadata_columns_are_migration_managed():
    expected={name for name,_ in EXPECTED_COLUMNS['case_analyses']}
    for col in ('case_posture','domain_classification','analysis_provenance','case_readiness'):
        assert col in expected


def test_ptun_and_investment_domain_boundaries():
    from services.case_domain_classifier import classify_case
    ptun=classify_case('Gugatan PTUN terhadap Keputusan Tata Usaha Negara setelah upaya administratif dengan dalil AUPB.')
    assert ptun['primary_domain']=='administrative'
    inv=classify_case('Perselisihan penanaman modal terkait investor dan perizinan berusaha, tanpa perkara pidana.')
    assert inv['primary_domain']=='investment'


def test_regulatory_corpus_has_expanded_procedure_and_advisory_coverage():
    from regulatory_db import get_all_regulations
    ids={r['id'] for r in get_all_regulations()}
    for rid in ('perma_mediasi_1_2016','perma_gugatan_sederhana_4_2019','inpres_khi_1_1991','uu_kip_14_2008','uu_penanaman_modal_25_2007','perma_e_court_7_2022'):
        assert rid in ids
