# LexiCore Release Policy

LexiCore tidak lagi memakai nomor versi sebagai catatan setiap patch kecil.
Identitas produk, versi rilis, dan identitas build dipisahkan agar koreksi teknis tidak merusak UI/test contract.

## Identitas tetap
- Product name: `LexiCore`
- Product label: `LexiCore Assistant`
- Firm: `ELF - Erfan's Law Firm`

`PRODUCT_LABEL` tidak membawa nomor versi dan tidak boleh berubah hanya karena corrective build.

## Versi rilis
`PUBLIC_VERSION` berubah hanya ketika ada milestone fitur/arsitektur yang sengaja dirilis.
`RELEASE_CHANNEL` menggunakan `RC` selama stabilization gate belum dibekukan sebagai stable.
`RELEASE_SEQUENCE` berubah ketika RC baru sengaja diterbitkan.

Contoh: `1.3.14-rc1`.

## Build identity
`BUILD_ID` adalah metadata operasional. Nilainya dapat dioverride melalui `LEXICORE_BUILD_ID` tanpa mengubah source atau test.
Build identity hanya untuk health, audit, manifest, dan troubleshooting; bukan label produk.

## Release gate
Satu build hanya boleh disebut release candidate bila:
1. Python compile PASS.
2. Structural audit PASS.
3. OCR readiness PASS.
4. Seluruh smoke/regression test PASS.
5. Tidak ada duplicate project tree, test-backup leakage, `__pycache__`, atau artefak patch di paket distribusi.
6. Case Analysis invariants tetap fail-closed: evidence nexus, tempus, instrument identity, case nexus, dan provision verification.

## Distribusi
Jangan lagi menumpuk patch ke instalasi produksi. Gunakan `build_release.bat` untuk menghasilkan paket bersih dari satu baseline source.
Patch hanya digunakan untuk diagnosis sementara; kandidat yang akan diuji lokal harus berupa clean full-project build.
