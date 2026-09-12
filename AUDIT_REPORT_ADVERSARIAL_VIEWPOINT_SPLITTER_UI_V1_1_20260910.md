# LexiCore Adversarial Viewpoint Splitter UI v1.1 — Audit Report

Date: 2026-09-10
Scope: Presentation-only projection. SAL/SSoT reasoning core remains frozen.

## Purpose
Add a deterministic PH-vs-JPU visual split to the dashboard and PDF/DOCX export without reclassifying statements or changing legal reasoning.

## Data contract
`services/adversarial_view.py` reads only:
- `source_ledger[*].sal_contract` for frozen semantic/adversarial metadata; and
- `sal_governed_pools.route_token_ledger` for access authorization.

A statement without a valid Route Token is not displayed in the adversarial projection and is counted under `blocked_without_route_token`.

## Presentation invariants
- PROSECUTOR -> label `Posisi JPU / Belum Terverifikasi`.
- DEFENSE_COUNSEL -> label `Posisi PH / Belum Terverifikasi`.
- UNKNOWN -> label `Sumber Netral / Belum Terverifikasi`.
- Neutral does not mean objective/proven fact.
- Renderer never changes semantic_type, admissibility_state, allowed_consumers, or target_node.
- Color is secondary; explicit text labels remain authoritative.

## Files changed
- `services/adversarial_view.py` (new read-only projection service)
- `app.py` (projection wiring after governed-pool compilation)
- `routes/case_analysis.py` (final API/export projection wiring)
- `static/index.html` (dashboard split view + responsive CSS)
- `exporters/common.py` (PDF/DOCX textual adversarial section)
- `tests/test_adversarial_viewpoint_splitter.py`
- `SEMANTIC_CONTRACT_FREEZE.md`

## Validation
- Targeted adversarial-view tests: 4 passed.
- Full non-smoke regression: 336 passed.
- Python compile: passed for modified Python modules.

## Non-goals
No database migration, no new reasoning pipeline, no law/evidence/element changes, no SAL schema changes, and no speaker reclassification in the renderer.
