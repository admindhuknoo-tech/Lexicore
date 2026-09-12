# Audit Report — Pleading Semantic Cleaner + Reader Terminology v1.2.2

Date: 2026-09-10
Baseline: LexiCore V2.3.1 + Law Weight Config v1.2.1
Scope: non-core quality and presentation layers only.

## Changes

1. `extractors/pleading_cleaner.py`
   - Detects Replik/Repliek, Duplik/Dupliek, Jawaban, and Gugatan civil pleading posture.
   - Provides bounded semantic overrides only for strong procedural-filing and civil-argument patterns.
   - Uses existing SAL v1.0 semantic types only; no schema extension.
   - Adds safe recursive reader-facing strategy sanitization without `eval`.
2. `services/semantic_admission.py`
   - Adds civil pleading semantic-quality hint before generic typing.
   - Propagates a `CIVIL_PLEADING` context marker into the temporary typing source used for ledger enrichment.
3. `services/document_posture_resolver.py`
   - Adds OCR/orthographic tolerance for `repliek`/`dupliek` while preserving the posture resolver as SSoT.
4. `exporters/terminology_mapper.py`
   - Cleans section 13 internal English/code vocabulary and section 14 leaked variable names.
5. `exporters/common.py`
   - Applies presentation-only civil strategy sanitization and terminology mapper.

## Explicit non-changes

- No Law Engine change.
- No Positive-Law Verifier or Tempus change.
- No Evidence admission change.
- No Legal Elements ownership change.
- No identity/adversarial fingerprinting change.
- No canonical reasoning structure change.
- No SAL schema change.

## Safety corrections to proposed draft

- `eval(strategy_str)` was not used. Recursive type-preserving sanitization is used instead.
- `epistemic_status` was not injected as a new key into the frozen SAL semantic envelope.
- Token-level replacement of generic words such as `act` was avoided; only bounded phrases are translated.
- Civil strategy substitutions are presentation-only and activate only when the resolved reader domain is PERDATA.

## Verification

- `python -m py_compile` on changed modules/tests: PASS.
- Targeted backlog/reader tests: 22 PASS.
- Full non-smoke regression suite: 370 PASS.
- `tests/test_smoke.py` intentionally excluded because it is environment-dependent; no full-smoke claim is made.


## Release-audit corrective note
`exporters/terminology_mapper.py` was removed because `tools/release_audit.py` freezes `exporters/` to `__init__.py`, `case_docx.py`, `case_pdf.py`, and `common.py`. The two presentation-only helper functions were consolidated into `exporters/common.py`; behavior and core contracts are unchanged.
