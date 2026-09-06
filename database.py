"""LexiCore database layer (SQLite) with versioned, idempotent migrations."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

from services.backup_service import create_database_backup, ensure_daily_backup, prune_backups

BASE_DIR = Path(__file__).resolve().parent
_raw_db_path = os.environ.get("LEXICORE_DB_PATH", "lexicore.db")
DB_PATH = str((BASE_DIR / _raw_db_path).resolve()) if not os.path.isabs(_raw_db_path) else str(Path(_raw_db_path).resolve())
SCHEMA_VERSION = 10

# Every table column expected by the current application lives here.  When a
# future release adds a column, add it to this map.  Startup validation will
# detect the missing column, create a backup, and add it idempotently.
EXPECTED_COLUMNS = {
    "drafts": [
        ("id", "INTEGER"), ("title", "TEXT"), ("doc_type", "TEXT"), ("party1", "TEXT"),
        ("party2", "TEXT"), ("effective_date", "TEXT"), ("duration", "INTEGER"),
        ("content", "TEXT"), ("word_count", "INTEGER"), ("clause_count", "INTEGER"),
        ("status", "TEXT DEFAULT 'draft'"), ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "contract_analyses": [
        ("id", "INTEGER"), ("filename", "TEXT"), ("file_path", "TEXT"), ("total_pages", "INTEGER"),
        ("word_count", "INTEGER"), ("parties", "TEXT"), ("effective_date", "TEXT"),
        ("termination_date", "TEXT"), ("risks", "TEXT"), ("summary", "TEXT"),
        ("risk_score", "TEXT"), ("review_payload", "TEXT"), ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "legal_research": [
        ("id", "INTEGER"), ("title", "TEXT"), ("jurisdiction", "TEXT"), ("citation", "TEXT"),
        ("source_type", "TEXT"), ("source_text", "TEXT"), ("issue", "TEXT"), ("holding", "TEXT"),
        ("reasoning", "TEXT"), ("keywords", "TEXT"), ("research_payload", "TEXT"), ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "risk_assessments": [
        ("id", "INTEGER"), ("title", "TEXT"), ("entity", "TEXT"), ("category", "TEXT"),
        ("answers", "TEXT"), ("score", "INTEGER"), ("risk_level", "TEXT"), ("findings", "TEXT"),
        ("recommendations", "TEXT"), ("assessment_payload", "TEXT"), ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "client_communications": [
        ("id", "INTEGER"), ("draft_id", "INTEGER"), ("client_id", "TEXT"),
        ("client_name", "TEXT"), ("client_email", "TEXT"), ("whatsapp_number", "TEXT"),
        ("subject", "TEXT"), ("message", "TEXT"), ("document_type", "TEXT"),
        ("status", "TEXT DEFAULT 'draft'"), ("sent_at", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "case_analyses": [
        ("id", "INTEGER"), ("title", "TEXT"), ("input_type", "TEXT"), ("filename", "TEXT"),
        ("source_text", "TEXT"), ("facts", "TEXT"), ("legal_issues", "TEXT"),
        ("applicable_law", "TEXT"), ("legal_analysis", "TEXT"), ("arguments_for", "TEXT"),
        ("arguments_against", "TEXT"), ("evidence_needed", "TEXT"), ("risks", "TEXT"),
        ("recommendations", "TEXT"), ("coverage_note", "TEXT"),
        ("case_posture", "TEXT"), ("domain_classification", "TEXT"),
        ("analysis_provenance", "TEXT"), ("case_readiness", "TEXT"), ("case_working_paper", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "legal_source_verifications": [
        ("id", "INTEGER"), ("case_analysis_id", "INTEGER"), ("status", "TEXT"), ("checked_at", "TEXT"),
        ("query_bundle", "TEXT"), ("source_health", "TEXT"), ("results_count", "INTEGER DEFAULT 0"),
        ("professional_status", "TEXT DEFAULT 'PENDING'"), ("professional_notes", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "audit_log": [
        ("id", "INTEGER"), ("action", "TEXT"), ("entity_type", "TEXT"), ("entity_id", "INTEGER"),
        ("details", "TEXT"), ("user", "TEXT DEFAULT 'system'"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "case_regulatory_snapshots": [
        ("id", "INTEGER"), ("case_analysis_id", "INTEGER"), ("mode", "TEXT"),
        ("domains", "TEXT"), ("queries", "TEXT"), ("official_results", "TEXT"),
        ("local_seed_count", "INTEGER DEFAULT 0"), ("official_results_count", "INTEGER DEFAULT 0"),
        ("source_ids", "TEXT"), ("content_hash", "TEXT"), ("fetched_at", "TEXT"),
        ("professional_status", "TEXT DEFAULT 'PENDING'"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "regulatory_corpus": [
        ("id", "TEXT"), ("nomor", "TEXT"), ("tahun", "INTEGER"), ("tentang", "TEXT"),
        ("jenis", "TEXT"), ("hierarchy_rank", "INTEGER"), ("status", "TEXT"),
        ("effective_date", "TEXT"), ("promulgation_date", "TEXT"), ("jdih_source", "TEXT"),
        ("official_url", "TEXT"), ("domain_tags", "TEXT"), ("articles", "TEXT"),
        ("metadata", "TEXT"), ("source", "TEXT DEFAULT 'BUILTIN_SEED'"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def db_session(*, write: bool = False):
    """Short-lived SQLite session with guaranteed rollback and close."""
    conn = get_db_connection()
    try:
        yield conn
        if write:
            conn.commit()
    except Exception:
        if write:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        conn.close()


def _create_tables(conn):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, doc_type TEXT NOT NULL,
        party1 TEXT, party2 TEXT, effective_date TEXT, duration INTEGER, content TEXT NOT NULL,
        word_count INTEGER, clause_count INTEGER, status TEXT DEFAULT 'draft',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS contract_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL, file_path TEXT,
        total_pages INTEGER, word_count INTEGER, parties TEXT, effective_date TEXT,
        termination_date TEXT, risks TEXT, summary TEXT, risk_score TEXT, review_payload TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS legal_research (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, jurisdiction TEXT,
        citation TEXT, source_type TEXT, source_text TEXT, issue TEXT, holding TEXT,
        reasoning TEXT, keywords TEXT, research_payload TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS risk_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, entity TEXT,
        category TEXT, answers TEXT, score INTEGER, risk_level TEXT, findings TEXT,
        recommendations TEXT, assessment_payload TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS client_communications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, draft_id INTEGER, client_id TEXT, client_name TEXT,
        client_email TEXT, whatsapp_number TEXT, subject TEXT, message TEXT, document_type TEXT,
        status TEXT DEFAULT 'draft', sent_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (draft_id) REFERENCES drafts(id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS case_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, input_type TEXT, filename TEXT,
        source_text TEXT NOT NULL, facts TEXT, legal_issues TEXT, applicable_law TEXT,
        legal_analysis TEXT, arguments_for TEXT, arguments_against TEXT, evidence_needed TEXT,
        risks TEXT, recommendations TEXT, coverage_note TEXT,
        case_posture TEXT, domain_classification TEXT, analysis_provenance TEXT, case_readiness TEXT, case_working_paper TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS legal_source_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_analysis_id INTEGER, status TEXT, checked_at TEXT,
        query_bundle TEXT, source_health TEXT, results_count INTEGER DEFAULT 0,
        professional_status TEXT DEFAULT 'PENDING', professional_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (case_analysis_id) REFERENCES case_analyses(id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity_type TEXT,
        entity_id INTEGER, details TEXT, user TEXT DEFAULT 'system',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS case_regulatory_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_analysis_id INTEGER NOT NULL, mode TEXT,
        domains TEXT, queries TEXT, official_results TEXT, local_seed_count INTEGER DEFAULT 0,
        official_results_count INTEGER DEFAULT 0, source_ids TEXT, content_hash TEXT, fetched_at TEXT,
        professional_status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (case_analysis_id) REFERENCES case_analyses(id))""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_case_regulatory_snapshots_case ON case_regulatory_snapshots(case_analysis_id)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS regulatory_corpus (
        id TEXT PRIMARY KEY, nomor TEXT, tahun INTEGER, tentang TEXT, jenis TEXT,
        hierarchy_rank INTEGER, status TEXT, effective_date TEXT, promulgation_date TEXT,
        jdih_source TEXT, official_url TEXT, domain_tags TEXT, articles TEXT, metadata TEXT,
        source TEXT DEFAULT 'BUILTIN_SEED', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_regulatory_corpus_year ON regulatory_corpus(tahun)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_regulatory_corpus_kind ON regulatory_corpus(jenis)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()


def _existing_columns(conn, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def schema_drift(conn) -> Dict[str, List[str]]:
    drift: Dict[str, List[str]] = {}
    for table, expected in EXPECTED_COLUMNS.items():
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not row:
            drift[table] = [name for name, _ in expected]
            continue
        existing = _existing_columns(conn, table)
        missing = [name for name, _ in expected if name not in existing]
        if missing:
            drift[table] = missing
    return drift


def _schema_version(conn) -> int:
    try:
        row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def _set_schema_version(conn, version: int):
    conn.execute("""INSERT INTO schema_meta(key,value,updated_at) VALUES('schema_version',?,CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""", (str(version),))


def _migrate_schema(conn):
    """Heal additive schema drift. Safe to re-run on every startup."""
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    changed = []
    for table, expected in EXPECTED_COLUMNS.items():
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not row:
            continue
        existing = _existing_columns(conn, table)
        for column, decl in expected:
            if column == "id" or column in existing:
                continue
            # SQLite ALTER TABLE rejects non-constant defaults such as
            # CURRENT_TIMESTAMP on some versions. Add a migration-safe shape,
            # then backfill existing rows; CREATE TABLE still keeps the default
            # for newly created databases.
            alter_decl = decl
            needs_timestamp_backfill = "CURRENT_TIMESTAMP" in decl.upper()
            if needs_timestamp_backfill:
                alter_decl = decl.upper().replace(" DEFAULT CURRENT_TIMESTAMP", "")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {alter_decl}")
            if needs_timestamp_backfill:
                conn.execute(f"UPDATE {table} SET {column}=CURRENT_TIMESTAMP WHERE {column} IS NULL")
            changed.append(f"{table}.{column}")
    _set_schema_version(conn, SCHEMA_VERSION)
    conn.commit()
    return changed


def validate_schema(conn) -> Dict[str, List[str]]:
    drift = schema_drift(conn)
    if drift:
        raise RuntimeError(f"LexiCore database schema drift remains after migration: {drift}")
    return drift


def init_database():
    # First create missing tables. Then inspect the shape of existing tables.
    with db_session(write=True) as conn:
        _create_tables(conn)
        drift = schema_drift(conn)
        current_version = _schema_version(conn)

    # A restore point is created before any ALTER TABLE operation.  Test DBs
    # can opt out via LEXICORE_DISABLE_AUTO_BACKUP=1.
    if (drift or current_version < SCHEMA_VERSION) and os.environ.get("LEXICORE_DISABLE_AUTO_BACKUP") != "1":
        create_database_backup(DB_PATH, reason=f"pre_migration_v{current_version}_to_v{SCHEMA_VERSION}")

    with db_session(write=True) as conn:
        _create_tables(conn)
        changed = _migrate_schema(conn)
        validate_schema(conn)
    if os.environ.get("LEXICORE_DISABLE_AUTO_BACKUP") != "1":
        if os.environ.get("LEXICORE_AUTO_BACKUP_DAILY", "1") != "0":
            ensure_daily_backup(DB_PATH)
        prune_backups(DB_PATH, keep=int(os.environ.get("LEXICORE_BACKUP_KEEP", "30")))
    try:
        from regulatory_db import get_all_regulations
        RegulatoryCorpusManager.sync_seed(get_all_regulations())
    except Exception as exc:
        try:
            AuditLogger.log_action('regulatory_seed_sync_error','regulatory_corpus',None,str(exc)[:300])
        except Exception:
            pass
    return {"schema_version": SCHEMA_VERSION, "migrated_columns": changed}


class DraftManager:
    @staticmethod
    def create_draft(data: Dict) -> int:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('''INSERT INTO drafts
            (title,doc_type,party1,party2,effective_date,duration,content,word_count,clause_count,status)
            VALUES (?,?,?,?,?,?,?,?,?,?)''', (
            data.get('title','Untitled Draft'), data.get('doc_type','general'), data.get('party1',''),
            data.get('party2',''), data.get('effective_date',''), data.get('duration',0),
            data.get('content',''), data.get('word_count',0), data.get('clause_count',0), data.get('status','draft')))
        draft_id = cur.lastrowid; conn.commit(); conn.close()
        AuditLogger.log_action('create_draft','draft',draft_id,f'Created draft: {data.get("title","")}')
        return draft_id

    @staticmethod
    def get_all_drafts(limit: int=50) -> List[Dict]:
        conn=get_db_connection(); rows=conn.execute('SELECT * FROM drafts ORDER BY updated_at DESC LIMIT ?', (limit,)).fetchall(); conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_draft(draft_id:int)->Optional[Dict]:
        conn=get_db_connection(); row=conn.execute('SELECT * FROM drafts WHERE id=?',(draft_id,)).fetchone(); conn.close(); return dict(row) if row else None

    @staticmethod
    def update_draft(draft_id:int,data:Dict)->bool:
        conn=get_db_connection(); cur=conn.cursor(); cur.execute('''UPDATE drafts SET title=?, content=?, word_count=?, clause_count=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?''',(
            data.get('title','Untitled Draft'),data.get('content',''),data.get('word_count',0),data.get('clause_count',0),data.get('status','draft'),draft_id))
        ok=cur.rowcount>0; conn.commit(); conn.close()
        if ok: AuditLogger.log_action('update_draft','draft',draft_id,'Updated draft')
        return ok

    @staticmethod
    def delete_draft(draft_id:int)->bool:
        conn=get_db_connection(); cur=conn.cursor(); cur.execute('DELETE FROM drafts WHERE id=?',(draft_id,)); ok=cur.rowcount>0; conn.commit(); conn.close()
        if ok: AuditLogger.log_action('delete_draft','draft',draft_id,'Deleted draft')
        return ok


class AnalysisManager:
    @staticmethod
    def save_analysis(data:Dict)->int:
        conn=get_db_connection(); cur=conn.cursor(); cur.execute('''INSERT INTO contract_analyses
        (filename,file_path,total_pages,word_count,parties,effective_date,termination_date,risks,summary,risk_score,review_payload)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',(
            data.get('filename',''),data.get('file_path',''),data.get('total_pages',0),data.get('word_count',0),
            json.dumps(data.get('parties',[]),ensure_ascii=False),data.get('effective_date',''),data.get('termination_date',''),
            json.dumps(data.get('risks',[]),ensure_ascii=False),data.get('summary',''),data.get('risk_score','LOW'),
            json.dumps(data,ensure_ascii=False)))
        i=cur.lastrowid; conn.commit(); conn.close(); AuditLogger.log_action('save_analysis','analysis',i,f'Analyzed: {data.get("filename","")}'); return i

    @staticmethod
    def get_all_analyses(limit:int=50)->List[Dict]:
        conn=get_db_connection(); rows=conn.execute('SELECT * FROM contract_analyses ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall(); conn.close(); out=[]
        for r in rows:
            d=dict(r); d['parties']=json.loads(d['parties'] or '[]'); d['risks']=json.loads(d['risks'] or '[]');
            try:
                payload=json.loads(d.get('review_payload') or '{}')
                if isinstance(payload,dict) and payload:
                    payload.update({'id':d.get('id'),'created_at':d.get('created_at'),'risk_score':d.get('risk_score') or payload.get('risk_score')})
                    d=payload
            except Exception:
                pass
            out.append(d)
        return out


class ResearchManager:
    @staticmethod
    def save(data:Dict)->int:
        conn=get_db_connection(); cur=conn.cursor(); cur.execute('''INSERT INTO legal_research
        (title,jurisdiction,citation,source_type,source_text,issue,holding,reasoning,keywords,research_payload) VALUES (?,?,?,?,?,?,?,?,?,?)''',(
            data.get('title','Untitled Research'),data.get('jurisdiction','Indonesia'),data.get('citation',''),data.get('source_type','case'),
            data.get('source_text',''),data.get('issue',''),data.get('holding',''),data.get('reasoning',''),json.dumps(data.get('keywords',[]),ensure_ascii=False),
            json.dumps(data.get('research_payload') or {},ensure_ascii=False)))
        i=cur.lastrowid; conn.commit(); conn.close(); AuditLogger.log_action('save_research','research',i,data.get('title','')); return i

    @staticmethod
    def all(limit:int=50)->List[Dict]:
        conn=get_db_connection(); rows=conn.execute('SELECT * FROM legal_research ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall(); conn.close(); out=[]
        for r in rows:
            d=dict(r); d['keywords']=json.loads(d['keywords'] or '[]');
            try: d['research_payload']=json.loads(d.get('research_payload') or '{}')
            except Exception: d['research_payload']={}
            out.append(d)
        return out


class RiskAssessmentManager:
    @staticmethod
    def save(data:Dict)->int:
        conn=get_db_connection(); cur=conn.cursor(); cur.execute('''INSERT INTO risk_assessments
        (title,entity,category,answers,score,risk_level,findings,recommendations,assessment_payload) VALUES (?,?,?,?,?,?,?,?,?)''',(
            data.get('title','Risk Assessment'),data.get('entity',''),data.get('category','General'),json.dumps(data.get('answers',{}),ensure_ascii=False),
            data.get('score',0),data.get('risk_level','LOW'),json.dumps(data.get('findings',[]),ensure_ascii=False),json.dumps(data.get('recommendations',[]),ensure_ascii=False),json.dumps(data,ensure_ascii=False)))
        i=cur.lastrowid; conn.commit(); conn.close(); AuditLogger.log_action('save_risk_assessment','risk_assessment',i,data.get('title','')); return i

    @staticmethod
    def all(limit:int=50)->List[Dict]:
        conn=get_db_connection(); rows=conn.execute('SELECT * FROM risk_assessments ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall(); conn.close(); out=[]
        for r in rows:
            d=dict(r); d['answers']=json.loads(d['answers'] or '{}'); d['findings']=json.loads(d['findings'] or '[]'); d['recommendations']=json.loads(d['recommendations'] or '[]');
            try:
                payload=json.loads(d.get('assessment_payload') or '{}')
                if isinstance(payload,dict) and payload:
                    payload.update({'id':d.get('id'),'created_at':d.get('created_at')})
                    d=payload
            except Exception:
                pass
            out.append(d)
        return out


class CaseAnalysisManager:
    @staticmethod
    def save(data:Dict)->int:
        with db_session(write=True) as conn:
            cur=conn.cursor(); cur.execute('''INSERT INTO case_analyses
        (title,input_type,filename,source_text,facts,legal_issues,applicable_law,legal_analysis,arguments_for,arguments_against,evidence_needed,risks,recommendations,coverage_note,case_posture,domain_classification,analysis_provenance,case_readiness,case_working_paper)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                data.get('title','Case Analysis'),data.get('input_type','narrative'),data.get('filename',''),data.get('source_text',''),
                json.dumps(data.get('facts',[]),ensure_ascii=False),json.dumps(data.get('legal_issues',[]),ensure_ascii=False),
                json.dumps(data.get('applicable_law',[]),ensure_ascii=False),data.get('legal_analysis',''),
                json.dumps(data.get('arguments_for',[]),ensure_ascii=False),json.dumps(data.get('arguments_against',[]),ensure_ascii=False),
                json.dumps(data.get('evidence_needed',[]),ensure_ascii=False),json.dumps(data.get('risks',[]),ensure_ascii=False),
                json.dumps(data.get('recommendations',[]),ensure_ascii=False),data.get('coverage_note',''),data.get('case_posture',''),
                json.dumps(data.get('domain_classification',{}),ensure_ascii=False),json.dumps(data.get('analysis_provenance',{}),ensure_ascii=False),
                json.dumps(data.get('case_readiness',{}),ensure_ascii=False),
                json.dumps(data.get('case_working_paper',{}),ensure_ascii=False)))
            i=cur.lastrowid
        AuditLogger.log_action('save_case_analysis','case_analysis',i,data.get('title',''))
        return i

    @staticmethod
    def all(limit:int=50)->List[Dict]:
        with db_session() as conn:
            rows=conn.execute('SELECT * FROM case_analyses ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            for k in ('facts','legal_issues','applicable_law','arguments_for','arguments_against','evidence_needed','risks','recommendations'):
                try: d[k]=json.loads(d.get(k) or '[]')
                except Exception: d[k]=[]
            for k in ('domain_classification','analysis_provenance','case_readiness','case_working_paper'):
                try: d[k]=json.loads(d.get(k) or '{}')
                except Exception: d[k]={}
            out.append(d)
        return out


class LegalSourceVerificationManager:
    @staticmethod
    def save(case_analysis_id:int,data:Dict)->int:
        with db_session(write=True) as conn:
            cur=conn.cursor(); cur.execute('''INSERT INTO legal_source_verifications
        (case_analysis_id,status,checked_at,query_bundle,source_health,results_count,professional_status)
        VALUES (?,?,?,?,?,?,?)''', (case_analysis_id,data.get('status',''),data.get('checked_at',''),
                json.dumps(data.get('searches',[]),ensure_ascii=False),json.dumps(data.get('source_health',[]),ensure_ascii=False),
                (data.get('summary') or {}).get('results_found',0),data.get('professional_verification','PENDING')))
            i=cur.lastrowid
        AuditLogger.log_action('official_source_verification','case_analysis',case_analysis_id,data.get('status',''))
        return i

    @staticmethod
    def latest_for_case(case_analysis_id:int)->Optional[Dict]:
        with db_session() as conn:
            row=conn.execute('SELECT * FROM legal_source_verifications WHERE case_analysis_id=? ORDER BY created_at DESC LIMIT 1',(case_analysis_id,)).fetchone()
        if not row: return None
        d=dict(row); d['query_bundle']=json.loads(d.get('query_bundle') or '[]'); d['source_health']=json.loads(d.get('source_health') or '[]'); return d


class CommunicationManager:
    @staticmethod
    def save(data:Dict)->int:
        conn=get_db_connection(); cur=conn.cursor(); cur.execute('''INSERT INTO client_communications
        (draft_id,client_id,client_name,client_email,whatsapp_number,subject,message,document_type,status,sent_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',(
            data.get('draft_id'),data.get('client_id',''),data.get('client_name',''),data.get('client_email',''),data.get('whatsapp_number',''),
            data.get('subject',''),data.get('message',''),data.get('document_type','client_update'),data.get('status','draft'),
            datetime.now().isoformat() if data.get('status')=='sent' else None))
        i=cur.lastrowid; conn.commit(); conn.close(); AuditLogger.log_action('save_communication','communication',i,data.get('subject','')); return i

    @staticmethod
    def all(limit:int=50)->List[Dict]:
        conn=get_db_connection(); rows=conn.execute('SELECT * FROM client_communications ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall(); conn.close(); return [dict(r) for r in rows]

    @staticmethod
    def contact_by_client_id(client_id:str)->Optional[Dict]:
        client_id=(client_id or '').strip()
        if not client_id: return None
        conn=get_db_connection(); row=conn.execute(
            "SELECT client_id,client_name,client_email,whatsapp_number FROM client_communications WHERE client_id=? AND COALESCE(whatsapp_number,'')<>'' ORDER BY created_at DESC LIMIT 1",
            (client_id,)
        ).fetchone(); conn.close(); return dict(row) if row else None


class CaseRegulatorySnapshotManager:
    """Persist compact metadata-only regulatory retrieval snapshots per case."""

    @staticmethod
    def save(case_analysis_id: int, payload: Dict) -> int:
        conn = get_db_connection(); cur = conn.cursor()
        sql = ("INSERT INTO case_regulatory_snapshots "
               "(case_analysis_id,mode,domains,queries,official_results,local_seed_count,official_results_count,source_ids,content_hash,fetched_at,professional_status) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?)")
        cur.execute(sql, (
            case_analysis_id, payload.get('mode',''),
            json.dumps(payload.get('domains',[]),ensure_ascii=False),
            json.dumps(payload.get('queries',[]),ensure_ascii=False),
            json.dumps(payload.get('official_results',[]),ensure_ascii=False),
            int(payload.get('local_seed_count',0) or 0), int(payload.get('official_results_count',0) or 0),
            json.dumps(payload.get('official_source_ids',[]),ensure_ascii=False),
            payload.get('content_hash',''), payload.get('fetched_at',''), payload.get('professional_verification','PENDING')
        ))
        i = cur.lastrowid; conn.commit(); conn.close()
        AuditLogger.log_action('case_regulatory_snapshot','case_analysis',case_analysis_id,
            f"mode={payload.get('mode')} | official={payload.get('official_results_count',0)} | seed={payload.get('local_seed_count',0)}")
        return i

    @staticmethod
    def latest(case_analysis_id: int) -> Optional[Dict]:
        conn=get_db_connection()
        row=conn.execute('SELECT * FROM case_regulatory_snapshots WHERE case_analysis_id=? ORDER BY id DESC LIMIT 1',(case_analysis_id,)).fetchone()
        conn.close()
        if not row:
            return None
        d=dict(row)
        for key in ('domains','queries','official_results','source_ids'):
            try:
                d[key]=json.loads(d.get(key) or '[]')
            except Exception:
                d[key]=[]
        return d


class RegulatoryCorpusManager:
    """Persistent local corpus used for OFFLINE and HYBRID research modes."""

    @staticmethod
    def sync_seed(regulations: List[Dict]) -> int:
        conn=get_db_connection(); cur=conn.cursor(); count=0
        sql=("INSERT INTO regulatory_corpus "
             "(id,nomor,tahun,tentang,jenis,hierarchy_rank,status,effective_date,promulgation_date,jdih_source,official_url,domain_tags,articles,metadata,source,updated_at) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) "
             "ON CONFLICT(id) DO UPDATE SET nomor=excluded.nomor,tahun=excluded.tahun,tentang=excluded.tentang,jenis=excluded.jenis,"
             "hierarchy_rank=excluded.hierarchy_rank,status=excluded.status,effective_date=excluded.effective_date,"
             "promulgation_date=excluded.promulgation_date,jdih_source=excluded.jdih_source,official_url=excluded.official_url,"
             "domain_tags=excluded.domain_tags,articles=excluded.articles,metadata=excluded.metadata,updated_at=CURRENT_TIMESTAMP")
        for reg in regulations or []:
            rid=str(reg.get('id') or '').strip()
            if not rid: continue
            metadata={k:v for k,v in reg.items() if k not in ('domain_tags','articles')}
            cur.execute(sql,(
                rid,reg.get('nomor',''),reg.get('tahun'),reg.get('tentang',''),reg.get('jenis',''),reg.get('hierarchy_rank'),
                reg.get('status',''),reg.get('effective_date',''),reg.get('promulgation_date',''),reg.get('jdih_source',''),
                reg.get('official_url',''),json.dumps(reg.get('domain_tags',[]),ensure_ascii=False),
                json.dumps(reg.get('articles',[]),ensure_ascii=False),json.dumps(metadata,ensure_ascii=False),reg.get('source','BUILTIN_SEED')))
            count += 1
        conn.commit(); conn.close(); return count

    @staticmethod
    def _decode(d:Dict)->Dict:
        for key,default in (('domain_tags',[]),('articles',[]),('metadata',{})):
            try:
                d[key]=json.loads(d.get(key) or ('{}' if isinstance(default,dict) else '[]'))
            except Exception:
                d[key]=default
        return d

    @staticmethod
    def all(limit:int=500)->List[Dict]:
        conn=get_db_connection(); rows=conn.execute('SELECT * FROM regulatory_corpus ORDER BY hierarchy_rank ASC, tahun DESC LIMIT ?',(limit,)).fetchall(); conn.close()
        return [RegulatoryCorpusManager._decode(dict(r)) for r in rows]

    @staticmethod
    def search(query:str, limit:int=12)->List[Dict]:
        q=(query or '').strip().lower(); rows=RegulatoryCorpusManager.all(1000)
        if not q: return rows[:limit]
        terms=[t for t in q.replace('/',' ').replace('-',' ').split() if len(t)>2]
        scored=[]
        for reg in rows:
            article_text=' '.join(' '.join([str(a.get('pasal','')),str(a.get('topic','')),str(a.get('content','')),' '.join(a.get('keywords',[]))]) for a in reg.get('articles',[]) if isinstance(a,dict))
            hay=' '.join([str(reg.get('nomor','')),str(reg.get('tentang','')),' '.join(reg.get('domain_tags',[])),article_text]).lower()
            title=(str(reg.get('tentang',''))+' '+str(reg.get('nomor',''))).lower()
            score=sum(9 if t in title else 3 for t in terms if t in hay)
            if q in hay: score += 15
            if score: scored.append((score,reg))
        scored.sort(key=lambda x:(x[0],x[1].get('tahun') or 0),reverse=True)
        return [r for _,r in scored[:max(1,limit)]]


class AuditLogger:
    @staticmethod
    def log_action(action:str,entity_type:str=None,entity_id:int=None,details:str=None):
        with db_session(write=True) as conn:
            conn.execute('INSERT INTO audit_log (action,entity_type,entity_id,details) VALUES (?,?,?,?)',(action,entity_type,entity_id,details))

    @staticmethod
    def get_recent_logs(limit:int=50)->List[Dict]:
        with db_session() as conn:
            rows=conn.execute('SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall()
        return [dict(r) for r in rows]


if __name__ == '__main__': init_database()
