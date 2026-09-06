# LexiCore v1.3.14-rc5 Audit Report

## Corrective scope
- Fixed Case Analysis export regression caused by missing `re` import in `exporters/common.py`.
- Preserved RC4 architecture: raw source trace, material evidence projection, strict merits gate, and contextual export fallback.
- Updated release identity from rc4 to rc5.

## Validation
- Python compileall: PASS
- Structural release audit: PASS
- Targeted `_case_export_sections()` scenarios: PASS
- Full pytest in sandbox: NOT RUN (Flask dependency unavailable)

Expected Windows release_check target: 158 passed, 0 failed.
