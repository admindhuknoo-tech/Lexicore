# LexiCore Reader Export Final Sanitizer & Deduplicator v1.2.6

Scope: presentation/export only. No changes to SAL, Evidence, Elements, Tempus, Candidate Law Governor, retrieval, persistence, or canonical reasoning semantics.

## Changes
- Extended reader-facing terminology cleanup in `exporters/common.py` for: Local Deterministic, Evidence-to-Action, retrieval sumber hukum, case keterkaitan, candidate result, actual loss, intervening acts, outstanding principal, and bounded impact/exposure/recovery phrases.
- Added key-scoped action deduplication. Only explicit action/recommendation nodes are deduplicated; generic evidence/issue/source lists are never deduplicated.
- Added direct deduplication of `recommended_action.actions` before canonical chain rendering, preventing repeated TINDAKAN lines while preserving canonical payload contents.
- No `eval()`, no stringification of structured action objects, and no global list deduplication.

## Validation
- Python compile: PASS.
- Structural release audit: PASS (`v1.3.14-rc18`, templates=43, regulations=48).
- Targeted presentation + candidate-law regression: 19 passed.
- Full non-smoke regression: 389 passed.
- Full smoke suite was not run in this container because Flask is not installed; local Windows `release_check.bat` remains the authoritative smoke/OCR gate.

## Freeze decision
v1.2.6 is presentation-only. Existing core contract freezes remain unchanged.
