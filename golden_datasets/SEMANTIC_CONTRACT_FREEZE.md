# LexiCore Semantic Contract Freeze — V2.3

## Definition of Done
Core reasoning is considered complete when all invariants below pass regression tests. A new output is **not** a reason to modify the core unless it violates one of these invariants.

1. One canonical chain only: Issue → Applicable Law → Legal Elements → Alleged Act → Evidence → Counter-Evidence → Element Test → Causation → Risk → Procedural/Merits → Recommended Action.
2. Every legal element has one explicit `owner_domain`, `owner_issue_id`, and `owner_issue`.
3. An element may never migrate to another issue by lexical similarity.
4. Applicable Law must be compatible with the element owner domain; cross-domain use requires an explicit compatibility rule.
5. Candidate/unverified law never becomes verified applicable law.
6. Pleading, denial, legal argument, heading, or metadata never becomes Evidence/Counter-Evidence merely from keyword overlap.
7. Evidence must pass a proposition-level compatibility gate for the owned element/domain.
8. Counter-argument remains separate from counter-evidence.
9. Procedural chains do not inherit merits causation.
10. Contract/wanprestasi reasoning activates only on an explicit contractual/breach formulation; generic civil language is insufficient.
11. Risk is aggregated from the chains owned by the same issue, not from unrelated global elements.
12. Recommended Action must be traceable to unresolved gates or element-test results.
13. Structural PASS and semantic HOLD are different states and must remain visible.
14. Exporters/UI consume the persisted canonical chain; they must not independently recalculate legal reasoning.
15. Core reasoning changes after freeze require a reproducible regression that names the violated invariant.

## Release Boundary
V2.3 is a **core-reasoning freeze candidate**. After this point, ordinary wording/layout improvements, retrieval tuning, or additional legal domains are not core fixes. They must be implemented outside the frozen contract unless an invariant above is demonstrably broken.

## Acceptance Rule
- **PASS / FREEZE ELIGIBLE:** all invariant regression tests pass; full existing test suite has no new failures; compile succeeds.
- **HOLD:** missing law, act, evidence, counter-evidence, or causation is represented explicitly and does not corrupt lineage.
- **FAIL:** domain lineage, element ownership, evidence proposition, or stage contract is silently violated.


## Final Corrective V2.3.1 — Freeze Exit Criteria
A benchmark may close the core only when `reasoning_contract.status=PASS`, `semantic_status` is PASS/HOLD solely for explicit missing or unverified gates, and `hard_semantic_violations=[]`. BAP posture, evidence-proposition admissibility, and issue-law-element ownership are frozen invariants.

## SAL v1.0 Universal Admission Contract — Upstream Freeze Boundary
SAL is now the mandatory upstream data gate before regulatory retrieval, evidence/readiness projection, element mapping, and the canonical reasoning contract.

Hard upstream invariants:
1. Every source statement receives exactly one semantic type before downstream routing.
2. QUESTION and FUTURE_ACTION never become Fact Pool or Evidence Map material.
3. DOCUMENT_REFERENCE and EVIDENCE_CLAIM remain LEAD_ONLY until the underlying artefact/substance is available and verified.
4. PARTY_ARGUMENT/COUNTER_ARGUMENT remain LIMITED propositions; downstream components may not upgrade them into facts or proof.
5. PRIMARY_EVIDENCE requires explicit evidentiary provenance and still requires proposition compatibility.
6. LAW_CITATION must pass subject-matter admission before substantive identity/status/tempus verification.
7. A specialized law family may not enter an unrelated case merely because of a generic lexical overlap such as “perjanjian”.
8. SAL rejection/route restrictions are monotonic: no downstream component, persistence layer, UI, PDF or DOCX exporter may upgrade them.
9. Malformed SAL payloads enter the Air-Gap fail-safe and are isolated to Document Audit / manual professional verification.
10. The SAL JSON Schema and golden edge-case dataset are release anchors; changes require a named regression and contract-version decision.

The wording “13 downstream components” in the design notes is treated as a conceptual label. The runtime register contains the explicitly enumerated analysis nodes plus semantic ingress/auxiliary buffers required by the routing contract (Issue, Counter-Evidence, Evidence Lead, Interrogation Context). The schema is authoritative for route names.

## SAL v1.0 Portable Runtime Corrective
The immutable schema remains authoritative, but absence of the `jsonschema` Python package may not transform valid source statements into Air-Gap fallbacks. A deterministic built-in schema guard enforces the frozen envelope in portable/offline installations; malformed payloads remain fail-closed.

## SAL v1.0 Cross-Layer Enforcement Addendum (2026-09-10)
SAL admissibility is binding, not advisory. No downstream node may upgrade a prohibited route. `LEAD_ONLY` cannot become Evidence or Alleged Act; clearly mismatched specialist law is dropped before Candidate Law. Core reopening after this point requires a reproducible violation of an existing invariant, not a stylistic or coverage preference.
