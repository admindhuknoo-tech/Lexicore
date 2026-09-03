# LexiCore v1.3.5.4 — Regulatory & Full-Document Stabilization

Stabilization release after the v1.3.5.3 benchmark cycle. This release intentionally closes the letter-by-letter corrective branch and addresses the root causes together.

## Full-Document AI
- Per-segment lifecycle trace: `PLANNED -> SENT -> RESPONSE_RECEIVED -> ACCEPTED/REJECTED`.
- Auditable reject reasons: HTTP error, timeout, empty candidate, invalid JSON/schema, empty evidence, synthesis failure.
- Fallback retains real planned/accepted segment counts and failure stage instead of hiding the failure behind `0/N` only.
- More robust JSON extraction, 8192 output-token ceiling, and two retries by default.

## Regulatory precision
- Added case domains for land/property, civil procedure, and Religious Court/absolute jurisdiction.
- Hard relevance gating suppresses weak incidental domains.
- Local regulatory seed matches are filtered to active case domains before Case Analysis and Norm Conflict output.
- Norm Conflict is recomputed after the relevance gate.
- Orphan article references including `Pasal N ayat (...)` are removed from applicable-law export unless qualified by an instrument.

## Date / tempus
- OCR split dates such as `2 6 Februari 2026` normalize to `26 Februari 2026`.
- Dates are classified as material event, procedural/filing, historical record, regulation date, or unknown.
- Filing dates are not automatically promoted to the material tempus date.
- BAP credit benchmark continues to prefer the transaction date (27 September 2022).

## Database
No schema migration. `schema_version` remains 3.

## Release gate
Run `release_check.bat`. Do not freeze the regulatory architecture until the release gate passes and both benchmark classes are retested.
