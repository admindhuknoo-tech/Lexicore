# LexiCore Assistant

**Release:** `1.3.14-rc17`  
**Initiative:** Evidence-to-Action Legal Intelligence  
**Firm:** ELF - Erfan's Law Firm

LexiCore Assistant adalah lawyer-assistance workspace dengan delapan area kerja: Legal Drafting, Contract Review, Regulatory Corpus, Legal Research, Compliance & Risk, Case Analysis, Norm Conflicts, dan Client Communication.

## Release model baru
Mulai release ini, identitas produk dipisahkan dari identitas teknis:

- `PRODUCT_LABEL = LexiCore Assistant` — stabil, tidak berubah setiap corrective build.
- `PUBLIC_VERSION = 1.3.14` — berubah hanya pada milestone rilis.
- `LEXICORE_VERSION = 1.3.14-rc17` — identitas release candidate teknis.
- `BUILD_ID` — metadata build/deployment, dapat dioverride melalui `LEXICORE_BUILD_ID` tanpa mengubah source atau test.

Kebijakan lengkap ada di `RELEASE_POLICY.md`.

## Release gate
Jalankan:

```bat
release_check.bat
```

Gate mencakup Python compile, structural audit, OCR readiness, dan seluruh smoke/regression tests.

Untuk menghasilkan clean full-project ZIP setelah seluruh gate PASS:

```bat
build_release.bat
```

Builder tidak memasukkan nested patch tree, cache Python/pytest, backup test, atau artefak development ke distribusi.

## Prinsip Case Analysis
Case Analysis menggunakan pendekatan fail-closed:

`FAKTA SUMBER → ISU → NEXUS → IDENTITAS/STATUS NORMA → TEMPUS → UNSUR/ATRIBUSI → KESIMPULAN BERSYARAT`

Tidak ada kesimpulan domain-spesifik tanpa nexus yang cukup. Tidak ada norma materiil dinyatakan applicable sebelum identitas instrumen, status, tempus, dan case nexus memadai. Professional Verification tetap PENDING sampai lawyer memverifikasi hasil.


## RC2 — Evidence Hygiene
RC2 memisahkan raw source trace dari user-facing evidence. Evidence Map hanya boleh memuat dokumen/bukti primer yang disebut, klaim substantif mengenai bukti, atau fakta perkara material. Identitas/kontak penasihat hukum, alamat kantor, metadata pendaftaran, nomor perkara, petitum, argumentasi hukum, dan fragmen angka tidak boleh muncul sebagai fakta yang dibuktikan.

User-facing report memakai `material_source_ledger`; `source_ledger` mentah tetap dipertahankan hanya untuk audit internal. Official-search noise juga tidak ditampilkan sebagai Regulasi & Tempus kecuali identitas instrumen dan case nexus telah terverifikasi.


## RC4 — Professional Legal Review Engine
Case Analysis kini menjalankan review multipass: klasifikasi dokumen, pemisahan fakta/argumentasi/metadata, deteksi typo dan inkonsistensi nama/tanggal/rujukan, legal gates, adversarial weakness review, serta rekomendasi prioritas. Semua koreksi bersifat kandidat dan wajib diverifikasi terhadap dokumen primer.



## RC8 — Dual Sticky Workspace Header & Horizontal Case Rail

RC8 menetapkan pola navigasi visual yang konsisten untuk seluruh 8 modul. Header utama LexiCore + 8 menu tetap sticky pada layout responsif, dan header workspace aktif (mis. **Case Analysis & Hypotheses**) menjadi sticky tepat di bawahnya. Offset dihitung dari tinggi header aktual agar tidak overlap pada ukuran layar yang berbeda.

Pada Menu 6, kontrol **Case Readiness / Evidence Map / Legal Construction / Action Plan / Export PDF / Export DOCX** sekarang selalu berupa rail horizontal dengan geser kanan/kiri, termasuk pada layar sempit.

## RC7 — Machine Status / Lawyer Output Contract

RC7 memisahkan secara tegas status mesin internal dari label laporan lawyer-facing. Status seperti `POST_TEMPUS_EXCLUDED` dan `TEMPUS_REQUIRES_EXACT_DATE` tetap dipertahankan untuk logika, audit, dan test mesin, tetapi PDF/DOCX menampilkan bahasa profesional yang mudah dibaca.

## RC6 — Professional Output Architecture
- Winning-probability wording removed from Case Analysis; the percentage now means Case Readiness / Analysis Completeness.
- Executive Legal Review is placed before diagnostic detail in PDF/DOCX exports.
- Lawyer-facing source context is privacy-compact; raw source remains available only in the internal trace/ledger.
- Internal status codes in regulatory/time sections are translated into professional wording.
- Executive-summary clipping is sentence-safe to avoid half-sentence output.
- Legal-only professional disclaimer remains mandatory.


## RC9 — Sticky Layout Stabilization

RC9 memperbaiki regresi RC8: aturan sticky/horizontal rail sebelumnya tidak masuk ke stylesheet aplikasi karena tersisip di template style Export PDF. RC9 memindahkan aturan ke stylesheet global, menghapus `overflow:hidden` pada `.main` di layout responsif yang memutus sticky positioning, mempertahankan header LexiCore + 8 menu sebagai header primer, menempatkan header workspace aktif tepat di bawahnya, dan memaksa rail Working Paper Case Analysis tetap horizontal dengan scrollbar/touch/wheel.


## RC12 — Two-Layer Sticky Contract

RC12 menetapkan kontrak layout yang eksplisit: hanya header primer LexiCore + 8 menu dan header judul workspace aktif yang sticky/freeze. Semua submenu/section navigation di bawah judul workspace kembali menjadi konten normal yang ikut bergerak saat halaman discroll. Rail Working Paper Case Analysis tetap horizontal kiri/kanan tetapi tidak sticky.


## RC12 layout contract
Pada layout responsif, area beku terdiri dari dua zona visual: header utama LexiCore/8 menu dan header modul yang mencakup judul modul serta empat submenu bagian. Konten di bawahnya tetap bergulir normal. Rail Working Paper Case Analysis tetap horizontal dan bukan bagian dari header beku.


## RC13 UI Freeze Clarification
The secondary frozen area is a single bounded stack consisting of the active module title/status row plus the module four-tab navigation. A strong bottom rule marks the freeze boundary; everything below remains normal-flow.


## RC14 — Soft Edge Frozen Workspace
Frozen module title + four submenu tabs retain the RC13 behavior, but the hard divider is replaced by a subtle edge boundary: translucent surface, hairline gradient, and low-elevation shadow. No reasoning/backend behavior changed.


### RC15 — Completion guidance & user-facing status
- Setelah Evidence-to-Action selesai, UI menampilkan notifikasi **Analisis selesai** dengan aksi **Lihat Working Paper**.
- Submenu Working Paper diberi indikator halus **Siap** setelah hasil tersedia.
- Status konektivitas sumber resmi diterjemahkan menjadi bahasa pengguna; kode transport/HTTP tidak ditampilkan mentah pada kartu sumber.
- Status hukum dan keterkaitan perkara di Case Analysis memakai label lawyer-facing, sementara kode internal tetap dipertahankan pada payload/audit layer.


### RC17 — Case Analysis Evidence Taxonomy & Probative Weight Guard

- Evidence Taxonomy V2 membedakan fakta yang didalilkan, peran/jabatan yang didalilkan, klaim keberadaan bukti, fakta perkara, dan bukti primer.
- Probative Weight Guard memisahkan keterkaitan semantik dari daya bukti/kemampuan membuktikan unsur.
- Jejak Sumber Material tidak lagi memuat heading, argumentasi hukum, petitum, metadata prosedural, atau fragmen nonmaterial.
- Legal Construction, Professional Review, dasar hukum, dan verifikasi sumber memakai bahasa lawyer-facing.
- Jika belum ada norma yang lolos gate, bagian hukum ditandai sebagai kandidat yang masih perlu diverifikasi.
- Executive Legal Review tetap menjadi lapisan ringkas; detail working paper dipertahankan untuk audit.

### RC16 — Guided Client Communication Lifecycle
- Menu 8 kini memiliki alur eksplisit 4 tahap: **Identitas & Matter → Status & Instruksi → Client Document → Riwayat Komunikasi**.
- Tahap 1 memiliki CTA **Lanjut: Status & Instruksi** dengan validasi identitas/WhatsApp/matter.
- Tahap 2 memiliki CTA **Buat Client Document**; setelah generator selesai, UI otomatis membuka tahap review dokumen.
- Tahap 3 menyediakan **Simpan Draft**, **Kirim WhatsApp**, export, edit data, dan akses riwayat.
- Pengiriman WhatsApp memastikan draft sudah tersimpan terlebih dahulu agar jejak komunikasi tidak hilang.
- Riwayat dapat membuka dokumen langsung ke tahap review atau memulai **Komunikasi Baru**.
