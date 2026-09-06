# LexiCore v1.3.14-rc6 — Professional Output Architecture

## Implemented
- Replaced lawyer-facing "probabilitas kemenangan" with **Case Readiness / Analysis Completeness**. The internal compatibility key `working_paper_percentage` remains, but its metric is now `CASE_ANALYSIS_READINESS`.
- Added **Executive Legal Review** as the first substantive export section, derived from Professional Review findings and strategic recommendations.
- Added privacy-compact case context for PDF/DOCX: obvious NIK/KTP-like numbers, phone numbers, emails, and representation/address boilerplate are not projected into the lawyer-facing context. Raw source remains internal for traceability.
- Preserved Evidence Map fail-closed semantics and material-source separation.
- Translated regulatory/tempus internal statuses into lawyer-facing language in exports.
- Added sentence-safe clipping to Executive Summary so analysis text is not cut in the middle of a sentence.
- Legal-only disclaimer remains mandatory; no medical-domain disclaimer exists in the project output path.
- UI Case Analysis now labels the first working-paper tab as **Case Readiness** and shows an Executive Legal Review before detailed construction.

## Validation performed in build environment
- Python compileall: PASS
- Inline JavaScript syntax (`node --check`): PASS
- Structural release audit: PASS
- Targeted Case Readiness semantic check: PASS (`CASE_ANALYSIS_READINESS`)
- Targeted privacy-context check: PASS (NIK / phone / email excluded; material case narrative retained)
- Targeted Executive Legal Review ordering check: PASS
- Medical-disclaimer leakage check: PASS

## Environment limitation
Full Flask `pytest` cannot be executed in this build environment because Flask is not installed. Final release gate remains `release_check.bat` on the user's Windows environment.
