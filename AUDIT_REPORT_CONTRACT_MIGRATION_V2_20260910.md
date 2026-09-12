# LexiCore V2.3.1 - Benchmark & Contract Migration Audit V2

Tanggal audit: 2026-09-10

## Scope

Audit membandingkan dua output aktual LexiCore dan menelusuri producer -> orchestration/API -> persistence -> UI -> exporter -> benchmark -> tests. Target kontrak analitis wajib adalah:

`Issue -> Applicable Law -> Legal Elements -> Alleged Act -> Evidence -> Counter-Evidence -> Element Test -> Causation -> Risk -> Procedural/Merits Classification -> Recommended Action`

Perubahan diperlakukan sebagai contract migration lintas-layer, bukan patch kosmetik pada PDF.

## Benchmark dua output sebelum migration

| Dimensi | 0731 - Eksepsi Elya / Tipikor | 0729 - Duplik Perdata | Putusan audit |
|---|---|---|---|
| Domain/posture fidelity | Domain Tipikor/perbankan/pidana terdeteksi baik; eksepsi dikenali | Isu prosedural/pertanahan/PA terdeteksi, tetapi subtype Duplik direduksi menjadi Jawaban Gugatan | PARTIAL / FAIL |
| Applicable-law/tempus gate | Fail-closed kuat: tempus belum terverifikasi, norma final tidak dipromosikan | Fail-closed kuat: hukum positif belum boleh dinyatakan applicable | PASS |
| Legal elements | Ada element matrix, tetapi mapping `personal responsibility` dapat ditopang metadata perkara/pertanyaan fidusia yang tidak membuktikan atribusi personal | Element engine beralih ke template kontrak/wanprestasi walau isu utama kompetensi, waris, pertanahan | PARTIAL / FAIL |
| Alleged act | Tersebar di issue analysis/evidence mapping, belum menjadi node kontrak kanonik | Tidak diproyeksikan secara konsisten terhadap tiap unsur | PARTIAL / FAIL |
| Evidence & counter-evidence | Ada mapping, tetapi lexical/topical matching dapat menaikkan sumber lemah | Banyak elemen 0%; fakta penting sumber tidak menjadi rantai unsur yang relevan | PARTIAL / FAIL |
| Element test | Tersedia, namun bukan satu rantai 11-stage yang persisted | Salah domain element template membuat test tidak menjawab isu perkara | PARTIAL / FAIL |
| Causation | `PARTIAL_NEXUS_IDENTIFIED` dapat muncul dari dukungan topikal yang lemah | `NEXUS_NOT_ESTABLISHED` lebih konservatif, tetapi tetap terpisah dari node unsur | PARTIAL |
| Procedural vs merits | Guard cukup baik dan secara eksplisit memisahkan forum dari merits | Kontaminasi template pidana: rekomendasi menyebut dakwaan/surat dakwaan pada Duplik perdata | PASS / FAIL |
| Recommended action traceability | Action plan ada tetapi tidak secara eksplisit satu-ke-satu dengan semua node rantai | Action plan ada, tetapi upstream issue/element mismatch menurunkan traceability | PARTIAL |
| Single canonical contract | Tidak ada objek runtime tunggal yang melewati seluruh layer | Tidak ada objek runtime tunggal yang melewati seluruh layer | FAIL |

## Root cause

1. `services/legal_reasoning_chain.py` sudah memiliki bentuk rantai 11-stage, tetapi sebelumnya tidak di-wire ke pipeline utama sehingga bukan kontrak persisted yang dipakai UI/exporter.
2. `services/case_benchmark.py` memeriksa key `classification`, sedangkan contract row memakai `procedural_merits_classification`; akibatnya benchmark full-chain tidak merepresentasikan schema aktual.
3. `services/element_reasoning.py` berhenti pada domain aktif pertama. Pada sengketa multi-domain, isu prosedural/pertanahan/Peradilan Agama dapat terdeteksi, tetapi unsur kemudian diproyeksikan dari template domain lain.
4. Domain luas `civil_contract` mencakup pola PMH sehingga gugatan PMH dapat salah dipaksa ke unsur wanprestasi/perjanjian.
5. `document_posture_resolver.py` belum mempertahankan subtype eksplisit `DUPLIK`/`REPLIK` untuk projection layer.
6. Exporter dan UI menampilkan fragmen issue/element/evidence/causation/risk, tetapi tidak merender satu objek canonical legal reasoning chain yang sama.

## Contract Migration V2 yang diterapkan

### Canonical schema

`services/reasoning_contract.py` menetapkan `CONTRACT_VERSION = 2.0`, urutan 11 stage, validator fail-closed, dan attachment function yang membangun lalu memvalidasi `legal_reasoning_chain` serta `reasoning_contract`.

### Producer / reasoning layer

- `services/legal_reasoning_chain.py` dinaikkan ke engine V2.
- Evidence memprioritaskan supporting evidence yang sudah dipetakan oleh element mapper sebelum fallback lexical ledger projection.
- Counter-evidence dinormalisasi sebagai struktur list/dict, bukan stringified aggregate.
- Causation membaca structured `causation_analysis` dan menjaga `NEXUS_NOT_ESTABLISHED`/`NOT_ASSESSED` sebagai GAP.
- Procedural/merits classification diperluas agar issue dan element dapat diklasifikasikan `PROCEDURAL`, `MERITS`, atau `MIXED`.

### Cross-domain element contract

- `services/element_reasoning.py` sekarang menggabungkan issue/element templates dari seluruh active reasoning domains; tidak lagi berhenti pada domain pertama.
- Ditambahkan template `civil_procedure`, `land_property`, `religious_court`, dan internal `civil_tort`.
- PMH dapat dipisahkan dari generic contract/wanprestasi untuk tujuan element testing tanpa mengubah retrieval-domain contract.

### Posture contract

- `services/document_posture_resolver.py` mengenali `DUPLIK` dan `REPLIK` sebagai subtype reader-facing sambil mempertahankan posture canonical response-to-complaint.
- Ini mencegah Duplik diproyeksikan sebagai dokumen generik dan mengurangi risiko template pidana bocor ke konteks perdata.

### Orchestration / persistence

- `routes/case_analysis.py` memanggil `attach_reasoning_contract(result)` sebelum persistence.
- Konsekuensinya, canonical chain yang sama tersedia untuk API response, persisted analysis object, UI, dan exporter.

### Projection / export

- `exporters/common.py` menambahkan section `Canonical Legal Reasoning Chain`, dibaca langsung dari persisted `legal_reasoning_chain` dan menampilkan seluruh 11 stage.
- `static/index.html` menampilkan chain yang sama berikut contract version/status.
- Projection tidak menghitung ulang chain sendiri, sehingga tidak membuka divergence antara API, layar, dan PDF/DOCX.

### Benchmark / tests

- `services/case_benchmark.py` memakai nama field canonical `procedural_merits_classification` dan validator contract V2.
- `tests/test_reasoning_contract_migration_v2.py` mengunci tiga regresi: multi-domain civil merge, subtype Duplik, dan kelengkapan 11-stage + semantics causation GAP.

## Contract migration map

| Layer | Contract sebelum | Contract sesudah | Risiko yang ditutup |
|---|---|---|---|
| Domain classifier | multi-domain tersedia | tetap | tidak mengubah retrieval semantics |
| Element producer | first-domain wins | merge active domains + PMH refinement | wrong-law/wrong-element projection |
| Reasoning chain | utility terpisah | canonical V2 producer | fragmented reasoning |
| Route/orchestrator | tidak attach chain | attach + validate sebelum save | API/persistence divergence |
| Persistence | fragment fields | fragment fields + canonical chain | re-computation drift |
| UI | render fragment | render canonical persisted chain | reader mismatch |
| PDF/DOCX exporter | render fragment | render canonical persisted chain | export mismatch |
| Benchmark | wrong schema key | canonical validator | false benchmark result |
| Tests | belum mengunci migration | contract regression tests | silent cross-layer regression |

## Validation

- Targeted contract/regression tests: PASS.
- Seluruh suite yang dapat dikoleksi tanpa Flask smoke dependency: `273 passed`.
- `tests/test_smoke.py` tidak dapat dikoleksi di sandbox audit karena dependency `flask` tidak terpasang pada environment audit. Ini merupakan limitation environment, bukan hasil fail test aplikasi.
- Python compile check dijalankan setelah perubahan.

## Catatan engineering

Migration ini sengaja tidak merefaktor arsitektur besar, tidak mengubah positive-law verification gate, dan tidak mempromosikan norma menjadi applicable tanpa tempus/source verification. Tujuannya menutup divergence lintas-layer dan memaksa setiap reasoning row memiliki jalur yang dapat diaudit dari issue sampai recommended action.
