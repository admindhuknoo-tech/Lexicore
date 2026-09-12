# LexiCore SAL v1.0 — Single Source of Truth Enforcement

## Scope
Contract migration only. No taxonomy redesign and no legal-rule refactor.

## Frozen boundary
Raw source remains available for auditability, but reasoning consumers must read only SAL governed pools. There is no empty-filter fallback to original candidates.

## Closed pools
- Evidence Map: PRIMARY_EVIDENCE + route token only; proposition compatibility remains element-specific.
- Alleged Act: FACT_ASSERTION/PARTY_ARGUMENT + route token only.
- Candidate Law: subject-matter-admitted law records only.
- Document Audit / Action Plan: isolated leads and future actions remain available without proof promotion.

## Fail-closed invariant
A downstream row without a registered route token is `BLOCKED_ROUTE_CONTRACT` by policy and receives no permission.

## Lifecycle migration
Source ingestion -> SAL typing -> route-token ledger -> governed pools -> element/evidence producer -> law admission -> working paper -> canonical chain -> persistence/export.

## Acceptance anchors
LELY: bare `surat perjanjian hutang piutang` cannot become evidence; `bukti kerugian` cannot become alleged act; IUP/mining cannot become candidate law.
BAP: question and procedural metadata cannot become proof; party statements remain allegation/fact propositions unless primary evidence supports them.
