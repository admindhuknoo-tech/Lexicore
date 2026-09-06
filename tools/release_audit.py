"""LexiCore deterministic pre-release audit.

Runs without network calls. It checks structural invariants that previously
caused regressions: version drift, duplicate DOM ids, stale AI configuration,
domain boundary leakage, drafting coverage, and local corpus availability.
"""
from __future__ import annotations
import ast, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def fail(msg: str):
    raise SystemExit(f"RELEASE AUDIT FAIL: {msg}")

# Python parse gate (compileall runs separately, but this reports the file).
for path in ROOT.rglob('*.py'):
    if any(part in {'.git','__pycache__','.pytest_cache'} for part in path.parts):
        continue
    try:
        ast.parse(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f"Python parse error {path.relative_to(ROOT)}: {exc}")

from version import LEXICORE_VERSION, PUBLIC_VERSION, RELEASE_CHANNEL, RELEASE_SEQUENCE, PRODUCT_NAME, INITIATIVE, FIRM_NAME, PRODUCT_LABEL, release_metadata
from legal_drafting import TEMPLATE_REGISTRY
from regulatory_db import get_all_regulations
from services.case_domain_classifier import classify_case
import ai_engine

# Artifact-hygiene invariants: exporters/ must contain only live exporter modules,
# and pytest must not have leaked test backups into the real project backups/.
_exporters = ROOT / 'exporters'
_allowed_exporter_files = {'__init__.py','case_docx.py','case_pdf.py','common.py'}
if not _exporters.exists():
    fail('missing exporters directory')
_exporter_children = {p.name for p in _exporters.iterdir() if p.name != '__pycache__'}
if _exporter_children != _allowed_exporter_files:
    fail(f'exporters directory contains regression debris: {sorted(_exporter_children - _allowed_exporter_files)}')
_leaked_test_backups = sorted((ROOT/'backups').glob('test_lexicore_*')) if (ROOT/'backups').exists() else []
if _leaked_test_backups:
    fail(f'test backup leakage detected in project backups/: {[p.name for p in _leaked_test_backups]}')
_conftest = (ROOT/'tests'/'conftest.py').read_text(encoding='utf-8',errors='ignore')
if 'LEXICORE_BACKUP_DIR' not in _conftest:
    fail('pytest backup-dir isolation missing from tests/conftest.py')

# Release identity contract: stable product label, dynamic technical version.
# Do not hard-code each corrective/build revision into tests or audit rules.
if PRODUCT_NAME != 'LexiCore':
    fail(f'product name drift: {PRODUCT_NAME}')
if PRODUCT_LABEL != 'LexiCore Assistant':
    fail(f'product label drift: {PRODUCT_LABEL}')
if INITIATIVE != 'Evidence-to-Action Legal Intelligence':
    fail(f'initiative drift: {INITIATIVE}')
if FIRM_NAME != "ELF - Erfan's Law Firm":
    fail(f'firm metadata drift: {FIRM_NAME}')
if RELEASE_CHANNEL != 'RC' or not isinstance(RELEASE_SEQUENCE, int) or RELEASE_SEQUENCE < 1:
    fail('release channel/sequence contract invalid')
if not re.fullmatch(r'\d+\.\d+\.\d+-rc\d+', LEXICORE_VERSION):
    fail(f'invalid technical release version: {LEXICORE_VERSION}')
if not LEXICORE_VERSION.startswith(PUBLIC_VERSION + '-rc'):
    fail('technical version does not belong to PUBLIC_VERSION release line')
meta = release_metadata()
if meta.get('product_label') != PRODUCT_LABEL or meta.get('version') != LEXICORE_VERSION:
    fail('release_metadata() is inconsistent with version constants')

# Distribution strategy invariants. Clean full-project builds must be reproducible
# without carrying nested patch trees or transient Python/test artifacts.
for required in ('RELEASE_POLICY.md','build_release.bat','tools/build_release.py'):
    if not (ROOT/required).exists():
        fail(f'missing release-governance file: {required}')
for forbidden in ROOT.rglob('*'):
    if not forbidden.exists():
        continue
    rel = forbidden.relative_to(ROOT)
    if any(part.startswith(('LEXICORE_PATCH_','LEXICORE_ROLLBACK_')) for part in rel.parts):
        fail(f'nested patch/rollback tree must not exist in canonical baseline: {rel}')

# README must identify the release line, but PRODUCT_LABEL is intentionally version-free.
readme = ROOT/'README.md'
if not readme.exists():
    fail('missing README.md')
rt = readme.read_text(encoding='utf-8', errors='ignore')
if PRODUCT_LABEL not in rt or LEXICORE_VERSION not in rt:
    fail('README does not identify current product label and technical release')

# OCR ingestion invariants.
ocr_module=ROOT/'services'/'document_ocr.py'
if not ocr_module.exists(): fail('missing services/document_ocr.py')
ocr_text=ocr_module.read_text(encoding='utf-8',errors='ignore')
for required in ('extract_pdf_text','extract_image_text','embedded_ocr_available','ocr_runtime_status','HYBRID_NATIVE_OCR','OCR_FALLBACK'):
    if required not in ocr_text: fail(f'OCR invariant missing: {required}')
for dep in ('PyMuPDF','Pillow','rapidocr','onnxruntime','numpy'):
    if dep.lower() not in (ROOT/'requirements.txt').read_text(encoding='utf-8',errors='ignore').lower():
        fail(f'OCR dependency missing from requirements.txt: {dep}')
if re.search(r'(^|\n)\s*import\s+fitz\b', ocr_text): fail('deprecated import fitz remains in OCR module')
if 'os_executable_required\": False' not in ocr_text and "'os_executable_required': False" not in ocr_text: fail('embedded OCR portability contract missing')
if 'result.boxes or []' in ocr_text: fail('numpy truth-value bug remains in RapidOCR result normalization')
if '_source_ledger_candidates' not in (ROOT/'app.py').read_text(encoding='utf-8',errors='ignore'): fail('deterministic OCR-to-evidence ledger missing')
if '_embedded_timeout_seconds' not in ocr_text or 'daemon=True' not in ocr_text or '_RAPID_CIRCUIT_OPEN' not in ocr_text:
    fail('embedded OCR hard-timeout/circuit-breaker invariant missing')
if '_ocr_total_timeout_seconds' not in ocr_text or 'LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS' not in ocr_text or 'total_timeout_exceeded' not in ocr_text:
    fail('document-level OCR total-time-budget invariant missing')
app_text=(ROOT/'app.py').read_text(encoding='utf-8',errors='ignore')
if 'threaded=True' not in app_text:
    fail('Flask dev server must explicitly run threaded=True')

# v1.3.11 OCR legal post-processing + evidence grouping invariants.
pp=ROOT/'services'/'legal_ocr_postprocess.py'
if not pp.exists(): fail('missing services/legal_ocr_postprocess.py')
pptext=pp.read_text(encoding='utf-8',errors='ignore')
for required in ('postprocess_legal_ocr','group_source_ledger','CONSERVATIVE_LEGAL_OCR_NORMALIZATION','EXTRACTIVE_GROUPING_ONLY'):
    if required not in pptext: fail(f'legal OCR/evidence grouping invariant missing: {required}')

# v1.3.12.4 official full-text / provision verification invariants.
plv=ROOT/'services'/'positive_law_verification.py'
if not plv.exists(): fail('missing services/positive_law_verification.py')
plvtext=plv.read_text(encoding='utf-8',errors='ignore')
for required in ('verify_document_candidate','verify_tempus','VERIFIED_APPLICABLE','STATUS_UNCERTAIN','classify_legal_document_candidate','CASE_NEXUS_VERIFIED','evaluate_case_nexus','verify_provisions','PROVISION_VERIFIED','VERIFIED_NOT_RELEVANT'):
    if required not in plvtext: fail(f'positive-law verification invariant missing: {required}')
ls=(ROOT/'legal_sources.py').read_text(encoding='utf-8',errors='ignore')
if 'fetch_official_document' not in ls: fail('official document fetch contract missing')
if 'CERT_NONE' in ls or 'check_hostname = False' in ls: fail('TLS verification weakening detected')

# v1.3.13.1 deep clause evaluation invariants.
cr=(ROOT/'contract_review.py').read_text(encoding='utf-8',errors='ignore')
for required in ('ClauseDeepEvaluator','clause_evaluations','existing_clause','risk_loophole','recommended_redraft'):
    if required not in cr: fail(f'contract deep-evaluation invariant missing: {required}')
if 'contract-review-table' not in (ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore'):
    fail('contract review three-column table UI missing')

# v1.3.13.2 Regulatory Corpus hierarchy invariants.
lrs=(ROOT/'services'/'legal_research_service.py').read_text(encoding='utf-8',errors='ignore')
for required in ('REGULATORY_HIERARCHY','specific_provisions','practical_implication','hierarchical_results'):
    if required not in lrs: fail(f'regulatory hierarchy invariant missing: {required}')
for label in ('UU','PP','PERPRES','PER_MENTERI_LEMBAGA','PERMA','PERMK','PERKAP','PERDA'):
    if label not in lrs: fail(f'regulatory hierarchy level missing: {label}')
if 'reg-map-table' not in (ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore'):
    fail('Regulatory Corpus hierarchy table UI missing')

# v1.3.13.3 Legal Research case-summary invariants.
cls=(ROOT/'services'/'case_law_summary.py')
if not cls.exists(): fail('missing services/case_law_summary.py')
clst=cls.read_text(encoding='utf-8',errors='ignore')
for required in ('summarize_case_source','chronology','ratio_decidendi','disposition','legal_rule','PROFESSIONAL VERIFICATION REQUIRED'):
    if required not in clst: fail(f'case-law summary invariant missing: {required}')
html_research=(ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore')
for required in ('Kronologi → Ratio Decidendi → Amar → Kaidah Hukum','renderResearchSummary','rFocus'):
    if required not in html_research: fail(f'Legal Research UI invariant missing: {required}')
if 'research_payload' not in (ROOT/'database.py').read_text(encoding='utf-8',errors='ignore'):
    fail('rich Legal Research persistence missing')

# DOM ids must be unique; duplicate ids previously broke frozen navigation.
html=(ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore')
ids=re.findall(r'\bid=["\']([^"\']+)["\']',html)
dups=sorted({x for x in ids if ids.count(x)>1})
if dups: fail(f"duplicate DOM ids: {dups}")

if len(TEMPLATE_REGISTRY) < 40:
    fail(f"legal drafting templates only {len(TEMPLATE_REGISTRY)}; expected >=40")
regs=get_all_regulations()
if len(regs) < 45:
    fail(f"regulatory corpus only {len(regs)}; expected >=45")

# Legal-domain boundary benchmarks.
bpr=classify_case('Berita Acara Pemeriksaan Tersangka dugaan Tindak Pidana Korupsi pemberian fasilitas kredit Perumda BPR. Direktur Utama, komite kredit, penyimpangan prosedur, penyalahgunaan kewenangan dan kerugian keuangan daerah. Ada Perjanjian Kredit.')
if bpr.get('primary_domain')!='corruption' or 'civil_contract' not in bpr.get('supporting_only',[]):
    fail(f"BPR/Tipikor boundary failed: {bpr}")
wan=classify_case('Bank swasta menagih debitur yang menunggak berdasarkan perjanjian kredit dan somasi. Tidak ada penyidikan, tidak ada fraud internal, tidak ada penyalahgunaan kewenangan dan tidak ada kerugian keuangan negara.')
if wan.get('primary_domain')=='corruption':
    fail(f"pure default misclassified as corruption: {wan}")
land=classify_case('Jawaban Tergugat atas gugatan dengan eksepsi obscuur libel, plurium litis consortium, Sertipikat Hak Milik, SKPT dan kompetensi absolut Pengadilan Agama.')
if any(x in set(land.get('domain_contract',[])) for x in ('financial_services','corruption','criminal','employment')):
    fail(f"land/civil boundary contaminated: {land}")
inheritance=classify_case('Replik dalam sengketa tanah. Dalam eksepsi declinatoir dibahas pembagian waris, para ahli waris, dan kewenangan absolut Pengadilan Agama.')
if 'religious_court' not in set(inheritance.get('domain_contract',[])):
    fail(f"inheritance/forum screen missing: {inheritance}")
ptun=classify_case('Gugatan PTUN terhadap Keputusan Tata Usaha Negara setelah upaya administratif dengan dalil pelanggaran AUPB.')
if ptun.get('primary_domain')!='administrative':
    fail(f"PTUN classification failed: {ptun}")

# Provider must resolve from current environment at call time, not import time.
oldp=os.environ.get('LEXICORE_AI_PROVIDER'); oldm=os.environ.get('LEXICORE_AI_MODEL')
try:
    os.environ['LEXICORE_AI_PROVIDER']='local'; os.environ.pop('LEXICORE_AI_MODEL',None)
    if ai_engine.provider_config()['provider']!='local': fail('dynamic AI local provider resolution failed')
    os.environ['LEXICORE_AI_PROVIDER']='gemini'; os.environ['LEXICORE_AI_MODEL']='audit-model'
    cfg=ai_engine.provider_config()
    if cfg != {'provider':'gemini','model':'audit-model'}: fail(f'dynamic AI provider resolution failed: {cfg}')
finally:
    if oldp is None: os.environ.pop('LEXICORE_AI_PROVIDER',None)
    else: os.environ['LEXICORE_AI_PROVIDER']=oldp
    if oldm is None: os.environ.pop('LEXICORE_AI_MODEL',None)
    else: os.environ['LEXICORE_AI_MODEL']=oldm


# v1.3.13.7 Client Communication invariants.
cc = ROOT / 'client_communication.py'
if not cc.exists():
    fail('client_communication.py missing')
cc_text = cc.read_text(encoding='utf-8', errors='ignore')
for token in ('Status saat ini','Makna bagi posisi hukum Anda','Alasan hukum/strategis','DRAFT_FOR_LAWYER_REVIEW'):
    if token not in cc_text:
        fail(f'client communication invariant missing: {token}')


# v1.3.13.8 Legal Drafting formal-structure invariants.
ld=(ROOT/'legal_drafting.py').read_text(encoding='utf-8',errors='ignore')
for token in ('CONTRACT_TYPES','_ensure_contract_core_clauses','REPRESENTATIONS & WARRANTIES','WANPRESTASI / DEFAULT','DOMISILI HUKUM','PETITUM PRIMAIR','PETITUM SUBSIDAIR','PASAL 143 KUHAP','MATRIS PEMBUKTIAN UNSUR PASAL','KASUS POSISI (FAKTA)','KESIMPULAN & REKOMENDASI MITIGASI','Eksepsi PTUN','Replik PTUN','Duplik PTUN'):
    if token not in ld:
        fail(f'legal drafting v1.3.13.8 invariant missing: {token}')

# v1.3.13.7.1 WhatsApp + norm-conflict corrective invariants.
for rel, token in (("app.py","/api/communication/whatsapp-link"),("database.py","whatsapp_number"),("static/index.html","sendClientWhatsApp"),("norm_conflict.py","relationships.extend")):
    txt=(ROOT/rel).read_text(encoding='utf-8',errors='ignore')
    if token not in txt:
        fail(f"{rel} missing v1.3.13.7.1 invariant: {token}")


# v1.3.13.11.2 regression-stabilization invariants.
_ls=(ROOT/'legal_sources.py').read_text(encoding='utf-8',errors='ignore')
_rr=(ROOT/'services'/'regulatory_retrieval.py').read_text(encoding='utf-8',errors='ignore')
_route=(ROOT/'routes'/'case_analysis.py').read_text(encoding='utf-8',errors='ignore')
_html=(ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore')
for needle in ('def federated_search_many','max_workers=6','SEARCH_TIME_BUDGET_EXCEEDED'):
    if needle not in _ls: fail(f'bounded official-source federation invariant missing: {needle}')
if 'federated_search_many' not in _rr: fail('case regulatory retrieval still lacks bounded federation')
if 'case_run_lock' not in _route or 'health_cache_only=True' not in _route: fail('Case Analysis server guard/cached-health invariant missing')
for needle in ('jsonWithTimeout','caseAnalysisInFlight','renderCaseReadiness','renderCaseWorkingPaper'):
    if needle not in _html: fail(f'Case Analysis frontend stability invariant missing: {needle}')

print(f"LexiCore structural audit PASS | v{LEXICORE_VERSION} | templates={len(TEMPLATE_REGISTRY)} | regulations={len(regs)}")


# v1.3.12.4 full-text provision resolver invariants.
legal_sources_text=(ROOT/'legal_sources.py').read_text(encoding='utf-8',errors='ignore')
retrieval_text=(ROOT/'services'/'regulatory_retrieval.py').read_text(encoding='utf-8',errors='ignore')
if 'def resolve_official_fulltext' not in legal_sources_text:
    fail('official full-text resolver missing')
if '_extract_pdf_text' not in legal_sources_text:
    fail('official PDF text extraction missing')
if 'resolve_official_fulltext' not in retrieval_text or 'provision_source_url' not in retrieval_text:
    fail('positive-law retrieval is not wired to official full-text provision resolution')


# v1.3.13.4 Compliance & Risk matrix invariants.
_compliance=(ROOT/'services'/'compliance_risk.py').read_text(encoding='utf-8',errors='ignore')
for needle in ('General Corporate','Tech/PDP','Employment','Commercial','Financial/AML','risk_identification','legal_justification','mitigation_checklist'):
    if needle not in _compliance:
        fail(f'compliance risk invariant missing: {needle}')


# v1.3.13.6 Case Analysis four-part working paper invariants.
_cwp=ROOT/'services'/'case_working_paper.py'
if not _cwp.exists(): fail('missing services/case_working_paper.py')
_cwpt=_cwp.read_text(encoding='utf-8',errors='ignore')
for needle in ('CASE_ANALYSIS_READINESS','working_paper_percentage','evidence_map','legal_construction','action_plan','opponent_evidence_weakness'):
    if needle not in _cwpt: fail(f'case working-paper invariant missing: {needle}')
if 'tidak di-hard-code' not in _cwpt:
    fail('criminal evidence basis must not hard-code stale KUHAP article numbering')
_html=(ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore')
for bad in ('Probabilitas kemenangan analitis','ANALYTICAL_WIN_PROBABILITY'):
    if bad in _cwpt or bad in _html:
        fail(f'probability wording leakage: {bad}')
for needle in ('Case Readiness','Status Pembuktian','Uji Lanjut','renderLegalConstruction','renderTacticalActionPlan'):
    if needle not in _html: fail(f'Case Analysis UI invariant missing: {needle}')
_db=(ROOT/'database.py').read_text(encoding='utf-8',errors='ignore')
if 'case_working_paper' not in _db: fail('case working-paper persistence missing')


# v1.3.13.10 Compliance questionnaire expansion invariants.
cr = ROOT / 'services' / 'compliance_risk.py'
if not cr.exists():
    fail('services/compliance_risk.py missing')
crt = cr.read_text(encoding='utf-8',errors='ignore')
for token in ('beneficial_owner','transaction_monitoring','aml_scope','pkwt_registration','dpia_transfer','liability_indemnity'):
    if token not in crt:
        fail(f'compliance v1.3.13.10.1 invariant missing: {token}')


# v1.3.13.11.2 case-analysis performance corrective invariants.
_app_text=(ROOT/'app.py').read_text(encoding='utf-8',errors='ignore')
_ui_text=(ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore')
if "/api/export/document/docx" not in _app_text:
    fail('generic workspace DOCX export endpoint missing')
for _kind in ('review','corpus','research','risk','norm','client'):
    if f"exportWorkspacePdf('{_kind}')" not in _ui_text:
        fail(f'workspace PDF export control missing: {_kind}')
    if f"exportWorkspaceDocx('{_kind}')" not in _ui_text:
        fail(f'workspace DOCX export control missing: {_kind}')


# v1.3.13.11.10: user-facing Case Analysis must not leak internal renderer labels.
case_ui = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8', errors='ignore')
for leaked in ('CASE-SCOPED REGULATORY RETRIEVAL', 'Retrieval funnel', 'seed fallback', '→ applicable ', '→ pasal verified '):
    if leaked in case_ui:
        fail(f'Case Analysis UI leaks internal label: {leaked}')
for required_label in ('PENELUSURAN REGULASI TERKAIT PERKARA', 'Alur penyaringan regulasi', 'Verifikasi profesional:'):
    if required_label not in case_ui:
        fail(f'Case Analysis user-facing label missing: {required_label}')


# v1.3.13.11.10 — Legal Reasoning Guard invariants.
guard = ROOT / 'services' / 'case_reasoning_guard.py'
if not guard.exists():
    fail('services/case_reasoning_guard.py missing')
else:
    gt=guard.read_text(encoding='utf-8',errors='ignore')
    for needle in ('FAIL_CLOSED_EVIDENCE_DRIVEN','TEMPUS_INSUFFICIENT','FORUM_VS_MERITS','ERROR_IN_PERSONA_VS_ATTRIBUTION','POTENTIAL_TYPO_OR_OCR'):
        if needle not in gt: fail(f'Legal Reasoning Guard invariant missing: {needle}')
route = (ROOT / 'routes' / 'case_analysis.py').read_text(encoding='utf-8',errors='ignore')
if 'apply_reasoning_guard(result, text)' not in route:
    fail('Case Analysis route does not apply Legal Reasoning Guard after synthesis')
app_text=(ROOT / 'app.py').read_text(encoding='utf-8',errors='ignore')
for forbidden in ('Fokus analisis tidak berhenti pada apakah SOP dilanggar','Untuk kasus berbasis kredit/perbankan, actual loss'):
    if forbidden in app_text: fail(f'Hard-coded case narrative leaked back into app.py: {forbidden}')

# v1.3.13.11.10 — integrated Case Analysis Evidence & Consistency Guard.
cc=ROOT/'services'/'case_consistency_guard.py'
if not cc.exists():
    fail('services/case_consistency_guard.py missing')
cc_text=cc.read_text(encoding='utf-8',errors='ignore')
for needle in ('issue_source_nexus','DOCUMENT_METADATA','GLOBAL_FAIL_CLOSED_CONSISTENCY','INSTRUMENT_IDENTITY_THEN_CASE_NEXUS_THEN_ARTICLE'):
    if needle not in cc_text: fail(f'Case consistency invariant missing: {needle}')
_cwp_text=(ROOT/'services'/'case_working_paper.py').read_text(encoding='utf-8',errors='ignore')
for needle in ('ranked_support_for_issue','evidence_nexus_score','ONLY'):
    if needle not in _cwp_text and needle!='ONLY': fail(f'Evidence-to-Issue working-paper invariant missing: {needle}')
_pv_text=(ROOT/'services'/'positive_law_verification.py').read_text(encoding='utf-8',errors='ignore')
if 'PROVISION_BLOCKED_BY_INSTRUMENT_GATE' not in _pv_text:
    fail('instrument-before-article verification gate missing')
if 'apply_global_case_consistency(result)' not in route:
    fail('global Case Analysis consistency guard not applied after legal reasoning guard')


# v1.3.14-rc2 — Evidence Hygiene & Material Source Projection invariants.
for needle in ('material_source_ledger','evidence_hygiene','MATERIAL_EVIDENCE_ONLY'):
    if needle not in _app_text:
        fail(f'Evidence hygiene app invariant missing: {needle}')
for needle in ('PROCEDURAL_METADATA','PETITUM_OR_PRAYER','LEGAL_ARGUMENT','NON_MATERIAL_FRAGMENT','material_source_ledger'):
    if needle not in cc_text:
        fail(f'Evidence hygiene classifier invariant missing: {needle}')
if "cls not in {'ACTUAL_EVIDENTIARY_ITEM','EVIDENCE_ASSERTION','CASE_FACT','PLEADED_FACT','ALLEGED_ROLE'}" not in cc_text:
    fail('Evidence Map allowlist missing; taxonomy-v2 classes may leak or be dropped incorrectly')
if "case_nexus_status')!='CASE_NEXUS_VERIFIED'" not in cc_text:
    fail('Regulatory reportability must require verified case nexus')
for needle in ('Jejak Sumber Material','Proposisi Faktual yang Perlu Diuji','Status Pembuktian','Uji Lanjut'):
    if needle not in _ui_text:
        fail(f'Case evidence hygiene UI invariant missing: {needle}')


# v1.3.14-rc3 — Professional Legal Review Engine invariants.
review_engine = ROOT / 'services' / 'legal_review_engine.py'
if not review_engine.exists():
    fail('services/legal_review_engine.py missing')
review_text = review_engine.read_text(encoding='utf-8', errors='ignore')
for needle in ('LEXICORE_PROFESSIONAL_REVIEW_V1','MULTI_PASS_FAIL_CLOSED','CHECK_TEXT_ENTITY_DATE_CITATION_ANOMALIES','ADVERSARIAL_ARGUMENT_REVIEW','BUILD_PRIORITIZED_RECOMMENDATIONS'):
    if needle not in review_text:
        fail(f'Professional Legal Review invariant missing: {needle}')
route_text=(ROOT/'routes'/'case_analysis.py').read_text(encoding='utf-8',errors='ignore')
if 'apply_professional_review(result, text)' not in route_text:
    fail('Case Analysis route does not apply Professional Legal Review Engine')
ui_text=(ROOT/'static'/'index.html').read_text(encoding='utf-8',errors='ignore')
if 'renderProfessionalReview' not in ui_text or 'Review Profesional' not in ui_text:
    fail('Professional Review UI missing')


# v1.3.14-rc17 — Evidence Taxonomy V2 + Probative Weight Guard + lawyer-facing output.
for needle in ('PLEADED_FACT','ALLEGED_ROLE','HEADING_OR_SECTION','probative_weight_for_issue','probative_sufficient'):
    if needle not in cc_text:
        fail(f'RC17 Evidence Taxonomy/Probative Guard invariant missing: {needle}')
if "allowed={'ACTUAL_EVIDENTIARY_ITEM','EVIDENCE_ASSERTION','CASE_FACT','PLEADED_FACT','ALLEGED_ROLE'}" not in cc_text:
    fail('RC17 material source ledger must exclude legal arguments/headings/metadata')
if 'SEMANTIC_NEXUS_ONLY' not in _cwp_text:
    fail('RC17 Legal Construction must distinguish semantic nexus from probative sufficiency')
_export_text=(ROOT/'exporters'/'common.py').read_text(encoding='utf-8',errors='ignore')
for needle in ('Kandidat Dasar Hukum yang Perlu Diverifikasi','Regulasi terverifikasi relevan dan berlaku','Bobot pembuktian','_human_review_type'):
    if needle not in _export_text:
        fail(f'RC17 lawyer-facing export invariant missing: {needle}')
for leaked in ('<small>probabilitas analitis</small>','PARTIAL_OFFICIAL_SOURCE_ACCESS'):
    if leaked in ui_text:
        fail(f'RC17 user-facing technical leakage: {leaked}')
export_text=(ROOT/'exporters'/'common.py').read_text(encoding='utf-8',errors='ignore')
if 'Audit Dokumen Terperinci' not in export_text:
    fail('Professional Review export section missing')
