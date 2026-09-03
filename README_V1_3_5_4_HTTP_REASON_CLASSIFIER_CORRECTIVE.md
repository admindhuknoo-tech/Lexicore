# LexiCore v1.3.5.4 — HTTP Reason Classifier Corrective

Corrective internal tanpa kenaikan versi.

Perubahan:
- `ai_engine.py` sekarang tetap mengklasifikasikan HTTP status secara spesifik walaupun error dari layer bawah dibungkus menjadi `RuntimeError("Gemini HTTP 429: ...")`.
- Contoh: `Gemini HTTP 429: quota` -> `HTTP_429_RATE_LIMIT`.
- Tidak ada perubahan schema database.
- Tidak ada perubahan API publik.
- Version tetap `1.3.5.4`, schema version tetap `3`.

Setelah overlay, jalankan:

    release_check.bat

Target: 45 passed, 0 failed.
