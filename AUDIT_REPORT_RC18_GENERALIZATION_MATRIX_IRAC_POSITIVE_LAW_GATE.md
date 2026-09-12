# LexiCore RC18 — Generalization Matrix + IRAC + Positive-Law Planner Gate

## Objective
Implement the audit direction additively without rewriting the existing `domain_classification` contract or replacing the deterministic pipeline.

## Production changes

### `services/case_domain_classifier.py`
- Preserves all existing keys (`posture`, `primary_domain`, `domains`, `domain_contract`, guards).
- Adds formal additive fields:
  - `ranah_hukum`
  - `posisi_pengguna`
  - `posisi_pengguna_confidence`
  - `posisi_pengguna_basis`
- Position is derived from document structure + explicit party-side markers and fails closed to `BELUM_TERIDENTIFIKASI` when ambiguous.
- Adds a safe `general_legal` fallback. Unknown/new matters no longer fall through to the first score dictionary entry (`corruption`) when all domain scores are zero.
- Inheritance-only text remains `GENERAL_LEGAL` with `forum_screen.inheritance_detected=true`; forum is not invented.

### `services/case_working_paper.py`
- Replaces broad domain-only tactical expansion with a conditional matrix keyed by `(ranah_hukum, posisi_pengguna)`.
- Matrix modules are *consideration modules*, not automatic legal recommendations. Every generated module states that facts/evidence/forum/tempus/verified-law gates still apply.
- Adds a generic evidence-first fallback for unknown/new matters, so a new case remains analyzable without adding a new case-specific branch.
- Adds a fail-closed positive-law gate for specific article/instrument recommendations. An unverified specific citation is withheld and replaced by a `LEGAL_VERIFICATION_REQUIRED` action.
- Formalizes the existing deterministic legal construction as explicit IRAC output while preserving prior fields:
  - `issue`
  - `rule`
  - `application`
  - `conclusion`
  - `reasoning_model = IRAC_DETERMINISTIC_FAIL_CLOSED`

## Non-goals / unchanged
- No new LLM prompt or AI dependency.
- No rewrite of Regulatory Corpus, positive-law verification, instrument identity, OCR, tempus, or retrieval.
- No case-specific branch for DKPP, corruption-credit, inheritance, or another named case.
- Existing domain/posture fields remain backward compatible.

## Validation
- `python -m py_compile services/case_domain_classifier.py services/case_working_paper.py` — PASS.
- New focused suite `tests/test_rc18_generalization_matrix_irac_gate.py` — 5 PASS.
- Existing non-Flask suite — 193 PASS.
- Full suite was not run in this container because Flask is unavailable; Windows `release_check.bat` remains authoritative.

## Acceptance invariants
1. Civil defendant source => `PERDATA + TERGUGAT` and defendant-side tactical modules.
2. Unknown/new inheritance source does not become corruption and does not require a new hardcoded domain branch.
3. Unknown/new domain still receives evidence-first general tactical modules.
4. Specific unverified statutory recommendations are blocked before action-plan promotion.
5. Legal construction exposes explicit deterministic IRAC without changing fail-closed semantics.
