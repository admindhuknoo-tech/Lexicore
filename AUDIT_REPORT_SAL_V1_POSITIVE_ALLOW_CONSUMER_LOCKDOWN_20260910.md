# LexiCore SAL v1.0 — Positive-Allow Consumer Lockdown

## Scope
This migration does not introduce a new reasoning pipeline. It makes the existing SAL/SSoT boundary authoritative across Issue, Alleged Act, Candidate Law, and Executive Summary consumers.

## Contract migration
- Source text remains audit-only after SAL enrichment.
- Evidence Map consumes only PRIMARY_EVIDENCE admitted by SAL.
- Alleged Act consumes only FACT_ASSERTION with positive actor + concrete past/current act proof.
- Current Issue generation is blocked unless a current FACT_ASSERTION/PARTY_ARGUMENT has a same-domain LAW_CITATION clash.
- Candidate Law uses positive subject-matter compatibility proof. Unknown/mismatched subject matter is rejected as REJECTED_SUBJECT_MATTER_UNPROVEN.
- Executive Summary reads governed fact/action pools only; FUTURE_ACTION cannot appear under Fakta Kunci.
- Missing route token or empty positive pool fails closed; there is no raw/original-candidate fallback.

## Files changed
- services/sal_source_of_truth.py
- services/semantic_admission.py
- services/legal_reasoning_chain.py
- app.py
- routes/case_analysis.py
- tests/test_sal_v1_positive_allow_ssot.py
- SEMANTIC_CONTRACT_FREEZE.md

## Validation
- Targeted SAL/SSoT/Positive-Allow: 31 passed.
- Full non-smoke regression: 325 passed.
- py_compile on changed Python modules: PASS.
- test_smoke.py not run in this container validation pass.

## Acceptance invariants
1. Bare document/evidence references never become proof.
2. Remedy/object phrases never become Alleged Act.
3. Future procedural plans never activate Current Issue.
4. Candidate law requires positive subject-matter proof; blacklist-only behavior is prohibited.
5. Executive Summary separates governed facts from future actions.
6. Raw source and original candidate fallback are prohibited for governed consumers.
