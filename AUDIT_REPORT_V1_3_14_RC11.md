# LexiCore v1.3.14-rc11 — Layout Stabilization Audit

- Baseline UI restored from RC7 before applying the requested two-header freeze.
- Header 1: LexiCore + 8-menu navigation fixed on responsive layout.
- Header 2: active module title fixed directly below Header 1.
- Submenu/section navigation remains normal-flow content.
- Case Working Paper selector is horizontal left/right scrolling and non-sticky.
- No RC8/RC9/RC10 sticky CSS retained.

## RC11 test-contract corrective
- Removed stale RC8 UI regression assertion from `tests/test_smoke.py`.
- Regression test now validates the RC11 two-fixed-header contract (`workspaceFixedHeader`, dynamic header heights, non-sticky panel subnav, horizontal Case rail).
- Runtime/UI source was not changed by this corrective.
