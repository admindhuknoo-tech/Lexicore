# LexiCore v1.3.5.4 — Test Contract Corrective

Corrective internal tanpa kenaikan versi.

Perubahan:
- Menyesuaikan regression test `test_full_document_failure_exposes_auditable_reason` dengan kontrak diagnosis HTTP spesifik pada engine v1.3.5.4.
- Fixture `Gemini HTTP 429: quota` sekarang wajib menghasilkan `HTTP_429_RATE_LIMIT`, bukan label lama `HTTP_ERROR`.
- Tidak ada perubahan engine, database, schema, route, UI, atau fitur.

Setelah overlay patch, jalankan:

    release_check.bat

Target:

    45 passed
    0 failed
    LexiCore release gate: PASS
