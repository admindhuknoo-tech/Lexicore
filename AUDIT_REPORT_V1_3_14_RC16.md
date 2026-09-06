# LexiCore v1.3.14-rc16 — Client Communication Lifecycle

## Scope
Menu 8 Client Communication diubah dari form datar menjadi lifecycle 4 tahap yang memberi arah jelas kepada pengguna awal.

1. Identitas & Matter — validasi ID klien, nama, WhatsApp, dan matter; CTA Lanjut.
2. Status, Dokumen & Tenggat — isi perkembangan/instruksi; CTA Buat Client Document.
3. Client Document — review/edit hasil; Simpan Draft, Kirim WhatsApp, Export, dan Lihat Riwayat.
4. Riwayat Komunikasi — buka dokumen tersimpan atau mulai komunikasi baru.

## Guardrails
- WhatsApp tidak dapat dikirim tanpa dokumen yang tersedia.
- Jika dokumen belum disimpan, pengiriman WhatsApp menyimpan draft terlebih dahulu agar audit trail tidak hilang.
- Pembaruan perkara meminta progres/status; permintaan dokumen meminta tenggat.
- Review riwayat membuka langsung tahap Client Document.
- Tidak ada perubahan pada OCR, Case Analysis reasoning, regulatory retrieval, Evidence Map, atau database schema.
