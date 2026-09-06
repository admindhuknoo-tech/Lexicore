# LexiCore v1.3.14-rc15 — Case Completion Guidance & User-Facing Source Status

## Scope
Presentation-layer refinement only. No changes to OCR, Case Analysis reasoning, Evidence Map logic, Professional Review, database schema, regulatory gates, or export semantics.

## Implemented
- Success notification after Evidence-to-Action analysis completes.
- Clear CTA: **Lihat Working Paper**.
- Working Paper outer submenu receives a subtle **Siap** indicator after successful analysis.
- Official-source connectivity codes are translated to user-facing Indonesian labels.
- Raw HTTP/status codes are no longer shown in the source connectivity cards.
- Failure message for source health is user-facing rather than exposing transport details.

## Connectivity language examples
- REACHABLE -> Sumber dapat diakses
- AUTOMATION_BLOCKED_403 -> Akses otomatis dibatasi oleh situs
- TIMEOUT -> Sumber belum merespons tepat waktu
- SSL_VALIDATION_ERROR -> Koneksi aman belum dapat diverifikasi
- DNS_RESOLUTION_ERROR -> Alamat sumber belum dapat dijangkau

## Release
`1.3.14-rc15`
