# LexiCore v1.3.14 RC18 — Posture / Tempus / Norm Single-Source Integration Closure

## Objective
Close the three remaining integration leaks observed in the 2026-09-09 DKPP benchmark without introducing parallel reasoning architecture or case-name hardcoding.

## Architectural decisions
1. **Canonical document posture**
   - Added `services/document_posture_resolver.py` as the single generated-posture resolver.
   - Structural document markers remain authoritative for document role.
   - Existing additive `ranah_hukum` / `posisi_pengguna` fields only refine labels when compatible with structural posture.
   - No DKPP/waris/Tipikor case-name branch is used.
   - `services/legal_review_engine.py` now consumes this resolver before structural review and strategy generation.
   - Existing machine-facing `document_structure.document_type` is preserved for compatibility; `display_document_type` is the canonical human-facing projection.
   - `exporters/common.py` uses `display_document_type` first so a response document no longer exports as an Eksepsi merely because an older enum exists.

2. **Single material-tempus selection before verification**
   - `routes/case_analysis.py` computes `select_material_tempus(text)` once before regulatory retrieval.
   - The selection is stored as `result.material_tempus` and passed to `retrieve_for_case_dynamic(...)`.
   - `services/regulatory_retrieval.py` reuses that exact selection for `event_date_candidate` / `event_year_candidate` and positive-law verification snapshot.
   - Extraction remains fail-closed and does **not** itself mark a norm applicable.
   - The regulatory snapshot retains `material_tempus` and selection basis for runtime auditability.

3. **Material norm-conflict gate**
   - Existing canonical `norm_conflict.py` was corrected instead of creating a second resolver module.
   - The word `bertentangan` in a factual allegation no longer creates an antinomy between every pair of regulations.
   - Conflict rows now require both `same_subject_matter` and `antinomy_identified`.
   - Explicitly negated conflict statements are ignored.
   - When no material antinomy exists, output is `NO_MATERIAL_NORM_CONFLICT_IDENTIFIED` with zero conflict rows.

4. **General orchestration compatibility**
   - `services/general_case_orchestrator.py` delegates posture resolution to the canonical resolver.
   - It reuses already-computed `material_tempus` rather than re-running a separate selection after positive-law verification.
   - Source/evidence ledgers and official verification records are never rewritten.

## Validation
- Python compile on all changed Python modules: PASS.
- Focused posture/tempus/norm integration suite: PASS.
- Existing generalized-case, Tempus contract, R30 scope, generalization-matrix, and R31 cross-domain tests: PASS.
- Full non-Flask suite: **197 passed**.
- Full Windows `release_check.bat` remains authoritative because this Linux validation environment does not have Flask installed.

## Expected runtime acceptance
For the DKPP benchmark:
- Executive/Audit document label should be `Jawaban atas Pengaduan Etik` (not `Eksepsi / nota keberatan`).
- Generated strategy must not mention `surat dakwaan` unless the source actually establishes a criminal pleading posture.
- `case_regulatory_snapshot.material_tempus` and `event_date_candidate` must use the same canonical Tempus selection.
- Positive-law verification may only increase `tempus_verified` when the canonical material date and official effective-date evidence satisfy the existing verification gate.
- Norm Conflict export should show no repeated pseudo-conflict rows when no material antinomy is identified.
