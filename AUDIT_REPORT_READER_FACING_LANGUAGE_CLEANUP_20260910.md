# Audit Report — Reader-Facing Language Cleanup

Scope: presentation/export layer only. Internal canonical codes remain unchanged in payload, persistence, SAL, Law Engine, Evidence, Elements, and reasoning contract.

Reference output reviewed: LexiCore-Case_Analysis-20260910-1530.docx.

Observed reader-facing code leakage included internal tokens such as `FAIL_CLOSED_DOCUMENT_AUDIT_ONLY`, `BLOCKED_LAW_VERIFICATION`, `NEXUS_NOT_ESTABLISHED`, `BAD_FAITH_NOT_ESTABLISHED_FROM_CURRENT_LEDGER`, `ACTUAL_IMPACT_NOT_ESTABLISHED_FROM_CURRENT_LEDGER`, `SAL_CONTRACT_LEDGER_*`, `READ_ONLY_SAL_ROUTE_TOKEN_LEDGER_NO_RECLASSIFICATION`, and English chain labels.

Correction:
- Added deterministic reader-facing Indonesian translation helpers in `exporters/common.py`.
- Humanized SAL/adversarial/canonical-chain labels without mutating internal values.
- Replaced technical presentation strings for mitigation, causation, status gates, routing, and readiness.
- Preserved statement IDs as audit identifiers where traceability is useful.
- Updated one presentation test to match the new reader-facing section titles.

Validation:
- Targeted presentation/adversarial/backlog tests: 18 passed.
- Full regression excluding environment-dependent `test_smoke.py`: 356 passed.
- `py_compile`: passed.

Invariant preserved: this is a presentation projection cleanup only; no legal reasoning or semantic admission logic changed.
