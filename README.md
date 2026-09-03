# LexiCore Patch v1.3.5.3

BAP Benchmark & Full-Document Pipeline Corrective.

Overlay ke baseline v1.3.5.2. Patch hanya berisi file yang berubah; tidak membawa `lexicore.db`.

Setelah overlay:

```bat
release_check.bat
py app.py
```

Target `/api/health`: version `1.3.5.3`, schema_version tetap `3`.

Kemudian ulangi benchmark BAP 36 halaman dan export PDF/DOCX. Freeze hanya jika release gate PASS dan benchmark substansial sesuai.
