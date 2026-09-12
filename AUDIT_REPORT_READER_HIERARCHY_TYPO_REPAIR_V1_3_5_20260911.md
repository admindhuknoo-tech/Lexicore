# LexiCore Audit Report — Reader Hierarchy & Typographic Repair v1.3.5

## Scope
Presentation/export layer only.

## Changes
1. Reader section order changed to:
   - Konteks Perkara, Duduk Perkara, dan Sumber
   - Kesiapan dan Kelengkapan Analisis
   - Pemetaan Bukti
   - Ringkasan Analisis Hukum
   - subsequent analytical sections in established order.
2. The prior Ringkasan Analisis Hukum is no longer the opening Roman section; it is rendered immediately after Pemetaan Bukti when an evidence map exists.
3. Added bounded reader-facing OCR typography repair for observed joined-word artifacts (for example `Kredityang`, `diberikankepada`, `DirekturUtama`, `ditandatanganioleh`).
4. Added narrow punctuation-spacing repair after commas/semicolons when followed immediately by alphabetic text.

## Invariants
No change to SAL, semantic admission, route-token rules, evidence authority, legal reasoning chain, tempus logic, positive-law verification, candidate-law governance, orchestration, persistence, or canonical source ledger. Raw/canonical source text remains unchanged; repair is export-string projection only.

## Validation
- Python compile: PASS
- Targeted presentation/export tests: 13 PASS
- Structural release audit: PASS (`v1.3.14-rc18`, templates=43, regulations=48)
- Full non-smoke regression: 422 PASS in 27.75s
