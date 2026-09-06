import os
import sqlite3

import ai_engine
import database


def test_missing_gemini_key_is_explicit_configuration_error(monkeypatch):
    monkeypatch.setenv('LEXICORE_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('LEXICORE_AI_MODEL', 'gemini-3.6-flash')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    diag = ai_engine.configuration_diagnostics()
    assert diag['configuration_valid'] is False
    assert diag['configuration_error'] == 'MISSING_GEMINI_API_KEY'
    assert diag['remote_ai_available'] is False
    assert ai_engine.is_available() is False


def test_legal_chunking_respects_estimated_token_budget(monkeypatch):
    text = ('PASAL 1\n' + ('ketentuan hukum dan pembuktian ' * 900) + '\n\n'
            'PASAL 2\n' + ('tempus delicti dan pertanggungjawaban ' * 900))
    chunks = ai_engine._chunks(text)
    assert chunks
    assert len(chunks) <= ai_engine.MAX_CHUNKS
    assert all(ai_engine._estimate_tokens(c) <= ai_engine.MAX_INPUT_TOKENS_PER_CHUNK * 1.08 for c in chunks)


def test_synthesis_evidence_is_deduplicated_and_budgeted():
    maps = []
    for i in range(24):
        maps.append({
            '_segment': i + 1,
            'facts': [{'statement': 'fakta yang sama', 'evidence': 'kutipan yang sama'}] * 8,
            'allegations': [{'statement': 'dugaan ' + ('x' * 500), 'evidence': 'y' * 500}] * 8,
            'legal_refs': ['Pasal 3 UU Tipikor'] * 8,
        })
    compact = ai_engine._compact_evidence_maps(maps)
    serialized = ai_engine.json.dumps(compact, ensure_ascii=False)
    assert ai_engine._estimate_tokens(serialized) <= ai_engine.SYNTHESIS_TOKEN_BUDGET
    # Global deduplication means repeated identical facts/refs do not balloon synthesis.
    facts = sum(len(m.get('facts', [])) for m in compact)
    refs = sum(len(m.get('legal_refs', [])) for m in compact)
    assert facts <= 1
    assert refs <= 1


def test_db_session_rolls_back_and_closes_on_exception(tmp_path, monkeypatch):
    db_path = tmp_path / 'test.db'

    def local_conn():
        conn = sqlite3.connect(str(db_path))
        conn.execute('CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, value TEXT)')
        conn.commit()
        return conn

    monkeypatch.setattr(database, 'get_db_connection', local_conn)
    captured = None
    try:
        with database.db_session(write=True) as conn:
            captured = conn
            conn.execute("INSERT INTO t(value) VALUES ('x')")
            raise RuntimeError('boom')
    except RuntimeError:
        pass

    # Transaction was rolled back.
    check = sqlite3.connect(str(db_path))
    assert check.execute('SELECT COUNT(*) FROM t').fetchone()[0] == 0
    check.close()
    # And the original connection is deterministically closed.
    try:
        captured.execute('SELECT 1')
        closed = False
    except sqlite3.ProgrammingError:
        closed = True
    assert closed is True
