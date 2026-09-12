# Audit Report — Unified Presentation Sanitizer v1.2.3

Scope: presentation/export only. No SAL, evidence, law applicability, tempus, element, or retrieval authority changed.

Implemented in `exporters/common.py` to preserve the frozen four-file exporters directory contract.

Key controls:
- strong-evidence civil posture projection for Duplik/Replik/Gugatan/Jawaban;
- civil-only terminology swap for residual criminal-template wording;
- universal reader-facing cleanup for system status/token leakage;
- recursive sanitization without `eval()` or serialization round-trip;
- final sanitizer cleans section lines only, preserving canonical internal section headings for regression compatibility.

Validation:
- targeted v1.2.2 + v1.2.3 + adaptive export tests: 19 passed;
- structural release audit: PASS;
- full non-smoke regression: 377 passed;
- Python compile check: PASS.
