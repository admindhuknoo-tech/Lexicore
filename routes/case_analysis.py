"""Case Analysis HTTP routes.

The route layer owns request parsing/response formatting only. Core reasoning
helpers are injected from the case-analysis service so this module remains
small and testable.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import threading
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file, g
from werkzeug.utils import secure_filename

from ai_engine import analyze_full_document, chunk_diagnostics, is_available as ai_available, status as ai_status, FullDocumentFailure
from contract_review import DocumentExtractor
from database import CaseAnalysisManager, LegalSourceVerificationManager, CaseRegulatorySnapshotManager, AuditLogger
from exporters.case_docx import export_case_docx
from exporters.case_pdf import export_case_pdf
from legal_sources import verify_queries
from norm_conflict import analyze_conflicts
from version import LEXICORE_VERSION, PRODUCT_LABEL
from services.regulatory_retrieval import retrieve_for_case_dynamic, filter_regulatory_matches_for_domains
from services.case_domain_classifier import classify_case
from services.case_working_paper import build_case_working_paper
from services.case_reasoning_guard import apply_reasoning_guard
from services.case_consistency_guard import apply_global_case_consistency
from services.legal_review_engine import apply_professional_review


def create_case_analysis_blueprint(*, allowed_file, verification_queries, case_payload,
                                   ensure_evidence_to_action, readiness_profile):
    bp = Blueprint("case_analysis_routes", __name__)
    # Single-user local app: never allow multiple expensive Case Analysis runs
    # to pile up. A second submit returns immediately instead of competing for
    # OCR/network/SQLite resources and making the whole dashboard look frozen.
    case_run_lock = threading.Lock()

    @bp.before_request
    def _guard_case_analysis_run():
        if request.endpoint == 'case_analysis_routes.case_analysis' and request.method == 'POST':
            if not case_run_lock.acquire(blocking=False):
                return jsonify(success=False, error='Case Analysis lain masih berjalan. Tunggu proses aktif selesai.'), 409
            g._lexicore_case_lock = True

    def _release_case_lock():
        if getattr(g, '_lexicore_case_lock', False):
            g._lexicore_case_lock = False
            try: case_run_lock.release()
            except RuntimeError: pass

    @bp.after_request
    def _release_case_lock_after(response):
        _release_case_lock()
        return response

    @bp.teardown_request
    def _release_case_lock_teardown(_exc):
        _release_case_lock()

    @bp.route('/api/case-analysis', methods=['GET', 'POST'])
    def case_analysis():
        if request.method == 'GET':
            return jsonify(success=True, data=CaseAnalysisManager.all(request.args.get('limit', 30, type=int)))

        request_started=time.monotonic(); perf={}
        text = ''; title = 'Case Analysis'; input_type = 'narrative'; filename = ''; d = {}; ingestion = None
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            title = (request.form.get('title') or 'Case Analysis').strip()
            narrative = (request.form.get('narrative') or '').strip(); text = narrative
            f = request.files.get('file')
            if f and f.filename:
                if not allowed_file(f.filename):
                    return jsonify(success=False, error='Dokumen Case Analysis mendukung PDF/DOCX serta scan/foto PNG, JPG/JPEG, WEBP, dan TIFF.'), 400
                td = tempfile.mkdtemp()
                try:
                    filename = secure_filename(f.filename); path = os.path.join(td, filename); f.save(path)
                    # Bug fix (v1.3.5.4): a corrupt/encrypted/malformed upload made
                    # DocumentExtractor raise (e.g. PyPDF2.PdfReadError), which was
                    # not caught here and produced an unhandled 500 HTML page
                    # instead of the JSON error response the frontend expects.
                    try:
                        t0=time.monotonic()
                        extracted, ingestion = DocumentExtractor.extract_with_diagnostics(path)
                        perf['document_ingestion']=round((time.monotonic()-t0)*1000)
                        extracted = extracted.strip()
                    except ValueError as exc:
                        return jsonify(success=False, error=str(exc)), 400
                    except Exception:
                        return jsonify(success=False, error='Dokumen tidak dapat dibaca. File mungkin rusak, terenkripsi/berpassword, atau formatnya tidak valid. Coba unggah ulang atau gunakan salinan lain.'), 422
                    if not extracted:
                        ocr_note = '; '.join((ingestion or {}).get('warnings') or [])
                        msg = 'Dokumen berhasil diunggah tetapi tidak menghasilkan teks. PDF/gambar tampaknya hasil scan dan OCR lokal tidak tersedia atau tidak mampu membacanya.'
                        if ocr_note:
                            msg += ' ' + ocr_note
                        return jsonify(success=False, error=msg, ingestion=ingestion), 422
                    text = (narrative + '\n\n' + extracted).strip(); input_type = 'document' if not narrative else 'narrative+document'
                finally:
                    shutil.rmtree(td, ignore_errors=True)
            elif len(narrative) < 120:
                return jsonify(success=False, error='Untuk analisis tanpa dokumen, narasi minimal 120 karakter diperlukan.'), 400
            regulatory_mode=(request.form.get('regulatory_mode') or 'hybrid').strip().lower()
            verify_online = regulatory_mode in ('online','hybrid')
        else:
            d = request.get_json(silent=True) or {}
            title = (d.get('title') or 'Case Analysis').strip(); text = (d.get('narrative') or d.get('source_text') or '').strip()
            if len(text) < 120:
                return jsonify(success=False, error='Untuk analisis tanpa dokumen, narasi minimal 120 karakter diperlukan.'), 400
            regulatory_mode=(d.get('regulatory_mode') or ('hybrid' if d.get('verify_online',True) else 'offline')).strip().lower()
            verify_online = regulatory_mode in ('online','hybrid')

        verification_q = verification_queries(text, title)
        # RC18 R15 latency closure: do not run a second official-source search here.
        # Dynamic case-scoped retrieval below already performs the authoritative
        # federation using the same qualified queries.  This pre-pass used to add
        # up to ~25s of duplicate DNS/TLS/search work before the real verification
        # pipeline even started, which could push a complete Case Analysis beyond
        # the request/proxy time limit.  Keep only cached source-health metadata
        # for the deterministic working-paper status; no network search is issued.
        t0=time.monotonic()
        official = verify_queries([], include_health=True, health_cache_only=True) if verify_online else None
        perf['official_source_discovery']=round((time.monotonic()-t0)*1000)
        t0=time.monotonic()
        result = case_payload(text, title, input_type, filename, official)
        perf['deterministic_case_payload']=round((time.monotonic()-t0)*1000)
        if ingestion:
            result['document_ingestion'] = ingestion
        domain_contract=classify_case(text)
        result['case_posture']=domain_contract.get('posture')
        result['domain_classification']=domain_contract
        result['domain_contract']=domain_contract

        # v1.3.5.1 — regulations follow the case.  The curated corpus is only a
        # compact seed/fallback; authoritative discovery is routed per detected
        # legal domain and stored later as metadata-only, case-scoped snapshot.
        t0=time.monotonic()
        case_regulatory = retrieve_for_case_dynamic(
            text=text, title=title, provision_refs=result.get('provision_refs', []), qualified_queries=verification_q,
            local_seed_matches=result.get('regulatory_matches', []), legal_issues=result.get('legal_issues', []), online=verify_online,
            retrieval_mode=regulatory_mode, domain_classification=domain_contract,
        )
        perf['case_regulatory_retrieval']=round((time.monotonic()-t0)*1000)
        result['case_regulatory_snapshot'] = case_regulatory
        result['regulatory_matches'] = (case_regulatory.get('local_database_results') or filter_regulatory_matches_for_domains(result.get('regulatory_matches', []), case_regulatory.get('domains', [])))
        result['norm_conflicts'] = analyze_conflicts(result.get('provision_refs', []), text, result.get('regulatory_matches', []))
        result['regulatory_corpus_status'] = {
            'mode': case_regulatory.get('mode'),
            'domains': len(case_regulatory.get('domains', [])),
            'queries': len(case_regulatory.get('queries', [])),
            'official_results': case_regulatory.get('official_results_count', 0),
            'local_seed_matches': case_regulatory.get('local_seed_count', 0),
            'cache_policy': case_regulatory.get('cache_policy'),
            'official_verification_required': True,
            'professional_verification': 'PENDING',
        }
        ai_result = None
        ai_capability = ai_status()
        ai_chunk_plan = chunk_diagnostics(text)
        ai_attempted = bool(ai_available())
        ai_error = None
        ai_failure_diagnostics = {}
        if ai_attempted:
            try:
                ai_result = analyze_full_document(text, title, result, official)
            except FullDocumentFailure as exc:
                ai_error = str(exc)[:500]
                ai_failure_diagnostics = exc.diagnostics or {}
                AuditLogger.log_action('ai_case_analysis_error', 'case_analysis', None, ai_error)
            except Exception as exc:
                ai_error = str(exc)[:500]
                AuditLogger.log_action('ai_case_analysis_error', 'case_analysis', None, ai_error)

        if ai_result:
            protected = {
                'title': title, 'input_type': input_type, 'filename': filename, 'source_text': text,
                'official_verification': official, 'legal_status': result.get('legal_status'),
                'money_values': result.get('money_values', []), 'date_values': result.get('date_values', []),
                'provision_refs': result.get('provision_refs', []), 'regulatory_matches': result.get('regulatory_matches', []),
                'regulatory_corpus_status': result.get('regulatory_corpus_status', {}), 'case_regulatory_snapshot': result.get('case_regulatory_snapshot', {}), 'norm_conflicts': result.get('norm_conflicts', {}),
                'case_posture': result.get('case_posture'), 'domain_classification': result.get('domain_classification', {}), 'domain_contract': result.get('domain_contract', {}),
                'document_ingestion': result.get('document_ingestion')
            }
            merged = dict(result); merged.update(ai_result); merged.update(protected)
            dr = merged.get('document_reading') or {}
            complete = dr.get('status') == 'COMPLETE'
            merged['analysis_provenance'] = {
                'mode': 'REMOTE_FULL_DOCUMENT' if complete else 'REMOTE_FULL_DOCUMENT_PARTIAL',
                'provider': dr.get('provider') or ai_capability.get('provider'),
                'model': dr.get('model') or ai_capability.get('model'),
                'ai_available_at_run': bool(ai_capability.get('available')),
                'ai_attempted': True, 'ai_succeeded': True,
                'segments_read': dr.get('segments_read', 0), 'segments_total': dr.get('segments_total', 0),
            }
            merged['analytical_method'] = merged['analysis_provenance']['mode']
            merged['coverage_note'] = f'{PRODUCT_LABEL} menggunakan Full-Document Multi-Pass AI Reasoning ({merged["analysis_provenance"]["mode"]}). Evidence-to-Action memisahkan fakta sumber, inference, gap bukti, dan langkah tindak lanjut. Verifikasi hukum positif tetap memerlukan sumber resmi dan Professional Verification: PENDING.'
            result = ensure_evidence_to_action(merged)
            AuditLogger.log_action('ai_full_document_case_analysis', 'case_analysis', None, f"{title}: {result.get('document_reading',{}).get('segments_read',0)}/{result.get('document_reading',{}).get('segments_total',0)} segments")
        else:
            # Distinguish intentional zero-cost/local analysis from a genuine
            # remote-AI failure.  Document reading can be COMPLETE even when no
            # remote AI segments are sent.
            local_mode = not ai_attempted
            method = 'LOCAL_DETERMINISTIC' if local_mode else 'DETERMINISTIC_FALLBACK'
            fallback_reason = None if local_mode else 'AI_ERROR_OR_EMPTY_RESULT'
            local_units = 1 if text else 0
            result['document_reading'] = {
                'characters': len(text),
                'segments_total': local_units if local_mode else ai_chunk_plan.get('segments_total', 0),
                'segments_read': local_units if local_mode else ai_failure_diagnostics.get('segments_read', 0),
                'status': 'COMPLETE' if text else 'EMPTY',
                'reading_mode': method,
                'provider': ai_capability.get('provider'),
                'model': ai_capability.get('model'), 'chunk_plan': ai_chunk_plan,
                'segment_trace': [] if local_mode else ai_failure_diagnostics.get('segment_trace', []),
                'failure_stage': None if local_mode else ai_failure_diagnostics.get('status'),
                'synthesis_reason': None if local_mode else ai_failure_diagnostics.get('synthesis_reason'),
                'failures': [] if local_mode else (ai_failure_diagnostics.get('failures') or ([ai_error] if ai_error else []))
            }
            result['analysis_provenance'] = {
                'mode': method, 'provider': ai_capability.get('provider'),
                'model': ai_capability.get('model'), 'ai_available_at_run': bool(ai_capability.get('available')),
                'ai_attempted': ai_attempted, 'ai_succeeded': False, 'fallback_reason': fallback_reason,
                'error': ai_error,
                'segments_total': result['document_reading']['segments_total'],
                'segments_read': result['document_reading']['segments_read'],
                'failure_stage': result['document_reading'].get('failure_stage'),
            }
            result['analytical_method'] = method
            if ai_attempted:
                result['coverage_note'] = f'{PRODUCT_LABEL} menggunakan deterministic fallback karena Full-Document AI tidak menghasilkan analisis yang dapat dipakai pada run ini. Evidence-to-Action dan retrieval sumber resmi tetap berjalan. Professional Verification: PENDING.'
            else:
                result['coverage_note'] = f'{PRODUCT_LABEL} menggunakan mode Local Deterministic tanpa panggilan AI eksternal. Dokumen tetap dibaca penuh, Evidence-to-Action dan retrieval sumber hukum tetap berjalan. Professional Verification: PENDING.'
            result = ensure_evidence_to_action(result)

        # Legal Reasoning Guard is intentionally applied AFTER either remote AI
        # or deterministic fallback.  AI/classifier narratives may enrich the
        # analysis, but may not bypass tempus, instrument-identity, case-nexus,
        # forum-vs-merits or attribution gates.  The pre-guard narrative is kept
        # as `unguarded_legal_analysis` for auditability.
        result = apply_reasoning_guard(result, text)
        # v1.3.13.11.10: enforce the same evidence/tempus/legal-verification
        # invariants across executive summary, scoring and downstream renderers.
        result = apply_global_case_consistency(result)
        # v1.3.14-rc3 — integrated professional multi-pass review. This layer
        # reviews the document as a lawyer would: structure, fact/argument
        # separation, anomaly detection, legal gates, adversarial weaknesses,
        # and prioritized recommendations. It remains fail-closed and never
        # silently rewrites the source document.
        result = apply_professional_review(result, text)

        result['case_readiness'] = readiness_profile(result)
        # v1.3.13.5 — canonical four-part Case Analysis working paper.
        # Backward-compatible case_readiness is retained, while the UI/export
        # uses the merits estimate, evidence correlation matrix, legal construction,
        # and tactical action plan below.
        t0=time.monotonic()
        result['case_working_paper'] = build_case_working_paper(result)
        perf['working_paper']=round((time.monotonic()-t0)*1000)
        result['case_analysis_id'] = CaseAnalysisManager.save(result)
        if result.get('case_regulatory_snapshot'):
            result['case_regulatory_snapshot_id'] = CaseRegulatorySnapshotManager.save(
                result['case_analysis_id'], result['case_regulatory_snapshot'])
        if official:
            result['verification_id'] = LegalSourceVerificationManager.save(result['case_analysis_id'], official)
        perf['total']=round((time.monotonic()-request_started)*1000)
        result['performance_timing_ms']=perf
        return jsonify(success=True, data=result)

    @bp.route('/api/case-analysis/<int:case_id>/regulatory-snapshot', methods=['GET'])
    def case_regulatory_snapshot(case_id):
        data = CaseRegulatorySnapshotManager.latest(case_id)
        if not data:
            return jsonify(success=False, error='Snapshot regulasi perkara belum tersedia'), 404
        return jsonify(success=True, data=data)

    @bp.route('/api/case-analysis/export/<fmt>', methods=['POST'])
    def export_case_analysis(fmt):
        x = request.get_json(silent=True) or {}
        if not isinstance(x, dict) or not (x.get('title') or x.get('legal_analysis') or x.get('source_ledger')):
            return jsonify(success=False, error='Belum ada hasil Case Analysis yang dapat diekspor'), 400
        fmt = (fmt or '').lower().strip(); safe = secure_filename(x.get('title') or 'case-analysis') or 'case-analysis'
        stamp = datetime.now().strftime('%Y%m%d-%H%M')
        try:
            if fmt == 'docx':
                bio = export_case_docx(x); mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'; ext = 'docx'
            elif fmt == 'pdf':
                bio = export_case_pdf(x); mime = 'application/pdf'; ext = 'pdf'
            else:
                return jsonify(success=False, error='Format export yang didukung: pdf atau docx'), 400
            AuditLogger.log_action('export_case_analysis', 'case_analysis', x.get('case_analysis_id'), f'{fmt.upper()} | {x.get("title","")[:180]}')
            return send_file(bio, as_attachment=True, download_name=f'LexiCore-{safe}-{stamp}.{ext}', mimetype=mime)
        except RuntimeError as exc:
            return jsonify(success=False, error=str(exc)), 503
        except Exception as exc:
            return jsonify(success=False, error=f'Export {fmt.upper()} gagal: {exc}'), 500

    return bp
