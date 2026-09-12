# LexiCore v1.4.6 — Mobile Profile Onboarding Layout Repair

Scope: presentation/UI only.

Observed issue: on phone viewport, the first-run Profile Pengguna/Firma onboarding sheet visually stacked over the frozen LexiCore mobile header/workspace and retained desktop-style multi-column form behavior.

Changes:
- profile onboarding receives a dedicated mobile full-screen surface at <=720px;
- profile modal z-index raised above the frozen mobile navigation;
- form rows collapse to one column;
- modal body becomes independently scrollable with safe-area bottom padding;
- save action remains reachable at the bottom of the onboarding surface;
- background workspace scroll is locked while profile modal is open;
- desktop layout is unchanged.

No changes to licensing semantics, onboarding persistence, SAL, evidence admission, tempus, positive-law verification, retrieval, canonical reasoning, persistence model, or exporters.

Validation:
- JavaScript syntax: PASS
- targeted v1.4.6 tests: 3 PASS
- structural release audit: PASS
- full non-smoke regression: 471 PASS (pytest completed before wrapper timeout)
