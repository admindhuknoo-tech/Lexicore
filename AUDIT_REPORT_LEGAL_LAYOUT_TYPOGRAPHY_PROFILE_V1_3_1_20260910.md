# LexiCore Legal Layout & Typography Profile v1.3.1

## Scope
Presentation/export layer only. No change to SAL, orchestration, retrieval, evidence admission, positive-law verification, tempus, canonical reasoning, persistence, or substantive legal logic.

## Selective integration
Changed only:
- `exporters/case_pdf.py`
- `exporters/case_docx.py`
- `tests/test_low_level_render_governor_v128.py` (render-text assertion made whitespace-safe for narrower legal page geometry)
- `tests/test_legal_layout_typography_v131.py` (new regression coverage)

## Layout profile
- F4 page: 215 mm x 330 mm
- Margins: top 40 mm, left 40 mm, bottom 30 mm, right 30 mm
- Main legal body: Times / Times New Roman, 12 pt
- Narrative body: justified, 1.5 line spacing, 12 mm first-line indent
- Structured records, labels, metadata, tables, bullets, header/footer: no first-line indent
- Chapter headings: 14 pt bold uppercase, centered, Roman numerals

## LexiCore-specific selective decisions
- Existing LexiCore masthead/brand identity preserved rather than converted into pleading text.
- Masthead and metadata widths recalculated to the 145 mm text area created by F4 + 40/30 mm side margins.
- Legal outline numbering is applied to top-level export sections only. Lower-level A./1./a. labels are not fabricated because the current export model does not carry reliable hierarchical level metadata.
- Structured canonical-chain rows remain unindented to preserve traceability and readability.
- Built-in ReportLab Times faces are used for PDF to avoid external font-file dependencies. DOCX uses Times New Roman.

## Verification
- `python -m py_compile exporters/case_pdf.py exporters/case_docx.py tests/test_legal_layout_typography_v131.py`: PASS
- Targeted export/layout/render regression: 15 PASS
- Full non-smoke suite (`pytest -q --ignore=tests/test_smoke.py`): 412 PASS
- Structural release audit: PASS (`v1.3.14-rc18`, templates=43, regulations=48)
- Smoke suite: NOT EXECUTED TO COMPLETION in this Linux container because `flask` is not installed; collection stops with `ModuleNotFoundError: flask`. No smoke PASS is claimed.
