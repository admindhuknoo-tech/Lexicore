# LexiCore Assistant — 1.3.14-rc18

Evidence-to-Action Legal Intelligence | ELF - Erfan's Law Firm

## RC18 Reliability Corrective Batch

This corrective batch does **not** add a new legal feature. It hardens three existing core paths while preserving the deterministic `case_reasoning_guard` and `case_consistency_guard` layers:

- SQLite manager calls now have a centralized `db_session()` pattern with rollback/close guarantees for critical Case Analysis, legal-source verification, startup migration, and audit-log paths.
- Gemini configuration diagnostics explicitly expose missing API-key configuration and keep deterministic fallback auditable instead of allowing a late ambiguous failure.
- Full-document AI input is legal-structure-aware and token-budget-aware; synthesis evidence is deduplicated/compacted before the final request.

`services/case_reasoning_guard.py` and `services/case_consistency_guard.py` remain local deterministic guards and do not perform separate LLM calls.

Professional Verification remains PENDING until a lawyer verifies primary documents and applicable positive law.

## RC18 Consolidated Baseline R3
R3 continues from the R2 benchmark without patch stacking. It preserves the per-instrument verification budget while allowing bounded official URL fallbacks (detail/preview/direct PDF) for the same regulation identity, and hardens deterministic official-PDF text extraction. See `AUDIT_REPORT_RC18_BASELINE_R3_OFFICIAL_FULLTEXT_FALLBACK.md`.
