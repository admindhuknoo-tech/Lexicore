"""LexiCore API smoke tests.

Hardened for the v1.3.4 stability baseline. Every bug found across
the v1.3.2 and v1.3.3 audits (stale client_communications schema, contract
party-extraction regex, PDF export silently dropping lines, redundant
Evidence-to-Action calls) was only caught by manually exercising every
endpoint by hand after the fact. This file automates that sweep so the same
class of regression is caught before a new zip ships, not after.

IMPORTANT — isolation from real data:
This suite points LEXICORE_DB_PATH at a throwaway SQLite file in a temp
directory (set *before* `app`/`database` are imported, since database.py
reads the env var once at import time). It never touches the firm's real
lexicore.db, and it deliberately exercises the destructive endpoints
(/api/history DELETE, purge-all) — which would be dangerous to run against
real client data.

Run with:
    py -m pip install pytest --break-system-packages   # if not installed
    py -m pytest test_smoke.py -v
"""
import os
import io
import json
import tempfile

# Must happen before importing app/database, since DB_PATH is read at import time.
_TMP_DIR = tempfile.mkdtemp(prefix="lexicore_test_")
os.environ["LEXICORE_DB_PATH"] = os.path.join(_TMP_DIR, "test_lexicore.db")
os.environ["LEXICORE_DISABLE_AUTO_BACKUP"] = "1"
os.environ["GEMINI_API_KEY"] = ""

import pytest
import app as appmod  # noqa: E402  (import must follow the env var above)
from contract_review import RiskDetector  # noqa: E402
from database import EXPECTED_COLUMNS, get_db_connection, SCHEMA_VERSION  # noqa: E402
from regulatory_db import get_all_regulations, search_regulations  # noqa: E402


@pytest.fixture()
def client():
    appmod.app.testing = True
    return appmod.app.test_client()


def post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _sample_docx_bytes(paragraphs):
    """Build a minimal real .docx in memory for upload-based endpoints."""
    from docx import Document
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio


# --------------------------------------------------------------------------
# Read-only / status endpoints
# --------------------------------------------------------------------------

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "online"


def test_ai_status(client):
    assert client.get("/api/ai/status").status_code == 200


def test_dashboard_metrics(client):
    r = client.get("/api/dashboard/metrics")
    assert r.status_code == 200
    assert "metrics" in r.get_json()


def test_regulations_catalog_and_search(client):
    assert client.get("/api/regulations/catalog").status_code == 200
    assert client.get("/api/regulations/search?q=korupsi").status_code == 200


def test_regulatory_intelligence_catalog_graph_timeline(client):
    assert client.get("/api/regulatory-intelligence/catalog").status_code == 200
    assert client.get("/api/regulatory-intelligence/graph?q=korupsi").status_code == 200
    assert client.get("/api/regulatory-intelligence/timeline?q=korupsi").status_code == 200


def test_legal_sources(client, monkeypatch):
    assert client.get("/api/legal-sources").status_code == 200
    # Release gate must be deterministic/offline: stub the external health
    # probe while still testing the Flask endpoint shape.
    monkeypatch.setattr(appmod, "source_health", lambda: [])
    r = client.get("/api/legal-sources/health")
    assert r.status_code == 200
    assert r.get_json()["count"] == 0


def test_audit_logs_empty_ok(client):
    assert client.get("/api/audit/logs").status_code == 200


# --------------------------------------------------------------------------
# Legal Drafting lifecycle: generate -> save -> get -> update -> export -> history
# --------------------------------------------------------------------------

def test_draft_lifecycle(client):
    r = post_json(client, "/api/generate/draft", {
        "doc_type": "Somasi", "party1": "PT A", "party2": "PT B",
        "effective_date": "2026-09-03", "duration": "", "prompt": "wanprestasi pembayaran",
    })
    assert r.status_code == 200
    content = r.get_json()["content"]
    assert len(content) > 50

    r = post_json(client, "/api/drafts", {
        "title": "Test Draft", "doc_type": "Somasi", "party1": "PT A", "party2": "PT B",
        "content": content, "word_count": len(content.split()), "clause_count": 1, "status": "saved",
    })
    assert r.status_code == 200
    draft_id = r.get_json()["draft_id"]
    assert draft_id

    assert client.get(f"/api/drafts/{draft_id}").status_code == 200

    r = client.put(f"/api/drafts/{draft_id}", data=json.dumps({"title": "Updated Title"}),
                    content_type="application/json")
    assert r.status_code == 200

    r = client.get(f"/api/drafts/{draft_id}/export/docx")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/vnd.openxmlformats")

    r = client.get(f"/api/history/drafts/{draft_id}")
    assert r.status_code == 200

    r = client.delete(f"/api/history/drafts/{draft_id}")
    assert r.status_code == 200
    assert client.get(f"/api/history/drafts/{draft_id}").status_code == 404


# --------------------------------------------------------------------------
# Contract Review — regression guard for the party-extraction bug
# --------------------------------------------------------------------------

def test_contract_review_party_extraction_does_not_pick_up_garbage(client):
    bio = _sample_docx_bytes([
        "PERJANJIAN KERJASAMA",
        "Pihak Pertama: PT Sumber Makmur, Pihak Kedua: Budi Santoso.",
        "Pihak Kedua wajib membayar denda sebesar Rp 50.000.000 apabila terjadi "
        "keterlambatan pembayaran lebih dari 30 hari.",
        "Pihak Pertama dapat mengakhiri perjanjian ini secara sepihak tanpa "
        "pemberitahuan sebelumnya.",
    ])
    r = client.post("/api/review", data={"file": (bio, "sample.docx")},
                     content_type="multipart/form-data")
    assert r.status_code == 200
    parties = r.get_json()["data"]["parties"]
    # Regression guard: previously this returned a truncated sentence fragment
    # ("dapat mengakhiri perjanjian ini secara sepihak tan...") as a "party".
    assert "PT Sumber Makmur" in parties
    assert "Budi Santoso" in parties
    for p in parties:
        assert "mengakhiri" not in p.lower(), f"garbage party name leaked back in: {p!r}"

    assert client.get("/api/analyses").status_code == 200


# --------------------------------------------------------------------------
# Legal Research
# --------------------------------------------------------------------------

def test_research_summarize_and_list(client):
    r = post_json(client, "/api/research/summarize", {
        "source_text": "Wanprestasi dalam perjanjian jual beli terjadi ketika salah satu "
                        "pihak tidak memenuhi kewajibannya sesuai perjanjian yang disepakati.",
    })
    assert r.status_code == 200
    assert client.get("/api/research").status_code == 200


# --------------------------------------------------------------------------
# Compliance & Risk
# --------------------------------------------------------------------------

def test_compliance_assess_and_list(client):
    r = post_json(client, "/api/compliance/assess", {
        "business_type": "PT", "sector": "fintech", "activities": "pinjaman online",
    })
    assert r.status_code == 200
    assert client.get("/api/compliance").status_code == 200


# --------------------------------------------------------------------------
# Case Analysis — including export, and regression guard for the
# PDF KeepTogether content-loss bug
# --------------------------------------------------------------------------

def test_case_analysis_and_exports(client):
    narrative = (
        "Karyawan diputus hubungan kerja tanpa pesangon oleh PT Maju Jaya pada "
        "1 Januari 2026 setelah bekerja selama lima tahun tanpa surat peringatan "
        "sebelumnya. Perusahaan mendalilkan efisiensi namun tidak ada dokumen "
        "pendukung. Karyawan menuntut pesangon, uang penghargaan masa kerja, dan "
        "uang penggantian hak sesuai UU Ketenagakerjaan."
    )
    r = post_json(client, "/api/case-analysis", {"title": "Kasus PHK Uji", "narrative": narrative, "verify_online": False})
    assert r.status_code == 200
    x = r.get_json()["data"]
    assert "case_readiness" in x
    assert x.get("case_analysis_id")
    assert x.get("analysis_provenance", {}).get("mode") == "DETERMINISTIC_FALLBACK"
    assert x.get("analysis_provenance", {}).get("ai_available_at_run") is False

    assert client.get("/api/case-analysis").status_code == 200

    r = post_json(client, "/api/case-analysis/export/pdf", x)
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf"
    pdf_bytes = r.get_data()
    assert len(pdf_bytes) > 2000
    # Regression guard: the KeepTogether bug used to silently drop the 2nd and
    # 3rd line of every section longer than 3 lines. Extract the text back out
    # and confirm known distinctive phrases from the narrative/analysis
    # actually made it into the PDF, not just page 1 boilerplate.
    try:
        from pypdf import PdfReader
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
        assert "PT Maju Jaya" in text or "pesangon" in text
    except ImportError:
        pass  # pypdf not installed in this environment; byte-length check above still applies

    r = post_json(client, "/api/case-analysis/export/docx", x)
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/vnd.openxmlformats")

    r = post_json(client, "/api/case-analysis/export/xyz", x)
    assert r.status_code == 400

    r = post_json(client, "/api/case-analysis/export/pdf", {})
    assert r.status_code == 400


# --------------------------------------------------------------------------
# Norm Conflicts
# --------------------------------------------------------------------------

def test_norm_conflicts(client):
    r = post_json(client, "/api/norm-conflicts", {
        "provisions": ["UU Tipikor Pasal 3", "KUHP Pasal 604"],
        "facts_context": "Dugaan korupsi dengan unsur perdata/wanprestasi",
    })
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert "conflicts_detected" in data
    assert "relationships_only" in data


# --------------------------------------------------------------------------
# Client Communication — regression guard for the stale-schema bug
# --------------------------------------------------------------------------

def test_client_communication_generate_save_list(client):
    r = post_json(client, "/api/communication/generate", {
        "client_name": "Budi", "document_type": "client_update", "matter": "sengketa waris",
    })
    assert r.status_code == 200

    r = post_json(client, "/api/communications", {
        "client_name": "Budi", "client_email": "", "subject": "Update Perkara",
        "message": "Pesan pembaruan untuk klien", "document_type": "client_update", "status": "draft",
    })
    assert r.status_code == 200
    comm_id = r.get_json()["communication_id"]

    r = client.get("/api/communications")
    assert r.status_code == 200
    rows = r.get_json()["data"]
    assert any(row["id"] == comm_id for row in rows)


# --------------------------------------------------------------------------
# History cleanup endpoints (safe here — isolated test DB, not the real one)
# --------------------------------------------------------------------------

def test_history_clear_kind_and_purge_all(client):
    post_json(client, "/api/drafts", {
        "title": "Throwaway", "doc_type": "Somasi", "content": "isi " * 20,
        "word_count": 5, "clause_count": 0, "status": "saved",
    })
    r = client.delete("/api/history/drafts")
    assert r.status_code == 200
    assert r.get_json()["deleted"] >= 1

    r = client.delete("/api/history", data=json.dumps({"confirm": "salah"}),
                       content_type="application/json")
    assert r.status_code == 400

    r = client.delete("/api/history", data=json.dumps({"confirm": "HAPUS SEMUA RIWAYAT"}),
                       content_type="application/json")
    assert r.status_code == 200

    assert client.get("/api/drafts").get_json()["data"] == []


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))


# --------------------------------------------------------------------------
# Stability baseline guards
# --------------------------------------------------------------------------

def test_schema_matches_expected_columns():
    conn = get_db_connection()
    try:
        version_row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        assert version_row and int(version_row[0]) == SCHEMA_VERSION
        for table, expected in EXPECTED_COLUMNS.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            missing = [name for name, _ in expected if name not in existing]
            assert not missing, f"schema drift in {table}: {missing}"
    finally:
        conn.close()


def test_contract_risk_detects_semantic_unilateral_termination():
    text = "Pihak Pertama dapat mengakhiri perjanjian ini secara sepihak tanpa pemberitahuan sebelumnya."
    risks = RiskDetector.analyze(text)
    assert any(r.category == 'Terminasi Sepihak' and r.risk_level == 'HIGH' for r in risks)


def test_regulatory_corpus_has_priority_domains():
    regs = get_all_regulations()
    assert len(regs) >= 10
    for query in ('ketenagakerjaan phk pesangon', 'perseroan direksi', 'bpr tata kelola kredit'):
        hits = search_regulations(query, limit=5)
        assert hits, f"no regulatory hit for {query}"

def test_health_version_is_centralized(client):
    from version import LEXICORE_VERSION
    assert client.get('/api/health').get_json()['version'] == LEXICORE_VERSION

# --------------------------------------------------------------------------
# v1.3.5 Regulatory Corpus Expansion / relevance regression tests
# --------------------------------------------------------------------------

def test_regulatory_corpus_expanded_and_structured():
    from regulatory_db import corpus_stats
    stats = corpus_stats()
    assert stats["regulations"] >= 19
    assert stats["articles"] >= 55
    assert stats["domains"] >= 20


def test_labor_query_does_not_rank_tipikor_as_primary_result():
    hits = search_regulations("PHK pesangon PKWT ketenagakerjaan", limit=5)
    assert hits
    ids = [h["regulation"]["id"] for h in hits]
    assert ids[0] in {"uu_ketenagakerjaan_13_2003_6_2023", "pp_35_2021", "uu_pphi_2_2004"}
    assert "uu_tipikor_31_1999" not in ids[:3]


def test_bpr_temporal_corpus_contains_pre_and_post_event_rules():
    from regulatory_db import get_regulation_by_id
    pre = get_regulation_by_id("pojk_4_2015_tata_kelola_bpr")
    post = get_regulation_by_id("pojk_23_2022_bmpk_bpr")
    current = get_regulation_by_id("pojk_9_2024_tata_kelola_bpr")
    assert pre and pre["effective_date"] == "2015-04-01"
    assert post and post["effective_date"] == "2022-11-23"
    assert current and current["effective_date"] == "2024-07-01"
    assert "September 2022" in post.get("temporal_note", "")


def test_regulatory_intelligence_reports_expanded_counts(client):
    r = client.get("/api/regulatory-intelligence/catalog")
    assert r.status_code == 200
    data = r.get_json()
    # Endpoint shape may wrap the catalog. Search recursively without coupling
    # the test to presentation-only response nesting.
    def find_counts(obj):
        if isinstance(obj, dict):
            if "counts" in obj and isinstance(obj["counts"], dict):
                return obj["counts"]
            for v in obj.values():
                found = find_counts(v)
                if found:
                    return found
        return None
    counts = find_counts(data)
    assert counts and counts.get("regulations", 0) >= 19 and counts.get("articles", 0) >= 55

# --------------------------------------------------------------------------
# v1.3.5.3 BAP benchmark / full-document pipeline corrective
# --------------------------------------------------------------------------

def test_full_document_chunk_plan_never_reports_zero_for_large_text():
    from ai_engine import chunk_diagnostics
    diag = chunk_diagnostics(("Dokumen pemeriksaan kredit BPR tahun 2022. " * 3500))
    assert diag["characters"] > 100000
    assert diag["segments_total"] > 0
    assert all(n > 0 for n in diag["segment_lengths"])


def test_case_applicable_law_prunes_orphan_and_irrelevant_domains():
    result = {
        "case_regulatory_snapshot": {"domains": [{"id":"financial_services"},{"id":"corruption"}]},
        "applicable_law": [
            {"domain":"Norma disebut dalam dokumen","source":"Pasal 603"},
            {"domain":"Norma disebut dalam dokumen","source":"Pasal 3J"},
            {"domain":"Ketenagakerjaan","source":"Peraturan ketenagakerjaan"},
            {"domain":"Pidana Materiil","source":"UU No. 1 Tahun 2023 tentang KUHP"},
        ],
    }
    cleaned = appmod._clean_applicable_law(result)
    sources = [x["source"] for x in cleaned]
    assert "Pasal 603" not in sources
    assert "Pasal 3J" not in sources
    assert all(x["domain"] != "Ketenagakerjaan" for x in cleaned)
    assert "UU No. 1 Tahun 2023 tentang KUHP" in sources


def test_norm_conflict_does_not_call_cross_domain_coexistence_a_conflict():
    from norm_conflict import analyze_conflicts
    out = analyze_conflicts(["UU Tipikor", "KUHPerdata"], "perkara kredit BPR perjanjian dan dugaan korupsi tahun 2022", [])
    assert not any(c.get("type") == "LEX_SPECIALIS_CANDIDATE" for c in out.get("conflicts_detected", []))
    assert any(r.get("classification") == "RELATIONSHIP_ONLY" for r in out.get("relationships_only", []))


def test_export_uses_compact_regulatory_section_and_executive_summary():
    from exporters.common import _case_export_sections
    sample = {
        "title":"Benchmark BAP", "analytical_method":"DETERMINISTIC_FALLBACK",
        "executive_summary":["Fakta kunci: fasilitas kredit BPR pada 2022.", "Isu utama: actual loss dan mens rea."],
        "case_regulatory_snapshot":{"event_year_candidate":2022,"event_date_candidate":"2022-09-27"},
        "regulatory_matches":[
            {"regulation":{"nomor":"POJK No. 23 Tahun 2022","effective_date":"2022-11-23"},"matched_articles":[]},
        ],
        "action_plan":[],
    }
    _, sections = _case_export_sections(sample)
    titles=[x[0] for x in sections]
    assert "Ringkasan Eksekutif" in titles
    assert "Regulasi & Tempus" in titles
    assert "Korpus Regulasi & Regulatory Intelligence" not in titles
    reg=dict(sections)["Regulasi & Tempus"]
    assert any("POST_TEMPUS_EXCLUDED" in line for line in reg)


def test_export_same_year_without_exact_event_date_stays_uncertain():
    from exporters.common import _case_export_sections
    sample = {
        "title":"Tempus year-only",
        "case_regulatory_snapshot":{"event_year_candidate":2022},
        "regulatory_matches":[
            {"regulation":{"nomor":"POJK No. 23 Tahun 2022","effective_date":"2022-11-23"},"matched_articles":[]},
        ],
    }
    _, sections = _case_export_sections(sample)
    reg=dict(sections)["Regulasi & Tempus"]
    assert any("TEMPUS_REQUIRES_EXACT_DATE" in line for line in reg)
    assert not any("POST_TEMPUS_EXCLUDED" in line for line in reg)


def test_bap_material_date_prefers_credit_date_over_procedural_and_regulation_dates():
    from services.regulatory_retrieval import detect_material_date
    sample = (
        "Berita Acara Pemeriksaan tanggal 21 Mei 2026. "
        "Diperlihatkan Perjanjian Kredit Nomor 10130003097 tanggal 27 September 2022. "
        "POJK No. 23 Tahun 2022 berlaku 23 November 2022."
    )
    assert detect_material_date(sample) == "2022-09-27"

# --------------------------------------------------------------------------
# v1.3.5.4 Regulatory & Full-Document Stabilization
# --------------------------------------------------------------------------

def test_ocr_split_day_is_normalized_without_becoming_material_event():
    from services.regulatory_retrieval import detect_case_dates, detect_material_date
    sample=(
        "Jawaban Tergugat atas Gugatan Penggugat tertanggal 2 6 Februari 2026. "
        "Eksepsi kompetensi absolut Pengadilan Agama. "
        "Sertipikat Hak Milik berdasarkan data fisik dan yuridis tanggal 03/11/2017."
    )
    dates=detect_case_dates(sample)
    assert any(x["date"] == "2026-02-26" and x["role"] == "procedural_or_filing" for x in dates)
    assert detect_material_date(sample) is None


def test_land_civil_pleading_domains_do_not_route_banking_or_employment():
    from services.regulatory_retrieval import detect_domains
    sample=(
        "Jawaban Tergugat atas Gugatan Penggugat. Eksepsi Obscuur Libel dan Plurium Litis Consortium. "
        "Kewenangan absolut Pengadilan Agama Pasal 49. Sertipikat Hak Milik, Surat Ukur, "
        "data fisik dan data yuridis serta Kantor Pertanahan."
    )
    ids={x["id"] for x in detect_domains(sample)}
    assert {"civil_procedure","land_property","religious_court"}.issubset(ids)
    assert "financial_services" not in ids
    assert "employment" not in ids
    assert "criminal" not in ids


def test_regulatory_seed_hard_gate_removes_cross_domain_contamination():
    from services.regulatory_retrieval import filter_regulatory_matches_for_domains
    matches=[
        {"regulation":{"nomor":"POJK No. 23 Tahun 2022","tentang":"BMPK BPR"},"matched_articles":[]},
        {"regulation":{"nomor":"UU No. 13 Tahun 2003","tentang":"Ketenagakerjaan"},"matched_articles":[]},
        {"regulation":{"nomor":"Staatsblad 1847 No. 23","tentang":"Kitab Undang-Undang Hukum Perdata"},"matched_articles":[]},
    ]
    domains=[{"id":"civil_procedure"},{"id":"land_property"},{"id":"civil_contract"}]
    out=filter_regulatory_matches_for_domains(matches,domains)
    titles=' '.join((x.get('regulation') or {}).get('tentang','') for x in out).lower()
    assert 'hukum perdata' in titles
    assert 'bpr' not in titles
    assert 'ketenagakerjaan' not in titles


def test_full_document_segment_trace_accepts_valid_payload(monkeypatch):
    import ai_engine
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    def fake(prompt):
        if 'Senior Legal Reasoning Engine' in prompt:
            return {"facts":["fakta"],"legal_issues":["isu"],"legal_analysis":"analisis","evidentiary_gaps":[],"action_plan":[]}
        return {"facts":[{"statement":"fakta","evidence":"kutipan","type":"DOCUMENT_FACT"}],"source_items":[{"label":"SOURCE FACT","statement":"fakta","evidence":"kutipan","segment":"1"}]}
    monkeypatch.setattr(ai_engine,'_gemini_json_retry',fake)
    out=ai_engine.analyze_full_document('Fakta perkara. '*1000,'Test',{},None)
    assert out["document_reading"]["segments_read"] > 0
    assert all(x["state"] == "ACCEPTED" for x in out["document_reading"]["segment_trace"])


def test_full_document_failure_exposes_auditable_reason(monkeypatch):
    import ai_engine
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    def fail(_prompt):
        raise RuntimeError('Gemini HTTP 429: quota')
    monkeypatch.setattr(ai_engine,'_gemini_json_retry',fail)
    with pytest.raises(ai_engine.FullDocumentFailure) as err:
        ai_engine.analyze_full_document('Dokumen perkara. '*900,'Test',{},None)
    diag=err.value.diagnostics
    assert diag["segments_total"] > 0
    assert diag["segments_read"] == 0
    assert diag["status"] == "ALL_SEGMENTS_REJECTED"
    assert all(x["reason"] == "HTTP_429_RATE_LIMIT" for x in diag["segment_trace"])


def test_orphan_article_with_ayat_is_removed_from_applicable_law():
    result={
        "case_regulatory_snapshot":{"domains":[{"id":"civil_procedure"},{"id":"land_property"}]},
        "applicable_law":[
            {"domain":"Norma disebut dalam dokumen","source":"Pasal 19 ayat (2)"},
            {"domain":"Pertanahan & Properti","source":"UUPA dan peraturan pertanahan yang berlaku"},
            {"domain":"Ketenagakerjaan","source":"Peraturan ketenagakerjaan"},
        ],
    }
    out=appmod._clean_applicable_law(result)
    sources=[x["source"] for x in out]
    assert "Pasal 19 ayat (2)" not in sources
    assert "UUPA dan peraturan pertanahan yang berlaku" in sources
    assert all(x.get("domain") != "Ketenagakerjaan" for x in out)


def test_ai_http_error_reasons_are_specific():
    import ai_engine
    assert ai_engine._http_reason(400) == 'HTTP_400_BAD_REQUEST'
    assert ai_engine._http_reason(403) == 'HTTP_403_AUTH_OR_PERMISSION'
    assert ai_engine._http_reason(429) == 'HTTP_429_RATE_LIMIT'
    assert ai_engine._http_reason(503) == 'HTTP_503_UPSTREAM'


def test_bpr_export_prunes_incidental_bw_seed():
    from exporters.common import _case_export_sections
    sample={
        'title':'BAP BPR',
        'case_regulatory_snapshot':{'domains':[{'id':'financial_services'},{'id':'corruption'},{'id':'criminal'},{'id':'regional_government'}], 'event_date_candidate':'2022-09-27'},
        'regulatory_matches':[
            {'regulation':{'nomor':'Staatsblad 1847 No. 23','tentang':'Kitab Undang-Undang Hukum Perdata','effective_date':'1848-05-01'},'matched_articles':[{'pasal':'Pasal 1233'}]},
            {'regulation':{'nomor':'POJK No. 13/POJK.03/2015','tentang':'Penerapan Manajemen Risiko bagi Bank Perkreditan Rakyat','effective_date':'2015-11-12'},'matched_articles':[{'topic':'Risiko Kredit'}]},
        ],
        'action_plan':[],
    }
    _, sections=_case_export_sections(sample)
    reg=' '.join(dict(sections)['Regulasi & Tempus']).lower()
    assert 'pojk' in reg
    assert 'staatsblad' not in reg


def test_action_plan_dedupes_same_substantive_issue():
    import app
    issue='Laporan hasil perhitungan kerugian keuangan negara/daerah lengkap beserta metode dan tanggal cut-off'
    result={
        'facts':['Dokumen membahas fasilitas kredit Perumda BPR tahun 2022.'],
        'legal_issues':['Apakah kerugian aktual telah terbukti?'],
        'legal_analysis':'Kerugian aktual perlu diverifikasi.',
        'evidentiary_gaps':[issue],
        'evidence_needed':[issue],
        'action_plan':[],
    }
    out=app._ensure_evidence_to_action(result)
    issues=[str(a.get('issue') or '') for a in out['action_plan']]
    assert sum(1 for x in issues if x == issue) == 1


def test_bpr_executive_summary_rejects_ocr_passthrough_noise():
    import app
    result={
        'source_text':'Berita Acara Pemeriksaan Tersangka dugaan Tindak Pidana Korupsi dalam Pemberian Fasilitas Kredit oleh Perumda BPR Kota Blitar kepada Debitur Dewi Mufarida Tahun 2022. Direktur Utama.',
        'facts':['Anak Dani (Alm) SOENARKO, sebagaimana diatur Jo.Pasal 603 Jo.Pasal 18', 'Mengertikah Tersangka mengapa Tersangka dimintai keterangan saat ini?'],
        'legal_issues':['Apakah kerugian aktual telah terbukti?'],
        'legal_analysis':'Pelanggaran prosedur tidak otomatis membuktikan tindak pidana.',
        'evidentiary_gaps':['Laporan audit kerugian aktual.'],
    }
    lines=app._compact_executive_summary(result)
    text=' '.join(lines)
    assert 'Anak Dani' not in text
    assert 'Mengertikah Tersangka' not in text
    assert 'Perumda BPR' in text
