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
    def fake_search(query, direct_ids=(), per_source_limit=4):
        calls.append((query, tuple(direct_ids)))
        return [{
            'source_id':'kemnaker','source_name':'JDIH Kementerian Ketenagakerjaan',
            'authoritative':True,'reachable':True,'http_status':200,
            'results':[{'title':'PP 35 Tahun 2021 - PHK dan PKWT','url':'https://jdih.kemnaker.go.id/peraturan/test','score':8}],
        }]
    monkeypatch.setattr(rr,'federated_search',fake_search)
    text='Karyawan mengalami PHK tanpa pesangon setelah bekerja dengan PKWT dan meminta hak ketenagakerjaan.'
    payload=rr.retrieve_for_case_dynamic(text=text,title='Sengketa PHK',provision_refs=[],qualified_queries=[],local_seed_matches=[],online=True)
    assert payload['mode']=='DYNAMIC_CASE_SCOPED'
    assert payload['official_results_count'] >= 1
    assert any(d['id']=='employment' for d in payload['domains'])
    assert calls and any('kemnaker' in ids for _,ids in calls)
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
    assert domains[0]['id'] == 'financial_services'
    assert any(d['id'] == 'corruption' for d in domains[:3])
    civil = next((d for d in domains if d['id'] == 'civil_contract'), None)
    assert not civil or civil['confidence'] < domains[0]['confidence']
    queries = rr.build_case_queries(text, 'BAP Kredit BPR', provision_refs=['Pasal 603'], domains=domains,
                                    qualified_queries=['Perdata & Perikatan perjanjian utang piutang'])
    assert any('BPR' in q and ('tata kelola' in q or 'risiko' in q or 'kredit' in q) for q in queries)
    assert not any(q.lower().startswith('perdata & perikatan') for q in queries)
    assert any('tempus delicti 2022' in q for q in queries)


def test_retrieval_funnel_filters_post_event_results(monkeypatch):
    import services.regulatory_retrieval as rr
    def fake_search(query, direct_ids=(), per_source_limit=4):
        return [{
            'source_id':'ojk','source_name':'OJK','authoritative':True,'reachable':True,'http_status':200,
            'results':[
                {'title':'POJK No. 4 Tahun 2015 Tata Kelola BPR','url':'https://ojk.go.id/2015','score':8},
                {'title':'POJK No. 9 Tahun 2024 Tata Kelola BPR','url':'https://ojk.go.id/2024','score':8},
            ],
        }]
    monkeypatch.setattr(rr, 'federated_search', fake_search)
    p = rr.retrieve_for_case_dynamic(
        text='Direksi Perumda BPR menyetujui kredit pada tahun 2022 dengan isu tata kelola dan manajemen risiko.',
        title='Kredit BPR', online=True, provision_refs=[], qualified_queries=[], local_seed_matches=[])
    assert p['event_year_candidate'] == 2022
    assert p['retrieval_funnel']['materially_relevant'] >= 1
    assert any(r['temporal_status'] == 'POST_EVENT_REFERENCE' for b in p['search_bundles'] for s in b['sources'] for r in s['results'] if '2024' in r['title'])
    assert p['retrieval_funnel']['temporal_not_excluded'] <= p['retrieval_funnel']['materially_relevant']
