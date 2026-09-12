# LexiCore SAL v1.0 — Cross-Layer Enforcement Migration

Date: 2026-09-10
Baseline: SAL v1.0 Portable Validator Corrective
Scope: final upstream-to-downstream contract enforcement; no core reasoning redesign.

## Why this migration exists

The 11:02 LELY benchmark showed that SAL typing itself was already correct, but downstream consumers could still re-promote a `LEAD_ONLY` document reference into Evidence/Alleged Act, and retrieved law from an unrelated specialist domain could still appear as Candidate Law. This release makes SAL routing binding across layers rather than advisory metadata.

## Changes

1. Added `services/contract_enforcer.py` as a deterministic cross-layer enforcer. It does not classify law substantively and does not create a parallel reasoning pipeline.
2. SAL payload construction now passes through route enforcement before schema validation.
3. `route_allowed()` delegates to the binding contract enforcer whenever a SAL envelope exists.
4. Short evidence references such as `bukti kerugian` are typed as `DOCUMENT_REFERENCE` and therefore remain `LEAD_ONLY`; they cannot become Evidence or Alleged Act.
5. Canonical chain Evidence consumer resolves `source_index` back to the SAL-enriched source ledger and refuses any source for which `Evidence Map` is prohibited.
6. Law subject-matter admission is generalized across specialist families (HKI, Pertambangan, Pertanahan, Ketenagakerjaan, Kepailitan, Pidana). A clearly specialist source is rejected when its subject matter is absent from the active case/issue context.
7. The optional user proposal was not copied literally. In particular, no hard-coded `civil => reject mining` exception is used as the architecture. The implementation applies family-level source/context alignment and preserves normal downstream law/tempus/status validation for general or aligned instruments.

## Invariants enforced

- `LEAD_ONLY` cannot enter Evidence Map, Case Readiness, Alleged Act, Legal Elements, or Causation.
- `LIMITED` cannot be upgraded into Evidence Map or Case Readiness.
- `REJECTED` cannot become evidence, alleged act, legal construction, element, causation, or risk; producer-authorized future actions may still route only to Action Plan.
- A downstream consumer cannot override a prohibited SAL route.
- Candidate Law admission rejects clear subject-matter mismatch before the canonical chain.
- Law admission remains an admission gate only; positive-law validity, status, tempus, provision verification, and final applicability remain downstream responsibilities.

## Regression results in build environment

- SAL targeted tests: 17 passed.
- Full non-smoke regression: 311 passed.
- `tests/test_smoke.py` cannot be collected in this build container because Flask is not installed. This is an environment dependency, not a failing application assertion.
- `py_compile`: PASS for modified Python modules/tests.

## Freeze criterion

Re-run LELY and BAP in the user's Windows runtime. LELY must no longer expose bare `surat perjanjian hutang piutang` as mapped proof, `bukti kerugian` as Alleged Act, or an IUP/mining instrument as Candidate Law. BAP must continue to reject interrogation questions and procedural/contextual statements from proof routes. If both benchmarks have no hard semantic-route or subject-matter violations, SAL upstream/downstream contract may be frozen.
