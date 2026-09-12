# LexiCore SAL v1.0 — Element & Source Trace Final Lockdown

## Scope
Contract migration is limited to the two remaining acceptance failures observed in the LELY 12:07 benchmark:
1. Legal Elements were still instantiated even when no admitted current Issue and no admitted Governing Law existed.
2. Material Source Trace could still display a legacy factual label inconsistent with the authoritative SAL semantic type.

## Migration
### Strict Element Instantiation
`services/legal_reasoning_chain.py`
- Under SAL Single Source of Truth, a legal element is instantiated only if both an admitted current Issue and an admitted Governing Law exist.
- If either owner is absent, the chain exposes `ELEMENT_NOT_INSTANTIATED`, an empty element text, empty evidence, and empty alleged act.
- No template/blueprint element is promoted merely to keep the chain visually populated.

### Semantic-Preserved Source Trace
`services/case_consistency_guard.py`
- `material_source_ledger` now preserves `sal_semantic_type`, `sal_admissibility_state`, and SAL statement id.
- Executive fact candidates exclude SAL types that are not FACT_ASSERTION/PRIMARY_EVIDENCE and exclude REJECTED/LEAD_ONLY rows.

`exporters/common.py`
- Source Trace labels are derived from SAL semantic type when available.
- `DOCUMENT_REFERENCE` renders as `Referensi Dokumen / Lead Only`, not as a factual legacy label.
- Display fallback remains only for pre-SAL compatibility and cannot alter admissibility or routing.

## Acceptance tests
- Targeted SAL/SSoT/Positive-Allow/Element-Trace suite: 33 passed.
- Full regression suite excluding environment-dependent `test_smoke.py`: 327 passed.
- `py_compile`: PASS.

## Freeze boundary
No taxonomy, domain classifier, law-verification semantics, or evidence admission rule was expanded. This release enforces already-frozen ownership and semantic-preservation invariants at the two remaining consumers.
