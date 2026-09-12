# Audit Report — Reader Export Final Render Lock v1.2.7

Date: 2026-09-10
Scope: presentation/export only.

## Root cause
The v1.2.6 sanitizer existed in `exporters/common.py`, but two gaps remained at the final render boundary:
1. Some strings could be assembled after the earlier sanitizer pass, so reader-facing cleanup was not guaranteed immediately before PDF/DOCX rendering.
2. Canonical-chain action nodes could contain identical reader-visible `action` text with different metadata. The old dedup fingerprint compared the whole dictionary, so visually duplicated `TINDAKAN:` rows survived.

## Correction
- `present_line()` now performs a final universal presentation cleanup immediately before PDF/DOCX rendering.
- Action fingerprints prefer the reader-visible `action` / `recommendation` / `instruction` field rather than provenance metadata.
- Added a section-specific `_deduplicate_rendered_action_lines()` safety lock. It deduplicates only `TINDAKAN:` lines inside each `RANTAI` in `Rantai Penalaran Hukum Kanonik`; it never deduplicates evidence, issues, sources, or the Action Plan section.
- Added exact reader-facing mappings for observed export residues: `UNKNOWN_DATE`, `case keterkaitan`, `candidate result`, `actual loss`, `outstanding principal`, `intervening act(s)`, `impact`, `existing_N`, `CREDIT/FIDUCIARY/LOSS`, `CREDIT/RESPONSIBILITY`, `seluruh gate`, and `level provisional`.

## Invariants
No change to SAL, Evidence, Elements, Law Retrieval, Candidate Law Governor, Positive-Law Verification, Tempus, persistence, or canonical reasoning data. All corrections are presentation-only.

## Validation
- Python compile: PASS.
- Structural release audit: PASS.
- Targeted reader/export + candidate-law regression: 17 PASS.
- Full non-smoke regression: 394 PASS.
