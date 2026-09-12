# Consolidation Manifest — RC18 Reader Export Canonicalization Fix

Changed files only:
- exporters/common.py
- exporters/case_pdf.py
- exporters/case_docx.py
- tests/test_rc18_reader_facing_integration_closure.py

Intentional absence:
- exporters/presentation.py

This is a compatibility/hygiene correction only. It preserves the reader-facing export behavior from the prior closure while satisfying the structural release audit.
