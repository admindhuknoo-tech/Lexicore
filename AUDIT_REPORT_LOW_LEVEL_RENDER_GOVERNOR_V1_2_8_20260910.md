# LexiCore Low-Level Render Governor v1.2.8

Scope: exporter presentation boundary only.

## Root cause
Previous reader-facing sanitation happened upstream in `prepare_case_export_for_reader()`. Some strings and duplicate action lines could still reach the actual PDF/DOCX write loops unchanged. The final safeguard therefore had to be placed directly in the renderer loops that create ReportLab `Paragraph` objects and python-docx paragraphs/table cells.

## Selective integration
- Added `LexiCoreLowLevelRenderGovernor` in `exporters/common.py`.
- PDF renderer: every section line is intercepted immediately before `Paragraph(...)`; metadata/title/heading/brand strings are sanitized at the same boundary.
- DOCX renderer: every section line is intercepted immediately before `add_paragraph()` / `add_run()`; metadata/table cells/title/heading/brand strings are sanitized at the same boundary.
- Immediate duplicate actions are skipped only inside canonical/action sections using a single-line memory ledger. Memory resets on non-action lines and section transitions.
- Civil substitutions activate only when civil posture is positively resolved from the bounded presentation source corpus.
- Universal residue substitutions are exact final-render replacements and do not mutate canonical data.

## Invariants
No changes to SAL, Evidence, Elements, Candidate Law Governor, Positive-Law verification, Tempus, canonical reasoning persistence, or retrieval logic.

## Verification
- `python -m py_compile exporters/common.py exporters/case_pdf.py exporters/case_docx.py`: PASS
- `python tools/release_audit.py`: PASS
- Targeted presentation/retrieval regression suite: 29 PASS
- Actual PDF + DOCX low-level renderer interception tests: PASS
- Full non-smoke suite: 399 PASS
