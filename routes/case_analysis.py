"""Case Analysis HTTP routes.

The route layer owns request parsing/response formatting only. Core reasoning
helpers are injected from the case-analysis service so this module remains
small and testable.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from ai_engine import analyze_full_document, chunk_diagnostics, is_available as ai_available, status as ai_status, FullDocumentFailure
from contract_review import DocumentExtractor
from database import CaseAnalysisManager, LegalSourceVerificationManager, CaseRegulatorySnapshotManager, AuditLogger
from exporters.case_docx import export_case_docx
from exporters.case_pdf import export_case_pdf
from legal_sources import verify_queries
from norm_conflict import analyze_conflicts
from version import LEXICORE_VERSION
from services.regulatory_retrieval import retrieve_for_case_dynamic, filter_regulatory_matches_for_domains


def create_case_analysis_blueprint(*, allowed_file, verification_queries, case_payload,
                                   ensure_evidence_to_action, readiness_profile):
    bp = Blueprint("case_analysis_routes", __name__)

    @bp.route('/api/case-analysis', methods=['GET', 'POST'])
    def case_analysis():
        if request.method == 'GET':
            return jsonify(success=True, data=CaseAnalysisManager.all(request.args.get('limit', 30, type=int)))

        text = ''; title = 'Case Analysis'; input_type = 'narrative'; filename = ''; d = {}
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            title = (request.form.get('title') or 'Case Analysis').strip()
            narrative = (request.form.get('narrative') or '').strip(); text = narrative
            f = request.files.get('file')
            if f and f.filename:
                if not allowed_file(f.filename):
                    return jsonify(success=False, error='Dokumen Case Analysis hanya mendukung PDF/DOCX'), 400
                td = tempfile.mkdtemp()
                try:
                    filename = secure_filename(f.filename); path = os.path.join(td, filename); f.save(path)
                    extracted = DocumentExtractor.extract_text(path).strip()
                    if not extracted:
                        return jsonify(success=False, error='Dokumen berhasil diunggah tetapi teks tidak dapat diekstrak. Pastikan PDF memiliki text layer atau gunakan DOCX.'), 400
                    text = (narrative + '\n\n' + extracted).strip(); input_type = 'document' if not narrative else 'narrative+document'
                finally:
                    shutil.rmtree(td, ignore_errors=True)
            elif len(narrative) < 120:
                return jsonify(success=False, error='Untuk analisis tanpa dokumen, narasi minimal 120 karakter diperlukan.'), 400
            verify_online = request.form.get('verify_online', 'true').lower() not in ('0', 'false', 'no')
        else:
            d = request.get_json(silent=True) or {}
            title = (d.get('title') or 'Case Analysis').strip(); text = (d.get('narrative') or d.get('source_text') or '').strip()
            if len(text) < 120:
                return jsonify(success=False, error='Untuk analisis tanpa dokumen, narasi minimal 120 karakter diperlukan.'), 400
            verify_online = bool(d.get('verify_online', True))

        verification_q = verification_queries(text, title)
        official = verify_queries(verification_q, include_health=True) if verify_online else None
        result = case_payload(text, title, input_type, filename, official)

        # v1.3.5.1 — regulations follow the case.  The curated corpus is only a
        # compact seed/fallback; authoritative discovery is routed per detected
        # legal domain and stored later as metadata-only, case-scoped snapshot.
        case_regulatory = retrieve_for_case_dynamic(
            text=text, title=title, provision_refs=result.get('provision_refs', []), qualified_queries=verification_q,
            local_seed_matches=result.get('regulatory_matches', []), legal_issues=result.get('legal_issues', []), online=verify_online,
        )
        result['case_regulatory_snapshot'] = case_regulatory
        result['regulatory_matches'] = filter_regulatory_matches_for_domains(result.get('regulatory_matches', []), case_regulatory.get('domains', []))
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
                'regulatory_corpus_status': result.get('regulatory_corpus_status', {}), 'case_regulatory_snapshot': result.get('case_regulatory_snapshot', {}), 'norm_conflicts': result.get('norm_conflicts', {})
            }
            merged = dict(result); merged.update(ai_result); merged.update(protected)
            dr = merged.get('document_reading') or {}
            complete = dr.get('status') == 'COMPLETE'
            merged['analysis_provenance'] = {
                'mode': 'GEMINI_FULL_DOCUMENT' if complete else 'GEMINI_FULL_DOCUMENT_PARTIAL',
                'provider': dr.get('provider') or ai_capability.get('provider'),
                'model': dr.get('model') or ai_capability.get('model'),
                'ai_available_at_run': bool(ai_capability.get('available')),
                'ai_attempted': True, 'ai_succeeded': True,
                'segments_read': dr.get('segments_read', 0), 'segments_total': dr.get('segments_total', 0),
            }
            merged['analytical_method'] = merged['analysis_provenance']['mode']
            merged['coverage_note'] = f'LexiCore v{LEXICORE_VERSION} menggunakan Full-Document Multi-Pass AI Reasoning ({merged["analysis_provenance"]["mode"]}). Evidence-to-Action memisahkan fakta sumber, inference, gap bukti, dan langkah tindak lanjut. Verifikasi hukum positif tetap memerlukan sumber resmi dan Professional Verification: PENDING.'
            result = ensure_evidence_to_action(merged)
            AuditLogger.log_action('ai_full_document_case_analysis', 'case_analysis', None, f"{title}: {result.get('document_reading',{}).get('segments_read',0)}/{result.get('document_reading',{}).get('segments_total',0)} segments")
        else:
            fallback_reason = 'AI_ERROR_OR_EMPTY_RESULT' if ai_attempted else 'AI_UNAVAILABLE'
            result['document_reading'] = {
                'characters': len(text), 'segments_total': ai_chunk_plan.get('segments_total', 0),
                'segments_read': ai_failure_diagnostics.get('segments_read', 0),
                'status': 'DETERMINISTIC_FALLBACK', 'provider': ai_capability.get('provider'),
                'model': ai_capability.get('model'), 'chunk_plan': ai_chunk_plan,
                'segment_trace': ai_failure_diagnostics.get('segment_trace', []),
                'failure_stage': ai_failure_diagnostics.get('status'),
                'synthesis_reason': ai_failure_diagnostics.get('synthesis_reason'),
                'failures': ai_failure_diagnostics.get('failures') or ([ai_error] if ai_error else [])
            }
            result['analysis_provenance'] = {
                'mode': 'DETERMINISTIC_FALLBACK', 'provider': ai_capability.get('provider'),
                'model': ai_capability.get('model'), 'ai_available_at_run': bool(ai_capability.get('available')),
                'ai_attempted': ai_attempted, 'ai_succeeded': False, 'fallback_reason': fallback_reason,
                'error': ai_error, 'segments_total': ai_chunk_plan.get('segments_total', 0), 'segments_read': ai_failure_diagnostics.get('segments_read', 0), 'failure_stage': ai_failure_diagnostics.get('status'),
            }
            result['analytical_method'] = 'DETERMINISTIC_FALLBACK'
            if ai_attempted:
                result['coverage_note'] = f'LexiCore v{LEXICORE_VERSION} menggunakan deterministic fallback karena Full-Document AI tidak menghasilkan analisis yang dapat dipakai pada run ini. Kapabilitas AI saat run: tersedia. Evidence-to-Action dan retrieval sumber resmi tetap berjalan. Professional Verification: PENDING.'
            else:
                result['coverage_note'] = f'LexiCore v{LEXICORE_VERSION} menggunakan deterministic fallback karena Legal AI Provider tidak tersedia pada saat run ini. Evidence-to-Action dan retrieval sumber resmi tetap berjalan. Professional Verification: PENDING.'
            result = ensure_evidence_to_action(result)

        result['case_readiness'] = readiness_profile(result)
        result['case_analysis_id'] = CaseAnalysisManager.save(result)
        if result.get('case_regulatory_snapshot'):
            result['case_regulatory_snapshot_id'] = CaseRegulatorySnapshotManager.save(
                result['case_analysis_id'], result['case_regulatory_snapshot'])
        if official:
            result['verification_id'] = LegalSourceVerificationManager.save(result['case_analysis_id'], official)
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
