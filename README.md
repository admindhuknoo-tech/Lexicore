# LEXICORE Patch v1.2.3 — Document Input Validation Fix

Perbaikan incremental dari v1.2.2.

## Perubahan
- Case Analysis menerima PDF/DOCX tanpa kewajiban mengisi narasi.
- Batas minimal 120 karakter hanya berlaku untuk mode **narasi tanpa dokumen**.
- Jika dokumen diunggah tetapi tidak memiliki teks yang dapat diekstrak, LexiCore memberi pesan khusus, bukan meminta narasi 120 karakter.
- UI menjelaskan bahwa narasi tidak wajib bila PDF/DOCX sudah dipilih.
- Tidak ada perubahan database, Official JDIH Federation, atau Deep Case Analysis logic.

## File berubah
- `app.py`
- `static/index.html`

## Instalasi
Replace dua file sesuai path project, restart `py app.py`, lalu hard refresh browser (`Ctrl+F5`).
