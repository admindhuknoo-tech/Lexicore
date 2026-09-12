# LexiCore Backlog A+B Audit Report — 2026-09-10

## Scope
This batch intentionally does **not** modify identity/provenance resolution, Evidence admission, Legal Elements, tempus verification, positive-law verification, causation, risk, or the canonical chain contract.

Two independent backlog modules were introduced:

1. `extractors/bap_noise_cleaner.py` — BAP-only semantic typing quality hints.
2. `retrieval/law_weight_config.json` — positive-nexus candidate-law retrieval weighting.

## Backlog A — Semantic Typing Quality
The BAP cleaner is source-specific and read-only. It never rewrites source text and never creates evidence. It only supplies a semantic-type override when a fragment is positively identified as originating from a BAP/interrogation context and matches a strong form:

- interrogation/question -> `QUESTION`;
- deontic/procedural/contractual obligation fragment -> `LAW_CITATION` under the frozen SAL taxonomy;
- generic legal-act enumeration split by OCR -> `LAW_CITATION`;
- concrete dated/completed conduct remains under the generic SAL classifier.

The cleaner is wired into `services/semantic_admission.py` only as a bounded pre-classification hint. SAL remains authoritative for routing/admissibility. If the cleaner is unavailable or uncertain, classification falls back to the existing generic SAL classifier, not to a new reasoning path.

## Backlog B — Candidate-Law Retrieval Relevance
`retrieval/law_weight_config.json` defines domain-specific positive terms, strong positive terms, disqualifying terms, and bounded relevance weights.

The retrieval gate reads candidate-owned text (`title`, `description`, `snippet`) and deliberately excludes the search query from positive proof. This prevents a correct query from laundering an unrelated returned regulation into the material candidate pool.

The policy can reject a discovery hit as `REJECTED_SUBJECT_MATTER_UNPROVEN` before it consumes material candidate/verification budget. Exact case-bound regulations remain available for identity verification. This gate does not mark law applicable and does not alter tempus or official positive-law verification.

Regression case closed: a KPK regulation on individual performance of advisers/employees is rejected for a Tipikor/BPR merits issue unless stronger positive subject-matter evidence exists.

## Validation
- New backlog tests: **8 passed**.
- Targeted SAL/SSoT/identity/adversarial/backlog suite: **53 passed**.
- Full suite excluding environment-dependent `tests/test_smoke.py`: **356 passed**.
- Python compilation of changed Python modules: **PASS**.

## Freeze Boundary
Identity/provenance remains frozen. The new modules are independent quality/configuration layers and must not be used to reopen the frozen core unless an existing invariant is reproducibly violated.
