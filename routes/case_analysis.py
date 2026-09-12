"""Case Analysis HTTP routes.

The route layer owns request parsing/response formatting only. Core reasoning
helpers are injected from the case-analysis service so this module remains
small and testable.
"""
from __future__ import annotations

import os
import inspect
import time
import threading
from datetime import datetime
from typing import Optional

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
from services.general_case_orchestrator import apply_general_case_orchestration
from services.material_tempus_extractor import select_material_tempus
from services.reasoning_contract import attach_reasoning_contract
from services.living_analysis_orchestrator import attach_living_analysis
from services.living_law_synthesis import enrich_living_analysis


def create_case_analysis_blueprint(*, allowed_file, verification_queries, case_payload,
                                   ensure_evidence_to_action, readiness_profile):
    bp = Blueprint("case_analysis_routes", __name__)
    # Single-user local app: keep one expensive Case Analysis run at a time,
    # but expose its lifecycle so the UI can attach to the real server state.
    # This avoids the old 240 s client timeout creating a false "stuck" state
    # while OCR legitimately continued on the server.
    case_run_lock = threading.Lock()
    case_progress_lock = threading.Lock()
    case_progress = {
        'active': False, 'token': None, 'percent': 0, 'stage': 'IDLE',
        'detail': '', 'status': 'IDLE', 'started_at': None, 'updated_at': None,
    }

    def _progress_snapshot():
        with case_progress_lock:
            return dict(case_progress)

    def _set_progress(percent: int, stage: str, detail: str = '', *, status: str = 'RUNNING', token: Optional[str] = None):
        now = datetime.now().isoformat(timespec='seconds')
        with case_progress_lock:
            if token is not None and case_progress.get('token') not in (None, token):
                return
            case_progress.update({
                'percent': max(int(case_progress.get('percent') or 0), max(0, min(100, int(percent)))) if status == 'RUNNING' else max(0, min(100, int(percent))),
                'stage': stage,
                'detail': detail or '',
                'status': status,
                'updated_at': now,
            })

    def _request_progress_token():
        token = (request.headers.get('X-Lexicore-Progress-Id') or '').strip()[:96]
        return token or f'local-{int(time.time() * 1000)}-{threading.get_ident()}'

    @bp.before_request
    def _guard_case_analysis_run():
        if request.endpoint == 'case_analysis_routes.case_analysis' and request.method == 'POST':
            token = _request_progress_token()
            if not case_run_lock.acquire(blocking=False):
                snap = _progress_snapshot()
                return jsonify(
                    success=False,
                    error='Case Analysis lain masih berjalan. Progres proses aktif dapat dipantau sampai selesai.',
                    code='CASE_ANALYSIS_IN_PROGRESS',
                    progress=snap,
                ), 409
            g._lexicore_case_lock = True
            g._lexicore_case_progress_token = token
            now = datetime.now().isoformat(timespec='seconds')
            with case_progress_lock:
                case_progress.update({
                    'active': True, 'token': token, 'percent': 1,
                    'stage': 'REQUEST_ACCEPTED', 'detail': 'Permintaan diterima.',
                    'status': 'RUNNING', 'started_at': now, 'updated_at': now,
                })

    def _case_progress(percent: int, stage: str, detail: str = ''):
        token = getattr(g, '_lexicore_case_progress_token', None)
        if token:
            _set_progress(percent, stage, detail, token=token)

    def _release_case_lock(final_status: Optional[str] = None, detail: str = ''):
        if getattr(g, '_lexicore_case_lock', False):
            token = getattr(g, '_lexicore_case_progress_token', None)
            g._lexicore_case_lock = False
            if token:
                with case_progress_lock:
                    if case_progress.get('token') == token:
                        if final_status:
                            case_progress['status'] = final_status
                            case_progress['detail'] = detail or case_progress.get('detail') or ''
                        case_progress['active'] = False
                        case_progress['updated_at'] = datetime.now().isoformat(timespec='seconds')
            try:
                case_run_lock.release()
            except RuntimeError:
                pass

    @bp.after_request
    def _release_case_lock_after(response):
        if getattr(g, '_lexicore_case_lock', False):
            if response.status_code >= 400:
                _release_case_lock('FAILED', f'Proses berakhir dengan HTTP {response.status_code}.')
            else:
                snap = _progress_snapshot()
                if snap.get('percent', 0) < 100:
                    _case_progress(100, 'COMPLETED', 'Analisis selesai.')
                _release_case_lock('COMPLETED', 'Analisis selesai.')
        return response

    @bp.teardown_request
    def _release_case_lock_teardown(exc):
        if getattr(g, '_lexicore_case_lock', False):
            _release_case_lock('FAILED' if exc else 'COMPLETED', str(exc)[:240] if exc else '')

    @bp.route('/api/case-analysis/progress/<token>', methods=['GET'])
    def case_analysis_progress(token):
        snap = _progress_snapshot()
        if not snap.get('token') or snap.get('token') != token:
            return jsonify(success=False, error='Progress Case Analysis tidak ditemukan.'), 404
        return jsonify(success=True, data=snap)

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
                # User uploads are persistent project inputs. Store them in
                # <project>/uploads instead of a temporary directory that is
                # deleted after analysis. Collision-safe names preserve prior files.
                upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                original_name = secure_filename(f.filename) or 'case-document'
                stem, ext = os.path.splitext(original_name)
                filename = original_name
                path = os.path.join(upload_dir, filename)
                if os.path.exists(path):
                    filename = f"{stem}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}{ext}"
                    path = os.path.join(upload_dir, filename)
                f.save(path)
                _case_progress(5, 'UPLOAD_STORED', f'Dokumen tersimpan: uploads/{filename}')

                # Bug fix (v1.3.5.4): malformed/encrypted uploads return JSON.
                try:
                    t0=time.monotonic()
                    _case_progress(8, 'DOCUMENT_READING', 'Membaca dokumen dan menjalankan OCR bila diperlukan.')
                    def _ocr_progress(done, total, phase):
                        total = max(1, int(total or 1)); done = max(0, min(total, int(done or 0)))
                        ratio = done / total
                        if phase == 'rapid':
                            pct = 8 + round(26 * ratio)       # 8..34%
                            phase_label = 'RapidOCR'
                        elif phase == 'tesseract':
                            pct = 34 + round(11 * ratio)      # 34..45%
                            phase_label = 'Tesseract fallback'
                        elif phase == 'complete':
                            pct = 45
                            phase_label = 'Pembacaan dokumen'
                        else:
                            pct = 8 + round(4 * ratio)
                            phase_label = 'Pembacaan dokumen'
                        _case_progress(pct, 'DOCUMENT_READING', f'{phase_label}: {done}/{total} halaman.')
                    extractor = DocumentExtractor.extract_with_diagnostics
                    parameters = inspect.signature(extractor).parameters
                    if 'progress_callback' in parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
                        extracted, ingestion = extractor(path, progress_callback=_ocr_progress)
                    else:
                        # Compatibility with test doubles / older adapters that
                        # intentionally expose the legacy one-argument contract.
                        extracted, ingestion = extractor(path)
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
                if ingestion and ingestion.get('authoritative_for_analysis') is False:
                    coverage = float(ingestion.get('coverage_ratio') or 0.0)
                    return jsonify(
                        success=False,
                        error=(
                            f'OCR coverage terlalu rendah untuk analisis yang representatif ({coverage:.1%}). '
                            'Hasil OCR parsial dipertahankan sebagai diagnostik, tetapi Case Analysis tidak dijalankan '
                            'sampai coverage mencapai ambang minimum atau hasil OCR terbaik sebelumnya dapat dipulihkan.'
                        ),
                        code='OCR_COVERAGE_TOO_LOW_FOR_AUTHORITATIVE_ANALYSIS',
                        ingestion=ingestion,
                    ), 422
                text = (narrative + '\n\n' + extracted).strip(); input_type = 'document' if not narrative else 'narrative+document'
                _case_progress(45, 'DOCUMENT_READING_COMPLETE', f'Pembacaan dokumen selesai; {len(extracted):,} karakter diperoleh.')
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

        _case_progress(48, 'CASE_MAPPING', 'Memetakan fakta, isu, dan referensi hukum awal.')
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
        _case_progress(55, 'CASE_MAPPING_COMPLETE', 'Pemetaan perkara deterministik selesai.')
        perf['deterministic_case_payload']=round((time.monotonic()-t0)*1000)
        if ingestion:
            result['document_ingestion'] = ingestion
        domain_contract=classify_case(text)
        result['case_posture']=domain_contract.get('posture')
        result['domain_classification']=domain_contract
        result['domain_contract']=domain_contract
        # One canonical tempus selection is computed before regulatory
        # verification and then reused downstream.  Extraction remains a
        # candidate gate; it never itself marks law as applicable.
        material_tempus = select_material_tempus(text)
        result['material_tempus'] = material_tempus

        # SAL v1.0 runs before regulatory retrieval.  It is a data-admission
        # contract, not a substantive law validator: future plans, questions,
        # and bare document references are prevented from seeding retrieval.
        from services.semantic_admission import build_sal_contract
        _sal_early=build_sal_contract(text, domain_contract=domain_contract, posture=domain_contract.get('posture') or '', prefix='SOURCE')
        result['semantic_admission']=_sal_early
        _sal_retrieval_text=_sal_early.get('retrieval_text') or text

        # v1.3.5.1 — regulations follow the case.  The curated corpus is only a
        # compact seed/fallback; authoritative discovery is routed per detected
        # legal domain and stored later as metadata-only, case-scoped snapshot.
        _case_progress(58, 'LEGAL_RETRIEVAL', 'Menelusuri dan memverifikasi sumber hukum yang terkait perkara.')
        t0=time.monotonic()
        case_regulatory = retrieve_for_case_dynamic(
            text=_sal_retrieval_text, title=title, provision_refs=result.get('provision_refs', []), qualified_queries=verification_q,
            local_seed_matches=result.get('regulatory_matches', []), legal_issues=result.get('legal_issues', []), online=verify_online,
            retrieval_mode=regulatory_mode, domain_classification=domain_contract,
            material_tempus_selection=material_tempus,
        )
        perf['case_regulatory_retrieval']=round((time.monotonic()-t0)*1000)
        _case_progress(74, 'LEGAL_RETRIEVAL_COMPLETE', 'Penelusuran regulasi perkara selesai.')

        # R16: reconcile the pre-payload cached health snapshot with the actual
        # case-scoped federation that just ran.  R15 intentionally removed the
        # duplicate live pre-search, but that left exports showing 0/0 and
        # OFFICIAL_SOURCE_ACCESS_FAILED even when the dynamic retrieval had
        # authoritative results.  This is metadata reconciliation only: it does
        # not promote any legal-status/tempus/applicability gate.
        if verify_online and isinstance(official, dict):
            reached_by_source={}
            authoritative_ids=set()
            for bundle in case_regulatory.get('search_bundles', []) or []:
                for src in bundle.get('sources', []) or []:
                    if not src.get('authoritative'):
                        continue
                    sid=str(src.get('source_id') or src.get('source_name') or '')
                    if not sid:
                        continue
                    authoritative_ids.add(sid)
                    reached=bool(src.get('reachable')) or bool(src.get('results'))
                    reached_by_source[sid]=bool(reached_by_source.get(sid) or reached)
            reached_count=sum(1 for sid in authoritative_ids if reached_by_source.get(sid))
            total_count=len(authoritative_ids)
            funnel=case_regulatory.get('retrieval_funnel') or {}
            authoritative_found=int(funnel.get('authoritative_source_located') or 0)
            if total_count and reached_count == total_count:
                status='FULL_OFFICIAL_SOURCE_ACCESS'
            elif reached_count or authoritative_found:
                status='PARTIAL_OFFICIAL_SOURCE_ACCESS'
            else:
                status='OFFICIAL_SOURCE_ACCESS_FAILED'
            official['status']=status
            official['checked_at']=case_regulatory.get('fetched_at') or official.get('checked_at')
            summary=official.setdefault('summary', {})
            summary.update({
                'authoritative_sources_reached':reached_count,
                'authoritative_sources_total':total_count,
                'reachable_search_sources':reached_count,
                'results_found':authoritative_found,
                'health_cache_only':True,
                'reconciled_from_case_scoped_retrieval':True,
            })
            official['source_status']='VERIFIED_FROM_OFFICIAL_SOURCE' if authoritative_found else ('OFFICIAL_SOURCES_REACHABLE_NO_MATCH' if reached_count else 'NOT_VERIFIED')
            official['cross_check']='COMPLETE' if status=='FULL_OFFICIAL_SOURCE_ACCESS' else ('PARTIAL' if status=='PARTIAL_OFFICIAL_SOURCE_ACCESS' else 'FAILED')

        result['official_verification'] = official
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
        _case_progress(77, 'LEGAL_ANALYSIS', 'Menyusun analisis hukum dan menguji hipotesis perkara.')
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
                'material_tempus': result.get('material_tempus', {}),
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
        _case_progress(88, 'REASONING_GUARDS', 'Menguji konsistensi, tempus, identitas norma, dan batas kesimpulan.')
        result = apply_global_case_consistency(result)
        # v1.3.14-rc3 — integrated professional multi-pass review. This layer
        # reviews the document as a lawyer would: structure, fact/argument
        # separation, anomaly detection, legal gates, adversarial weaknesses,
        # and prioritized recommendations. It remains fail-closed and never
        # silently rewrites the source document.
        result = apply_professional_review(result, text)
        _case_progress(94, 'PROFESSIONAL_REVIEW', 'Professional review dan adversarial check selesai.')

        # RC18 generalized closure: derive procedural posture and material tempus
        # from source structure/event ownership, then normalize generated
        # projection before readiness and Working Paper rendering.  Regulatory
        # Corpus, official verification, evidence ledgers and source quotations
        # remain untouched.
        result = apply_general_case_orchestration(result, text)

        # Final SAL SSoT refresh after all producers have completed. From this
        # point, working-paper/canonical consumers must use governed pools only.
        from services.sal_source_of_truth import build_governed_pools, enforce_governed_consumers, governed_summary_lines
        build_governed_pools(result)
        enforce_governed_consumers(result)
        from services.adversarial_view import build_adversarial_viewpoint_splitter
        build_adversarial_viewpoint_splitter(result)
        # Final exporter/API projection must use governed pools only.
        result['executive_summary'] = governed_summary_lines(result)
        result['case_readiness'] = readiness_profile(result)
        # v1.3.13.5 — canonical four-part Case Analysis working paper.
        # Backward-compatible case_readiness is retained, while the UI/export
        # uses the merits estimate, evidence correlation matrix, legal construction,
        # and tactical action plan below.
        t0=time.monotonic()
        _case_progress(96, 'WORKING_PAPER', 'Menyusun Case Working Paper dan action plan.')
        result['case_working_paper'] = build_case_working_paper(result)
        # Contract migration V2: attach the canonical 11-stage legal reasoning
        # chain only after all upstream producers (law verification, element
        # mapping, causation, risk, posture, and action planning) are final.
        # This object is then persisted and consumed unchanged by API/UI/export.
        result = attach_reasoning_contract(result)
        # Purely additive: narrates the already-computed result through the
        # explicit 14-step Living Analysis method + critic loop. Does not
        # recompute or alter any field the frozen pipeline above produced.
        result = attach_living_analysis(result)
        # One additional, fail-closed AI call to fill the Living Law /
        # Judicial Realism dimensions no frozen engine currently computes.
        # Never raises; degrades to a clearly-labeled placeholder if AI is
        # unavailable or the response doesn't validate.
        _case_progress(97, 'LIVING_LAW_SYNTHESIS', 'Menyusun analisis Living Law dan Judicial Realism.')
        result = enrich_living_analysis(result, text)
        perf['working_paper']=round((time.monotonic()-t0)*1000)
        _case_progress(98, 'SAVING', 'Menyimpan hasil analisis dan snapshot verifikasi.')
        result['case_analysis_id'] = CaseAnalysisManager.save(result)
        if result.get('case_regulatory_snapshot'):
            result['case_regulatory_snapshot_id'] = CaseRegulatorySnapshotManager.save(
                result['case_analysis_id'], result['case_regulatory_snapshot'])
        if official:
            result['verification_id'] = LegalSourceVerificationManager.save(result['case_analysis_id'], official)
        perf['total']=round((time.monotonic()-request_started)*1000)
        result['performance_timing_ms']=perf
        _case_progress(100, 'COMPLETED', 'Pembacaan dan analisis perkara selesai.')
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
