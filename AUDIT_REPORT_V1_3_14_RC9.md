# LexiCore v1.3.14-rc9 — Sticky Layout Stabilization

- Moved RC8 sticky/rail CSS from PDF export template into the global application stylesheet.
- Removed responsive `.main{overflow:hidden}` interference with CSS sticky positioning via RC9 override.
- Primary LexiCore + 8-module navigation is sticky on responsive layout.
- Workspace title/status header is sticky directly below the primary header using measured CSS offsets.
- Case Working Paper navigation is forced horizontal on every viewport with visible horizontal scrollbar, touch swipe, and mouse-wheel bridge.
- No reasoning/OCR/database/export payload logic changed.
