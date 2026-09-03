# LexiCore v1.3.5.1 — Dynamic Case-Scoped Regulatory Retrieval

Perubahan arsitektur: Regulatory Corpus tidak lagi diarahkan untuk tumbuh menjadi database nasional yang besar. Korpus lokal v1.3.5 dipertahankan sebagai **core regulatory seed/fallback**. Saat Case Analysis dijalankan, LexiCore mendeteksi ruang lingkup perkara, membentuk query terarah/qualified, merutekan pencarian ke sumber resmi yang relevan, lalu menyimpan **snapshot metadata ringan per case**.

## Alur

`Case input → domain detection → qualified query builder → relevant official source routing → official discovery → core seed fallback → case-scoped snapshot → analysis/norm-conflict handoff`

Snapshot hanya menyimpan metadata hasil (judul, URL sumber resmi, instansi, query, timestamp, hash), bukan mengarsipkan seluruh isi regulasi. Tujuannya menjaga audit trail tanpa membuat `lexicore.db` menjadi gudang regulasi nasional.

## Sumber sektoral baru

- JDIH / Regulasi OJK untuk jasa keuangan.
- JDIH Kemnaker untuk ketenagakerjaan.
- BPK, MA, MK, Kemenkum, Setneg, Kemendagri tetap dipakai sesuai domain.
- JDIHN tetap directory-only dan tidak dihitung sebagai sumber otoritatif.

## Database

Schema naik ke **3** dengan tabel `case_regulatory_snapshots`. Migration framework v1.3.4 otomatis membuat backup sebelum perubahan schema dan memvalidasi `EXPECTED_COLUMNS`.

## Mode

- `DYNAMIC_CASE_SCOPED`: pencarian resmi case-specific aktif.
- `DYNAMIC_CASE_SCOPED_NO_MATCH`: pencarian dilakukan tetapi belum ada hasil.
- `LOCAL_SEED_FALLBACK`: online retrieval dimatikan; core seed tetap digunakan.

Semua hasil tetap `Professional Verification: PENDING` sampai diverifikasi lawyer.
