# LexiCore RC18 — Tempus Statute-Year / Procedural-Date Ownership Fix

## Trigger
Windows `release_check.bat` reported:
`test_r30_material_tempus_rejects_vehicle_year_procedural_date_and_statute_year`
expected `MATERIAL_TEMPUS_UNKNOWN`, but the extractor returned `MATERIAL_TEMPUS_CANDIDATE`.

## Root cause
The candidate incorrectly promoted was `1999` from `Undang-Undang Nomor 31 Tahun 1999`, not the 31 August 2026 hearing date.
A two-segment OCR context joined the allegation sentence with a following sentence containing temporal language, allowing the statute year to inherit a material-event score.

## Production correction
Only `services/material_tempus_extractor.py`:
1. Adds candidate-local statute-identity year rejection. A year token bound to an instrument identity (`UU ... Tahun YYYY`, shorthand type/number/year, etc.) cannot become material tempus.
2. Prevents an explicitly procedural date-bearing segment from handing its date to an adjacent generic material-event segment during OCR window merging.
3. Preserves OCR line-break recovery for the intended inverse pattern: event line followed by a bare date line.

## Preserved invariants
- OCR pipeline unchanged.
- Positive-law verification unchanged.
- Tempus remains candidate discovery only; no automatic `tempus_verified` or `applicable` promotion.
- Competing material dates remain fail-closed.
- Existing R30.1 credit-agreement material date behavior remains preserved.

## Focused validation
- `python -m py_compile services/material_tempus_extractor.py`: PASS
- `tests/test_tempus_extraction_closure.py`: 12 PASS
- Direct reproduction of the Windows failing sample: `MATERIAL_TEMPUS_UNKNOWN`: PASS

Windows `release_check.bat` remains the authoritative full-suite gate.
