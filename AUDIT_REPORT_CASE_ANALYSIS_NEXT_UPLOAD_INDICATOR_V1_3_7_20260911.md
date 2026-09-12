# LexiCore v1.3.7 — Case Analysis Next / Upload Indicator

Scope: UI-only correction in `static/index.html`.

Changes:
- Adds one slim actionable `NEXT / PROSES · Mode & Analisis` chip for manual input or chosen-file flow.
- The chip jumps directly to the regulatory-mode selector; analysis remains an explicit user action.
- Adds an inline file state: `File berhasil dipilih` immediately after file selection.
- Promotes that state to `Upload sukses` only after backend progress reports `UPLOAD_STORED`.
- Preserves existing Case Analysis process strip, analysis logic, history refresh, and review behavior.

Frozen core unchanged: SAL, evidence admission, canonical reasoning, tempus, positive-law verification, retrieval, candidate-law governor, persistence semantics.
