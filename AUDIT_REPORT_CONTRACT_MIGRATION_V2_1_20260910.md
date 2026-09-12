# LexiCore V2.3.1 — Contract Migration V2.1 Audit

## Trigger
Regression audit against `LexiCore-Case_Analysis-20260910-0907.pdf` after Contract Migration V2.

## Findings
1. **Cross-domain leakage remained**: a civil inheritance/land/PMH pleading still received `civil_contract` / wanprestasi elements even though the source did not establish a contractual dispute.
2. **Evidence hygiene contract was broken downstream**: the report declared only 1 material source item from 48, but the element matrix still promoted legal argument, party/procedural text, pleaded assertions, and denials into `Evidence` / `Counter-Evidence`.
3. **Alleged Act remained missing** in canonical chains because pleading propositions were not carried as a separate contract channel.
4. **Counter-argument vs Counter-Evidence remained conflated**: denial language could populate counter-evidence solely from lexical cues.
5. **Applicable Law selection could borrow an unrelated global candidate** when semantic score was zero.
6. **Procedural chains inherited a global merits causation status**, producing a misleading `MAPPED` causation stage.
7. **Civil source taxonomy was underpowered**: land, inheritance, civil-procedure and PMH facts were not consistently classified as material case propositions.

## Contract Migration Applied
Canonical sequence remains:
`Issue → Applicable Law → Legal Elements → Alleged Act → Evidence → Counter-Evidence → Element Test → Causation → Risk → Procedural/Merits Classification → Recommended Action`

### Producer/source taxonomy
- Added civil-procedure, land, inheritance, tort and contract concepts to source classification.
- Expanded civil material-fact recognition for SHM/sertipikat, SKPT/PTSL/BPN, inheritance, PMH and core pleading propositions.

### Element reasoning
- Contract elements are no longer activated by a bare occurrence of the word `perjanjian`; a real contract/breach formulation is required.
- Source rows now carry separate eligibility for allegation vs evidence.
- Pleaded facts, denials and legal arguments are excluded from Evidence/Counter-Evidence.
- Pleading propositions can populate `alleged_act` / `alleged_act_sources`.
- Denials/legal argument are retained only as `counter_arguments`, never silently upgraded into counter-evidence.

### Canonical reasoning chain
- Counter-argument fallback is preserved separately when no counter-evidence exists.
- Zero-nexus legal candidates are no longer selected as element-level Applicable Law merely because they were globally retrieved.
- Procedural chains keep the causation stage visible but fail closed as GAP/non-merits rather than inheriting a global merits nexus.

## Regression Tests Added
`tests/test_contract_migration_v2_1_civil_evidence_hygiene.py`

Covers:
- PMH/waris/tanah does not inject wanprestasi elements absent a contract dispute.
- Pleading and denial are not promoted to evidence or counter-evidence.
- Procedural chain does not borrow an unrelated law candidate and does not claim a merits causation mapping.

## Validation
- `pytest -q --ignore=tests/test_smoke.py` → **276 passed**.
- `python -m compileall -q services tests` → **PASS**.
- `tests/test_smoke.py` remains excluded because its environment dependency (`flask`) is not available in this audit sandbox, consistent with the prior audit limitation.

## Release assessment
V2.1 closes the residual contract drift demonstrated by the 09:07 output without broad refactor. The change is intentionally surgical and keeps fail-closed positive-law/tempus behavior intact.
