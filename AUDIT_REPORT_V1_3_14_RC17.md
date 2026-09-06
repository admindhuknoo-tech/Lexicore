# LexiCore v1.3.14-rc17 — Case Analysis Stabilization Audit

## Scope
RC17 implements the eight Case Analysis findings from the Elya benchmark without changing OCR, database lifecycle, positive-law verification gates, or Client Communication lifecycle.

## Implemented corrections
1. **Evidence Taxonomy V2** — separates `PLEADED_FACT`, `ALLEGED_ROLE`, `EVIDENCE_ASSERTION`, `CASE_FACT`, and `ACTUAL_EVIDENTIARY_ITEM`; headings, metadata, legal argument and prayers remain non-merits classes.
2. **Probative Weight Guard** — semantic relevance no longer equals evidentiary sufficiency. Actual-loss, causation, intent and responsibility issues have issue-specific sufficiency gates.
3. **Source Ledger Hygiene V2** — lawyer-facing material ledger excludes headings, legal arguments, procedural metadata, personal metadata, prayers and non-material fragments.
4. **Legal Construction language cleanup** — internal classes/statuses remain machine-readable internally but are translated in UI/PDF/DOCX.
5. **Professional Review terminology cleanup** — finding names and document types use lawyer-facing Indonesian labels.
6. **Applicable-law presentation** — when no regulation is fully verified applicable, the report section is explicitly titled **Kandidat Dasar Hukum yang Perlu Diverifikasi**.
7. **Official-source presentation cleanup** — discovery/status/provision wording is translated to user-facing Indonesian; raw internal status strings are not projected to the report.
8. **Two-layer professional output** — Executive Legal Review remains concise; detailed evidence/legal/audit trace is grouped under Working Paper Terperinci, while Ringkasan Eksekutif is shortened to avoid repetition.

## Validation performed in build environment
- `python -m compileall -q .` — PASS
- Inline JavaScript syntax parse — PASS
- `python tools/release_audit.py` — PASS
- Evidence Taxonomy V2 targeted cases — PASS
- Source-ledger heading/argument exclusion — PASS
- Actual-loss semantic-vs-probative guard — PASS
- Legal Construction `SEMANTIC_NEXUS_ONLY` gate — PASS
- Lawyer-facing export leakage check — PASS

## Full local validation required
Run `release_check.bat` on the Windows LexiCore environment. Full Flask smoke/regression execution is not available in the build environment used here.
