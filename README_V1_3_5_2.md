# LexiCore v1.3.5.2 — Case-Aware Regulatory Precision Fix

Patch ini dibangun di atas **v1.3.5.1** dan memperbaiki temuan benchmark BAP sebelum regulatory architecture difreeze.

## Fokus koreksi

1. **AI provenance tunggal per Case Analysis**
   - hasil case menyimpan `analysis_provenance`;
   - mode aktual dibedakan menjadi `GEMINI_FULL_DOCUMENT`, `GEMINI_FULL_DOCUMENT_PARTIAL`, atau `DETERMINISTIC_FALLBACK`;
   - PDF/DOCX dan UI membaca provenance run yang sama, bukan menebak dari health endpoint.

2. **Case-aware domain scoring**
   - entitas kuat seperti BPR/OJK/POJK/BMPK/Tipikor mempunyai bobot lebih tinggi;
   - kata generik `perjanjian`, `utang`, `perusahaan`, atau `direksi` tidak boleh mengalahkan domain sektoral yang dominan.

3. **Issue-driven qualified queries**
   - regulation-qualified references diprioritaskan;
   - query domain/isu didahulukan dari generic discovery;
   - bare `Pasal N` tetap ditolak;
   - pada perkara BPR/Tipikor ditambahkan jalur tata kelola kredit, manajemen risiko, kewenangan Direksi, kerugian negara, dan tempus delicti.

4. **Tempus screening awal**
   - LexiCore mendeteksi kandidat tahun peristiwa dengan frequency + material-context weighting;
   - hasil pasca-peristiwa diberi `POST_EVENT_REFERENCE` dan tidak dihitung sebagai lolos screening tempus awal;
   - screening ini tidak menyatakan norma final berlaku tanpa verifikasi profesional.

5. **Regulatory retrieval funnel**
   - `discovered`
   - `unique_discovered`
   - `candidate`
   - `materially_relevant`
   - `temporal_not_excluded`
   - `authoritative_source_located`
   - `temporal_verified_applicable`

6. **Professional export cleanup**
   - Section menjadi **Verifikasi Sumber Hukum Resmi**;
   - tidak lagi mencetak daftar query generik sebagai hasil utama;
   - source reachable/source located dibedakan dari norma yang benar-benar terverifikasi berlaku;
   - metadata export mencantumkan AI Provider/Model dan provenance mode aktual.

## Benchmark BAP EDA

Pada dokumen benchmark 36 halaman yang digunakan selama pengembangan, precision layer mendeteksi:

- kandidat tempus: **2022**;
- domain utama: **Perbankan/Jasa Keuangan**;
- domain terkait: Pidana/Acara Pidana, Pemerintahan Daerah/BUMD, Tipikor;
- generic Perdata/Corporate tidak lagi menjadi jalur utama hanya karena terdapat kata perjanjian/utang/direksi.

Contoh query terarah yang dihasilkan:

- `BPR tata kelola Direksi persetujuan kredit`
- `POJK BPR manajemen risiko kredit`
- `tempus delicti 2022 asas legalitas ketentuan pidana`
- `Perumda BPR kewenangan Direksi persetujuan kredit tata kelola`
- `BPR kredit penyalahgunaan kewenangan kerugian negara Tipikor`

## Schema

Tidak ada perubahan database schema. `schema_version` tetap **3**.

## Release gate

Setelah overlay patch ke root project:

```bat
release_check.bat
```

Patch hanya boleh difreeze jika seluruh test kembali PASS.
