# LexiCore v1.3.14-rc7 — Audit Report

## Scope
RC7 memisahkan kontrak status mesin internal dari label laporan lawyer-facing.

## Corrective
- Mesin tetap menyimpan `POST_TEMPUS_EXCLUDED` dan `TEMPUS_REQUIRES_EXACT_DATE` sebagai status deterministik internal.
- PDF/DOCX tidak menampilkan kode internal tersebut; output menggunakan bahasa profesional:
  - `Terbit setelah peristiwa — tidak dipakai sebagai dasar materiil`
  - `Tanggal perbuatan harus dipastikan`
- Regression tests diperbarui agar menguji dua lapis secara terpisah: machine contract dan lawyer-facing contract.

## Validation
- Python compile: PASS
- Structural release audit: PASS
- Direct tempus status contract: PASS
- Lawyer-facing translation contract: PASS
- Full Flask smoke suite: wajib dijalankan pada environment lokal pengguna.
