# LexiCore v1.3.14 RC18 — Consolidated Baseline

This tree consolidates the RC17 full-project baseline with the accepted RC18 corrective work through:

- complete legal verification closure
- integrated official-law verification and secondary legal research
- final verification wiring correction
- provision-text and official-fulltext closure
- reliability corrective batch

Purpose: eliminate patch stacking. Future benchmark/testing should use this single tree as the active baseline.

## Expected benchmark behavior
For the Elya exception benchmark:
- `Pasal yang diperiksa` should no longer be 0 and should be deduplicated per instrument.
- `Pasal yang berhasil diverifikasi` may become >0 when official full text is actually resolved.
- `Tempus terverifikasi` and `Verified applicable` may remain 0 when tempus delicti is not safely established.

## Validation in build environment
- Python compile: PASS
- Structural release audit: PASS
- Targeted positive-law / verification-wiring / reliability tests: 40 PASS

The project remains fail-closed for legal applicability and still requires professional verification.


## RC18 Consolidated Baseline R3
- Based on R2 full project.
- Official representation fallback per instrument identity.
- Direct PDF/download representation priority.
- pypdf + local PyMuPDF deterministic fulltext extraction fallback.
- No feature expansion; verification lifecycle only.

## R6 known-regulation registry closure
- Expanded KNOWN_REGULATION_QUERIES to all DOMAIN_RULES keys.
- 17/18 domains have deterministic known-instrument routes; civil_procedure intentionally remains empty for HIR/RBg integrity.
- Critical BPR/Tipikor tempus query now precedes known-instrument expansion to preserve the max_queries=10 benchmark contract.


## R7 identity/provision telemetry closure
- Official PDF identity normalization hardened without changing number/year.
- Added separate provision text-location telemetry before legal verification.
- Full legal verification remains fail-closed.

## R10 runtime identity diagnostics
R10 adds telemetry-only diagnostics for provisions located in official text but blocked before legal verification. No legal gate is relaxed.

## RC18 R11 consolidated correction
- Isolated source-derived provision provenance from generated research queries.
- Added strict expected-identity fulltext resolution and bounded exact-identity recovery.
- Split official provision text verification from case-bound provision/applicability gates.


## R13 correction
Primary official-document identity must match the expected instrument; referenced/amended instrument identities are diagnostic only.

## R14 case-readiness gate integrity
- Case Readiness no longer improves merely because instrument identity/legal status is verified.
- Legal-readiness uplift requires a regulation to survive case nexus, tempus, and applicability gates; provision bonus remains tied to coherent VERIFIED_APPLICABLE records.
- Prevents transient/false-positive source verification from inflating readiness.

## R15 — Case Analysis Time Budget Closure
- Removed duplicate pre-payload official-source federation from Case Analysis request path.
- Dynamic case-scoped retrieval remains the single authoritative network discovery path.
- Primary federation bounded to 20 seconds.
- Secondary research deferred until after positive-law verification and bounded to 4 seconds.
- Legal gates and fail-closed semantics unchanged.
