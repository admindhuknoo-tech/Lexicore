# LexiCore RC18 — Reader Export Canonicalization Fix

## Root cause
The previous reader-facing export closure introduced `exporters/presentation.py`, while the structural release audit explicitly rejects that filename as regression debris. Removing the file alone then broke imports in `case_pdf.py`, `case_docx.py`, and the focused reader-facing test.

## Correction
- Moved the reader-facing presentation adapter into existing canonical `exporters/common.py`.
- Updated `case_pdf.py` and `case_docx.py` to import `prepare_case_export_for_reader` from `exporters.common`.
- Updated the focused test to use the canonical import.
- `exporters/presentation.py` is intentionally absent from this package.
- No changes to OCR, Tempus, Positive-Law verification, Regulatory Corpus, posture logic, or legal reasoning.

## Validation
- Python compile: PASS
- `tests/test_rc18_reader_facing_integration_closure.py`: 4 PASS
- `tools/release_audit.py`: PASS
- Full Flask smoke/release suite remains authoritative on Windows.
