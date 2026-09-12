# LexiCore Audit Report — Candidate-Law Retrieval Weight Policy v1.2.1

Date: 2026-09-10
Baseline: `LEXICORE_V2.3.1_READER_FACING_LANGUAGE_CLEANUP_FULL.zip`
Scope: Candidate-law retrieval relevance only.

## Implemented

1. Replaced `retrieval/law_weight_config.json` with frozen contract `1.2.1_frozen`.
2. Added `retrieval/search_router.py` as a retrieval-only Positive-Allow router.
3. Wired `services/regulatory_retrieval.py` through the router while preserving its public compatibility facade.
4. Added institutional mismatch protection for KPK internal personnel/organizational regulations using issuer + subject-matter conjunction, not a broad KPK blacklist.
5. Added cross-domain degradation for mining/energy/environment/employment noise only when the corruption+banking target profile is active.
6. Added protected candidate laws with effect `BYPASS_RETRIEVAL_DROP_ONLY`; no retrieval rule can mark Applicable Law or bypass tempus/positive-law verification.
7. Added `CONTEXTUAL_LAW` tagging for underlying credit/fiduciary/agunan norms.
8. Preserved generic-domain behavior outside the targeted corruption+banking profile.

## Explicitly Not Changed

- SAL schema and semantic admission contract.
- Evidence Map admission.
- Element ownership/instantiation.
- Document Identity / speaker ownership.
- Positive-Law Verifier, tempus gate, provision verification, or case applicability.
- Canonical legal reasoning chain structure.

## Validation

- `py_compile`: PASS.
- New + backlog retrieval tests: 14 PASS initially; after generic-domain regression correction, targeted migration set PASS.
- Full non-smoke regression: **362 passed** (`tests/test_smoke.py` excluded because environment-dependent).
- A regression found during integration (`test_dynamic_case_regulatory_domain_and_query_routing`) was corrected by limiting aggressive target-profile penalties/thresholds to corruption+financial-services context. This prevented the new configuration from suppressing valid employment-law retrieval.

## Acceptance Invariants

- KPK internal employee/performance regulation in corruption-banking case -> hard drop before Candidate Law Pool.
- Tipikor/KUHP protected candidate -> may survive retrieval, but remains unverified and cannot become Applicable Law through this module.
- Fiduciary/agunan/credit relationship norm -> contextual candidate only unless downstream verification independently promotes it.
- Cross-domain mining regulation -> degraded/rejected for corruption-banking profile.
- Ordinary employment/civil/land cases -> not subjected to corruption-banking institutional penalty profile.
