# LexiCore v1.4.5 — Desktop Layout Balance

Scope: presentation-only desktop layout adjustment on top of v1.4.4.

## Changes
- Desktop sidebar is forced to fill the viewport height (`100dvh`) so the dark navigation surface no longer stops early.
- Main workspace now fills the desktop viewport and uses flex-column layout.
- Main footer/identity block is pushed to the bottom when page content is short, removing the visually empty lower-right corner.
- Desktop title/header spacing, main horizontal padding, nav spacing, and sidebar footer spacing are balanced with `clamp()` values.
- All changes are scoped to `@media(min-width:1001px)`; tablet/mobile behavior is unchanged.

## Production files changed
- `static/index.html`

## Validation
- New v1.4.5 tests: 2 PASS.
- Targeted deployment/UI regression: 31 PASS.
- Structural release audit: PASS (`v1.3.14-rc18`, templates=43, regulations=48).
- Full non-smoke suite: 468 PASS in 27.28s. The container wrapper reported timeout only after pytest had printed the completed 468/468 summary.

No SAL, legal reasoning, evidence, tempus, retrieval, license semantics, persistence, or exporter semantics were changed.
