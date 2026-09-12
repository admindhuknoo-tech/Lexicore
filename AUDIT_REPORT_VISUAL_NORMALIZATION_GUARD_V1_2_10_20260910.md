# LexiCore Visual Normalization Guard v1.2.10

Scope: exporter presentation layer only.

Changed production file:
- exporters/common.py

Added regression test:
- tests/test_visual_normalization_guard_v130.py

Final literal case-sensitive micro-normalization added at the existing clean_text render sanitizer boundary for:
- missing link / Missing Link
- merits / Merits
- Personal responsibility / personal responsibility
- Source:
- Provision Citation:
- mode mode deterministik lokal / Mode Mode Deterministik Lokal

No changes to recursive sanitization, SAL, orchestrator, evidence, law engine, tempus, retrieval, canonical reasoning, or persistence.

Validation:
- Python compile: PASS
- Structural release audit: PASS
- Targeted export/presentation regression: 16 passed
- Full non-smoke regression: 406 passed
