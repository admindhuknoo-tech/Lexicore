# LexiCore v1.3.4 — Case Context / Duduk Perkara & Section Hierarchy

## Scope
Selective exporter-layer correction only.

## Changes
- Expanded reader-facing section II from `Konteks Perkara dan Sumber` to `Konteks Perkara, Duduk Perkara, dan Sumber`.
- Added source-grounded projection for:
  - document/procedural status,
  - concise duduk perkara orientation,
  - articles expressly mentioned in the source,
  - statutes/instruments expressly mentioned in the source,
  - indictment/demand availability status,
  - explicit statement when sentence demand is not present.
- BAP guard: an investigation/interview record cannot be presented as if it were an indictment or prosecution demand.
- Removed the reader-facing `Analisis Terperinci` wrapper section because it only introduced the following analytical sections.
- Kept `Audit Dokumen Terperinci` as an independent substantive audit section.
- Roman numbering remains sequential because PDF/DOCX renderers enumerate the final section list at render time.

## Frozen / Unchanged
No changes to SAL, semantic admission, evidence admission, legal reasoning chain, tempus, positive-law verification, retrieval, candidate-law governor, orchestrator, persistence, or legal conclusions.

## Validation
- Python compile: PASS.
- Targeted exporter/presentation regression: 19 PASS.
- Structural release audit: PASS (`v1.3.14-rc18`, templates=43, regulations=48).
- Full non-smoke regression: 419 PASS.

## Important behavior
If the source is a BAP and does not contain a formal indictment or prosecution demand, the exporter must say so. It must not infer a requested prison term or convert mentioned legal provisions into a final charge.
