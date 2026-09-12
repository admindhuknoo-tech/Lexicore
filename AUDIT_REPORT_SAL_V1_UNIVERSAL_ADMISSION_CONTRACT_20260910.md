# LexiCore — SAL v1.0 Universal Admission Contract

## Scope
This release migrates Semantic Admission from a downstream corrective check into an upstream lifecycle contract. It is intentionally not a new parallel reasoning pipeline and it does not act as a substantive Law Engine.

## Lifecycle migration
- **Producer / source ingestion:** `services/semantic_admission.py` segments and classifies source statements into one strict semantic type and attaches provenance, modality/temporality, domain/posture and restricted routes.
- **Pre-retrieval admission:** `routes/case_analysis.py` builds SAL before dynamic legal retrieval. QUESTION, FUTURE_ACTION and bare document-reference text no longer seed legal retrieval.
- **Evidence producer:** `app.py` enriches every source-ledger row with its SAL contract before material-source, Evidence Map and element projections.
- **Evidence / readiness consumers:** `services/case_consistency_guard.py` rejects SAL-forbidden statements from Evidence Map and excludes QUESTION/FUTURE_ACTION from user-facing material evidence projection.
- **Element reasoning:** `services/element_reasoning.py` consumes SAL route eligibility, so legacy lexical classifications cannot upgrade rejected/lead-only statements into element proof.
- **Candidate law / canonical chain:** `services/semantic_admission.py::law_subject_matter_admissible` and `services/legal_reasoning_chain.py` deny specialized subject-matter mismatches before a law can bind an element chain. This is an admission screen only; positive-law identity/status/tempus verification remains authoritative downstream.
- **Document posture:** `services/document_posture_resolver.py` recognizes planning/advisory notes as `PRE_LITIGATION_ADVISORY` before generic words such as “gugatan” can misclassify them as filed pleadings.
- **Persistence/API:** SAL objects are attached to the canonical result object prior to `CaseAnalysisManager.save`; no separate persistence model/source of truth is introduced.
- **UI / PDF / DOCX:** existing exporters/UI consume the persisted SAL summary and do not recalculate semantic status.
- **Air-gap:** malformed/out-of-schema payloads are transformed into an isolated LEAD_ONLY Document Audit payload with `FORCE_MANUAL_PROFESSIONAL_VERIFICATION`.

## Three immutable anchors
1. `schemas/LexiCore-SAL-v1.0.json` — Draft 2020-12 JSON Schema with `additionalProperties:false`, strict enums and route validation.
2. `golden_datasets/SAL-v1.0-edge-cases.json` — regression anchors for LELY future-action leakage, BAP interrogation/party-argument separation and unrelated HKI law retrieval.
3. `services/semantic_admission.py` — schema validator + deterministic Air-Gap fail-safe.

## Important normalization of the supplied design
The supplied design calls the downstream register “13 components” while explicitly listing 15 analysis nodes, and Stage 2 also requires semantic ingress/auxiliary routes (`Issue`, `Counter-Evidence`, `Evidence Lead`, `Interrogation Context`). The production schema therefore validates the explicit route names instead of trusting the numeric label. This avoids a false contract that cannot represent its own routing rules.

## Regression acceptance
- Targeted SAL/freeze/corrective tests: 31 passed.
- Full suite excluding `tests/test_smoke.py`: 307 passed with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
- `tests/test_smoke.py`: not collectible in this execution environment because Flask is not installed (`ModuleNotFoundError: flask`). This is an environment dependency, not a SAL test failure.
- Python compile check for all modified modules: PASS.

## Freeze boundary
The next benchmark is not allowed to create new ad-hoc SAL rules. BAP and LELY are acceptance datasets. A core change is permitted only if a reproducible input violates an existing SAL or 11-stage hard invariant. Missing source, unverified law, weak evidence or ordinary wording quality are HOLD/coverage concerns and do not reopen the upstream contract.
