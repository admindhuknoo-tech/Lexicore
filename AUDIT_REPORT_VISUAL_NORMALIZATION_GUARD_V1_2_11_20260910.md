# LexiCore Visual Normalization Guard v1.2.11

Scope: presentation/exporter layer only.

## Residuals closed
- `Domain:` -> `Ranah hukum:`
- `[CRITICAL]` -> `[KRITIS]`
- `Status review:` -> `Status penelaahan:`
- `Review ini` -> `Penelaahan ini`
- `Ringkasan Review Hukum` -> `Ringkasan Penelaahan Hukum`
- `diverifikasi lawyer` -> `diverifikasi profesional hukum`
- `Versi tampilan: ADV-VIEW-1.1` -> `Mode tampilan: Pemisahan posisi para pihak`
- `Versi kontrak:` -> `Versi struktur analisis:`
- `Status struktur:` -> `Kelengkapan struktur analisis:`
- `Status semantik:` -> `Status verifikasi analisis:`
- `Urutan wajib:` -> `Urutan analisis:`
- `tanggal cut-off` -> `tanggal batas perhitungan`

## Invariants preserved
- No SAL contract changes.
- No reasoning/orchestrator changes.
- No Evidence, Elements, Tempus, retrieval, Candidate Law or positive-law changes.
- Low-level render governor remains the final string boundary.
- Brand literals and legitimate legal Latin terms remain untouched.

## Validation
- `python -m py_compile`: PASS
- Structural release audit: PASS
- Targeted presentation/render/Candidate Law suite: 18 PASS
- Full non-smoke regression: 409 PASS
