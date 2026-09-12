# LexiCore V2.3.1 — Contract Migration V2.2 Selective Integration Audit

Date: 2026-09-10
Baseline: CONTRACT_MIGRATION_V2_1
Input idea set: `Pasted markdown(9).md` — Semantic Contract Closure

## Decision

The idea set was **not copied as a parallel V2.1 pipeline**. LexiCore already has a mature `element_reasoning`, `legal_reasoning_chain`, positive-law gate, tempus gate, evidence hygiene, persistence/export wiring, and regression suite. Adding the pasted modules verbatim would create a second source of truth and re-introduce lexical false positives.

The accepted concepts were integrated into the existing canonical code path only where they strengthened the current contract.

## Accepted selectively

1. **Explicit inherited binding context**
   - Added stable `issue_key`, `law_key`, and `element_key` lineage per canonical chain row.
   - Added binding metadata to `element_test`.
   - No new parallel `IssueLawBinding`, `ElementAllegedBinding`, or `EvidenceElementBinding` service was introduced.

2. **Granular element-test status**
   - Added `granular_status` while retaining existing fail-closed source status.
   - Law verification gate precedes evidentiary confidence.
   - Examples: `LAW_GATE_HOLD`, `ACT_ATTRIBUTION_UNVERIFIED`, `NO_SUPPORTING_EVIDENCE`, `SUPPORTED_WITH_COUNTER`, `DISPUTED_WITH_COUNTER`, `PRIMA_FACIE_SUPPORTED`.

3. **Risk aggregation per issue**
   - Added `issue_risk` derived from the element chains bound to that issue.
   - This avoids the pasted-code defect where each issue receives the global element-test summary.

4. **Recommended-action provenance**
   - Added `derived_from` gate provenance for law, act, evidence, counter-evidence, element status, and causation.
   - Existing precision action plan remains authoritative when available.

5. **Semantic contract validation**
   - Contract version raised to 2.2.
   - Validator now checks typed stage envelopes, explicit stage status, and binding lineage.
   - Substantive missing/unverified stages are represented as semantic `HOLD`, not structural failure.

## Rejected / not copied

1. **Naive Issue ↔ Law keyword overlap**
   - Rejected because `len(overlap) > 0` plus generic words (`pidana`, `perdata`, `korupsi`, `perjanjian`) can bind unrelated law.
   - Existing `_law_candidates` semantic-nexus + `VERIFIED_APPLICABLE` behavior is retained.

2. **Alleged Act = first 1000 chars of source text**
   - Rejected. Source text can contain headers, counsel identity, procedural metadata, quotations, or legal argument.
   - Existing element-level alleged-act extraction remains authoritative.

3. **Evidence binding by first five words of element description**
   - Rejected because this can promote pleadings, headings, denials, or legal references into evidence.
   - Existing evidence-hygiene channel remains authoritative.

4. **Counter-evidence extracted from `arguments_for`, `arguments_against`, or denial markers**
   - Rejected. Argument is not evidence. LexiCore V2.1 already separates counter-argument from counter-evidence.

5. **Element status determined by evidence-count majority**
   - Rejected. Evidentiary quantity is not probative weight, authenticity, admissibility, legal sufficiency, or credibility.

6. **Causation inferred from generic SUPPORTED status**
   - Rejected. A supported element does not establish causation. Procedural issues continue to mark merits causation as a GAP/non-merits stage.

7. **Standalone parallel `case_analysis_pipeline.py`**
   - Rejected to preserve the single-source lifecycle already wired through service → API/persistence → UI/exporter → benchmark/tests.

## Files changed

- `services/reasoning_contract.py`
- `services/legal_reasoning_chain.py`
- `tests/test_contract_migration_v2_2_selective_semantic_binding.py` (new)
- this audit report

## Contract after migration

`Issue → Applicable Law → Legal Elements → Alleged Act → Evidence → Counter-Evidence → Element Test → Causation → Risk → Procedural/Merits Classification → Recommended Action`

Every chain row now carries stable lineage across Issue/Law/Element plus explicit gate provenance for the final action.

## Validation

- Targeted regression: **12 passed**
- Full collectible suite excluding `tests/test_smoke.py`: **282 passed**
- `tests/test_smoke.py`: not collectible in this sandbox because `flask` is not installed (`ModuleNotFoundError: No module named 'flask'`). This is an environment dependency limitation, not an observed application test failure.
- `py_compile` for changed Python modules/tests: **PASS**

## Migration posture

No broad refactor was performed. The integration intentionally preserves:

- positive-law fail-closed behavior;
- tempus gate;
- evidence vs pleading/argument separation;
- procedural vs merits separation;
- canonical persistence/export path;
- existing element reasoning as the single authoritative producer.
