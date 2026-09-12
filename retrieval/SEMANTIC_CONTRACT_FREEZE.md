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

## SAL v1.0 Single Source of Truth Governor — 2026-09-10

The SAL contract is now a mandatory data boundary, not advisory metadata.

- Raw `source_ledger` is audit-only for reasoning consumers.
- Evidence Map consumes only the governed `evidence_map_pool`.
- Alleged Act consumes only the governed `alleged_act_pool`.
- Candidate Law consumes only the subject-matter-admitted `candidate_law_pool`.
- Empty governed pools MUST remain empty; fallback to original/raw candidates is prohibited.
- Every admitted source statement must have a route token. Missing token means `BLOCKED_ROUTE_CONTRACT`.
- `LEAD_ONLY`, `LIMITED`, and `REJECTED` may not be upgraded by downstream code or exporters beyond their explicit allowed routes.

This closes the upstream-to-canonical split source-of-truth found in the LELY acceptance benchmark.

## SAL v1.0 Positive-Allow Consumer Lockdown — 2026-09-10
The final upstream contract uses positive-allow semantics rather than blacklist filtering. Issue, Alleged Act, Candidate Law, Evidence Map, and Executive Summary must consume closed governed pools. Absence of positive compatibility proof is a denial, not permission. Raw-source/original-candidate fallback is prohibited. A consumer without an authorized route token must fail closed as `BLOCKED_ROUTE_CONTRACT`.

## SAL v1.0 Element & Source Trace Final Lockdown — 2026-09-10
- Legal elements MUST NOT instantiate without both an admitted current Issue owner and admitted Governing Law owner.
- Missing owner(s) => `ELEMENT_NOT_INSTANTIATED`; `unsur_list`/element text must remain empty at the live chain layer.
- Material Source Trace MUST preserve SAL semantic type/admissibility and MUST NOT re-label `DOCUMENT_REFERENCE`, `FUTURE_ACTION`, `PARTY_ARGUMENT`, or other non-fact types as factual evidence through legacy labels.
- Export display fallback is compatibility-only and MUST NOT upgrade routing/admissibility.


## Addendum — Adversarial Context Envelope (2026-09-10)
- Pleading/tanggapan statements preserve binary speaker ownership in the frozen SAL provenance/posture fields.
- A unilateral accusation or rebuttal cannot become an objective FACT_ASSERTION merely because its syntax is declarative.
- JPU accusation -> PARTY_ARGUMENT/LIMITED; PH rebuttal -> COUNTER_ARGUMENT/LIMITED when the viewpoint gate positively matches.
- Downstream route tokens carry `speaker_role`, `position`, and `stance`; Evidence Map remains closed to these argument-only statements.
- This addendum does not reopen evidence, positive-law, tempus, element-owner, or SSoT invariants.

## Addendum — Adversarial Viewpoint Splitter UI v1.1 (2026-09-10)
The adversarial splitter is presentation-only and MUST NOT reopen SAL/SSoT core behavior.

Frozen presentation invariants:
1. Dashboard/export consumes Route Token Ledger + frozen SAL metadata only.
2. No Route Token means no adversarial display (`blocked_without_route_token`).
3. Renderer may not reclassify semantic type, admissibility, speaker ownership, or routes.
4. PROSECUTOR and DEFENSE_COUNSEL are displayed as viewpoint/provenance, never as proof of truth.
5. UNKNOWN/neutral ownership is rendered as `Sumber Netral / Belum Terverifikasi`, never `Fakta Objektif` by default.
6. Visual color is secondary; text labels are mandatory.
7. UI/export defects do not reopen reasoning core unless they cause semantic upgrade, route bypass, or false ownership.

## Addendum — Robust Speaker Fingerprinting / Epistemic Ownership (2026-09-10)
- Adversarial document identity is resolved from the whole available extracted corpus using deterministic weighted fingerprints; first-page header availability is not required.
- Identity resolution is positive-allow. Ties/weak evidence MUST produce `UNRESOLVED_SOURCE_OWNERSHIP`; no default side is allowed.
- `semantic_type` and `speaker ownership/epistemic status` are separate dimensions. A chronological FACT_ASSERTION may remain a FACT_ASSERTION while being explicitly owned by PH/JPU.
- Unilateral merits allegations/rebuttals MUST NOT be projected as universal objective facts in Executive Summary or Source Trace.
- Frozen SAL schema remains immutable; ownership metadata is carried through existing provenance/posture channels and read-only projections.
- This addendum does not reopen Evidence, Law, Tempus, Element, Causation, Risk, or canonical reasoning contracts.

## Addendum — Document Identity Projection Sync v1.1 (2026-09-10)

Document identity is a provenance/presentation contract. Corpus-wide semantic fingerprinting may resolve JPU, PH, or BAP identity, but it MUST NOT mutate Evidence, Legal Elements, Applicable Law, causation, or merits conclusions. Presentation components MUST consume the positively resolved identity instead of independently re-running a legacy document classifier. Weak/tied identity remains unresolved and MUST NOT default to any adversarial side.

## 2026-09-10 Addendum — Backlog A/B Isolation

Identity/provenance, Evidence admission, Element ownership, positive-law verification, tempus, and canonical-chain structure remain frozen.

Two bounded quality layers are permitted without reopening core:

- `extractors/bap_noise_cleaner.py`: BAP-only semantic typing hint; no source rewrite, no evidence creation, no routing authority.
- `retrieval/law_weight_config.json`: candidate-law discovery relevance configuration; no authority to mark a norm applicable or temporally valid.

Candidate-law retrieval must prove positive nexus from candidate-owned metadata/text rather than inheriting relevance solely from the search query. BAP typing cleanup must remain source-context gated and must preserve concrete completed events for normal SAL typing.

## Reader-Facing Language Projection Freeze — 2026-09-10
Internal status/contract codes may remain in canonical payloads and persistence, but professional PDF/DOCX exports must translate them into clear reader-facing legal Indonesian. Exporters MUST NOT reinterpret or alter the underlying semantic status, routing, ownership, evidence admission, law applicability, element state, or causation state while translating labels.

## Addendum — Candidate-Law Retrieval Weight Policy v1.2.1 (2026-09-10)

Status: **FROZEN — RETRIEVAL-ONLY POLICY**.

- `retrieval/law_weight_config.json` is frozen at `1.2.1_frozen` for the targeted corruption + banking/BUMD retrieval profile.
- `retrieval/search_router.py` may rank, degrade, or reject discovery candidates before the Candidate Law Pool; it has **no authority** to mark a norm applicable, temporally valid, provision-verified, or governing.
- Internal KPK personnel/organizational rules are hard-dropped only when both an institutional issuer anchor and an internal-personnel subject anchor are present under the targeted corruption+banking profile. The word `KPK` alone is never a blacklist trigger.
- Cross-domain mining/energy/environment/employment hits are degraded only while the targeted corruption+banking profile is active; unrelated LexiCore domains retain generic positive-nexus routing.
- `protected_candidate_laws` means `BYPASS_RETRIEVAL_DROP_ONLY`; it is explicitly **not** an admission to Applicable Law.
- Fiduciary/agunan/private-credit norms may be tagged `CONTEXTUAL_LAW`; they cannot become governing law without the existing positive-law/tempus/provision/case-applicability gates.
- SAL, Evidence admission, Element ownership, Document Identity, canonical chain structure, and Positive-Law Verifier remain unchanged.

## Addendum — Generic Pleading Semantic Cleaner + Reader Terminology v1.2.2 (2026-09-10)

This addendum freezes two non-core invariants:

1. Civil pleading semantic quality may use positive, bounded typing hints for procedural filing language and civil adversarial argument, but may emit only existing SAL v1.0 semantic types.
2. Replik/Repliek and Duplik/Dupliek spelling variants may refine document posture without reopening adversarial identity logic.
3. Presentation strategy sanitization is allowed only as a reader-facing projection and may not mutate source facts, SAL routing, evidence, law applicability, or canonical reasoning.
4. Reader-facing sections 13–14 may translate internal implementation vocabulary, but canonical payload values remain unchanged.
5. No use of `eval` or schema-extending metadata is permitted in these projection/quality helpers.


### Release Hygiene Correction — 2026-09-10
Reader-facing terminology helpers must reside in `exporters/common.py`; no fifth live module may be added under `exporters/` while the structural release audit freezes the canonical exporter set. This is a packaging/presentation invariant only and does not change SAL, Law, Evidence, Elements, Identity, or routing semantics.

## Addendum — Unified Presentation Sanitizer v1.2.3 (2026-09-10)

Unified Presentation Sanitizer v1.2.3 is presentation-only and lives in `exporters/common.py` to preserve the frozen exporter directory contract. It may project a reader-facing civil pleading label from strong contextual evidence and sanitize report strings, but it has no authority to mutate SAL semantic types, admissibility, route tokens, evidence status, legal applicability, tempus, element status, or retrieval results. Civil terminology substitution is domain/posture gated. No `eval()` or string-serialization round-trip is permitted.

## Reader Export Final Cleanup v1.2.4 — 2026-09-10
- SAL v1.0 remains fully active as an internal admission/audit contract but is intentionally omitted from reader-facing PDF/DOCX exports.
- Removal of the SAL diagnostic section is presentation-only and does not change semantic types, admissibility, route tokens, evidence authority, persistence, or downstream reasoning.
- Reader-facing adversarial/source projection masks internal SAL ledger identifiers while preserving a compact audit reference.
- Internal route labels and semantic-token phrases are translated only at export projection time.

## Addendum — Final Candidate Law Governor Lock (2026-09-10)

Candidate-law admission is now protected by two independent boundaries: post-merge retrieval enforcement and the SAL SSoT Candidate Law governor. Retrieval-policy metadata must survive official-result reconstruction. A row marked `candidate_law_eligible=false`, or a row that proves an institutional hard mismatch under the frozen policy, cannot enter the canonical Candidate Law pool even when broad lexical family matching would otherwise overlap. Exact case citations may remain available for identity/provision audit but do not bypass the governing-law subject-matter lock. This addendum does not grant retrieval authority over applicability, tempus, provision validity, evidence, or legal elements.


## Addendum — Reader Export Residue Cleanup v1.2.5 (2026-09-10)
Presentation-only terminology cleanup was extended in `exporters/common.py`. No semantic admission, evidence, law, tempus, retrieval, or reasoning authority is granted to this mapper.

## Reader Export Final Sanitizer & Deduplicator v1.2.6 — 2026-09-10
- Presentation-only terminology cleanup remains confined to `exporters/common.py`.
- Action deduplication is permitted only for explicit action/recommendation nodes and may not deduplicate generic evidence, issue, source, or semantic lists.
- Canonical reasoning payloads are not mutated; deduplication affects reader-facing rendering only.
- SAL, Evidence, Elements, Positive Law/Tempus, Candidate Law Governor, identity/provenance, retrieval, and persistence remain frozen and unchanged.

## Reader Export Final Render Lock v1.2.7 — 2026-09-10
Presentation-only addendum. Final reader-facing cleanup is now re-applied at the PDF/DOCX render boundary. Canonical-chain action deduplication is scoped only to repeated rendered `TINDAKAN:` lines within the same chain. This layer has no authority to mutate SAL classification, evidence admission, law applicability, tempus, element status, retrieval decisions, or the canonical reasoning ledger.
