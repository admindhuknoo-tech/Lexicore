# AUDIT REPORT — SAL v1.0 Robust Speaker Fingerprinting

Date: 2026-09-10
Scope: upstream adversarial identity/provenance only; no evidence/law/element core redesign.

## Purpose
Close the OCR-partial speaker-ownership gap observed in the PH/JPU adversarial golden pair without reopening substantive reasoning. Document identity is resolved from weighted semantic fingerprints across the entire available extracted corpus rather than relying on the first-page header.

## Contract changes
- Added `LexiCoreContractEnforcer.resolve_document_adversarial_identity()` using positive weighted prosecution/defense fingerprints.
- Identity is positive-allow: weak/tied evidence yields `UNRESOLVED_SOURCE_OWNERSHIP`; it never defaults to DEFENSE.
- `enrich_source_ledger_with_sal()` can receive the complete extracted corpus and propagates one document identity to every statement.
- Frozen SAL schema remains unchanged. `speaker_role`, `position`, `stance`, and `epistemic_status` are encoded in existing provenance/posture strings and projected to ledger fields.
- FACT_ASSERTION is no longer forcibly converted solely because it belongs to an adversarial document. Speaker ownership and epistemic status are separate dimensions.
- Prosecution merits assertions are tagged `UNVERIFIED_PROSECUTION_ALLEGATION` and excluded from governed Executive Summary facts.
- Defense rebuttal assertions are tagged `UNVERIFIED_DEFENSE_REBUTTAL`; ordinary chronology reported by defense remains `FACT_ASSERTION` with `CHRONOLOGICAL_FACT_REPORTED_BY_DEFENSE`.
- Source trace/viewpoint projections label owned allegations/rebuttals explicitly instead of presenting them as universal objective facts.
- General document presentation posture may be corrected by decisive adversarial fingerprint, including OCR-partial documents where the physical header is absent from extracted text.

## Non-changes / frozen core
No change to Evidence Map admission, Positive Law verification, tempus gates, element ownership, causation, risk, or canonical legal reasoning semantics. No raw-source fallback was added.

## Validation
- Targeted SAL/SSoT/adversarial/view tests: 31 passed.
- Full regression excluding environment-dependent `tests/test_smoke.py`: 342 passed.
- `py_compile` passed for all modified Python modules.

## Golden acceptance
1. JPU body fingerprint can resolve `PROSECUTOR/PROSECUTION` without the physical header.
2. JPU unilateral merits accusation remains semantically traceable but is epistemically bounded and excluded from `Fakta Kunci`.
3. PH chronology can remain `FACT_ASSERTION` while retaining `DEFENSE_COUNSEL` ownership.
4. Unknown/tied documents remain unresolved; no binary default is permitted.
