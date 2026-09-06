"""Deterministic compliance risk matrix for LexiCore.

v1.3.13.9 expands the category questionnaires using the user-supplied
Compliance & Risk Assessment framework plus a small set of cross-cutting
controls that were already present in LexiCore but are materially necessary
for a usable corporate risk profile.

This module performs issue spotting, not final legal advice. Exact article,
sanction quantum, sector applicability, tempus and licensing consequence must
remain subject to professional/source verification.
"""
from __future__ import annotations

from typing import Dict, List

CATEGORY_ALIASES = {
    "general corporate": "General Corporate",
    "tech/pdp": "Tech/PDP",
    "technology & data": "Tech/PDP",
    "technology and data": "Tech/PDP",
    "employment": "Employment",
    "commercial": "Commercial",
    "financial/aml": "Financial/AML",
    "financial / aml": "Financial/AML",
}

DEFAULT_OPTIONS = [
    {"value": "yes", "label": "Ya / tersedia"},
    {"value": "partial", "label": "Sebagian / perlu perbaikan"},
    {"value": "no", "label": "Tidak / belum tersedia"},
]


def O(*pairs):
    """Compact option builder: O((value,label), ...)."""
    return [{"value": v, "label": l} for v, l in pairs]


def R(key, group, question, risk, basis, sanctions, actions, *, options=None, severity="MEDIUM"):
    return dict(
        key=key,
        group=group,
        question=question,
        risk=risk,
        basis=basis,
        sanctions=sanctions,
        actions=actions,
        options=options or list(DEFAULT_OPTIONS),
        severity=severity,
    )


RULES = {
    "General Corporate": [
        R("legal_entity", "Legalitas & Tata Kelola", "Apakah status badan hukum, akta, AHU dan seluruh perubahan data korporasi sudah mutakhir?",
          "Ketidaksesuaian status badan hukum, kewenangan organ, atau data korporasi dengan keadaan aktual.",
          "UU Perseroan Terbatas dan ketentuan administrasi badan hukum/AHU yang relevan.",
          "Risiko administratif, penolakan layanan/aksi korporasi, sengketa kewenangan organ, dan tanggung jawab perdata; sanksi sektoral dapat mencakup pembekuan/pencabutan izin.",
          ["Cocokkan akta terakhir dengan data AHU", "Verifikasi kewenangan Direksi/Komisaris dan persetujuan organ yang diperlukan", "Perbarui perubahan data korporasi yang belum tercatat"], severity="HIGH"),
        R("license", "Legalitas & Tata Kelola", "Apakah NIB, perizinan berusaha dan izin sektoral tersedia, sesuai kegiatan aktual, dan masih berlaku?",
          "Menjalankan kegiatan usaha tanpa atau di luar ruang lingkup perizinan yang dipersyaratkan.",
          "Rezim Perizinan Berusaha Berbasis Risiko (OSS-RBA) dan regulasi sektoral.",
          "Dapat memicu sanksi administratif mulai teguran, penghentian kegiatan, pembekuan sampai pencabutan perizinan sesuai sektor.",
          ["Inventarisasi KBLI dan aktivitas aktual", "Cocokkan NIB/sertifikat standar/izin sektoral dengan aktivitas", "Buat kalender masa berlaku dan PIC perizinan"], severity="HIGH"),
        R("governance", "Legalitas & Tata Kelola", "Apakah keputusan material perusahaan terdokumentasi dalam persetujuan organ, notulen, dan matriks kewenangan yang jelas?",
          "Keputusan material berpotensi dipersoalkan karena melampaui kewenangan atau tidak memenuhi tata kelola internal.",
          "UU Perseroan Terbatas, anggaran dasar, dan kebijakan tata kelola internal.",
          "Eksposur utama berupa pembatalan/keberatan korporasi dan tanggung jawab perdata pengurus; konsekuensi administratif bergantung sektor.",
          ["Petakan reserved matters", "Lengkapi risalah RUPS/keputusan sirkuler/notulen Direksi-Komisaris", "Simpan approval matrix dan bukti konflik kepentingan"]),
        R("financial_tax", "Finansial & Perpajakan", "Apakah perusahaan rutin melakukan audit/review keuangan yang diperlukan dan melaporkan SPT Tahunan tepat waktu?",
          "Kelemahan kontrol keuangan dan keterlambatan kepatuhan perpajakan dapat menimbulkan koreksi, sengketa, dan eksposur sanksi.",
          "Ketentuan perpajakan, pembukuan, pelaporan keuangan, dan audit yang berlaku sesuai jenis/ukuran entitas.",
          "Dapat memicu bunga/denda administratif, koreksi pajak, pemeriksaan, sengketa pajak, atau konsekuensi lain sesuai kewajiban yang berlaku.",
          ["Rekonsiliasi pelaporan pajak dengan pembukuan", "Tetapkan tax calendar dan maker-checker", "Dokumentasikan audit/review eksternal apabila diwajibkan atau dibutuhkan"],
          options=O(("yes","Ya, rutin & tepat waktu"),("partial","Ada keterlambatan/temuan tertentu"),("no","Tidak ada kontrol memadai / sering terlambat"))),
        R("related_party", "Finansial & Perpajakan", "Apakah transaksi material dengan pihak terafiliasi telah melalui persetujuan organ dan pengungkapan konflik kepentingan yang diperlukan?",
          "Transaksi pihak terafiliasi tanpa approval atau pengungkapan yang memadai dapat dipersoalkan sebagai konflik kepentingan atau tindakan melampaui kewenangan.",
          "UU Perseroan Terbatas, anggaran dasar, kebijakan konflik kepentingan, serta regulasi sektoral bila berlaku.",
          "Dapat menimbulkan keberatan/pembatalan tindakan korporasi, tanggung jawab pengurus, sengketa pemegang saham, dan sanksi sektoral bila relevan.",
          ["Inventarisasi transaksi afiliasi", "Verifikasi threshold dan reserved matters", "Dokumentasikan disclosure konflik kepentingan dan approval"] ,
          options=O(("yes","Tidak ada atau seluruhnya sudah disetujui"),("partial","Ada, approval/dokumentasi belum lengkap"),("no","Ada transaksi material tanpa approval yang diperlukan"))),
        R("asset_ip", "Aset & Kekayaan Intelektual", "Apakah aset material dan kekayaan intelektual utama yang digunakan perusahaan terdaftar/dikuasai atas nama pihak yang tepat dan terdokumentasi?",
          "Aset atau IP yang masih atas nama pribadi/entitas lain dapat mengganggu pembuktian kepemilikan, pembiayaan, lisensi, atau enforcement.",
          "Peraturan pertanahan, kekayaan intelektual, kontrak pengalihan/lisensi, dan administrasi korporasi yang relevan.",
          "Eksposur utama berupa sengketa kepemilikan/penguasaan, kehilangan nilai aset, hambatan transaksi, dan ganti rugi bila hak pihak lain dilanggar.",
          ["Buat asset & IP register", "Verifikasi bukti kepemilikan/pengalihan/lisensi", "Prioritaskan registrasi atau assignment aset/IP material"] ,
          options=O(("yes","Ya, seluruh aset material terdokumentasi"),("partial","Sebagian masih atas nama pribadi/pihak lain"),("no","Belum ada inventaris/registrasi yang memadai"))),
        R("confidentiality", "Aset & Kekayaan Intelektual", "Apakah NDA/kerahasiaan dan pengamanan informasi rahasia mengikat karyawan serta vendor yang mengakses informasi sensitif?",
          "Rahasia dagang, data, know-how, atau informasi klien dapat bocor tanpa dasar kontraktual dan kontrol akses yang memadai.",
          "Ketentuan kontrak, rahasia dagang, pelindungan data, dan kebijakan keamanan informasi yang relevan.",
          "Dapat menimbulkan sengketa kontrak, kehilangan rahasia dagang, ganti rugi, serta sanksi data/sectoral bila informasi yang bocor termasuk data yang dilindungi.",
          ["Gunakan NDA/clauses yang proporsional", "Petakan akses informasi sensitif", "Atur return/deletion, survival, dan remediasi kebocoran"] ,
          options=O(("yes","Ya, mengikat & diterapkan"),("partial","Hanya posisi/vendor tertentu"),("no","Tidak ada kesepakatan/kontrol tertulis"))),
        R("beneficial_owner", "Legalitas & Tata Kelola", "Apakah Pemilik Manfaat (Beneficial Owner) korporasi sudah diidentifikasi, diverifikasi, dan datanya dijaga tetap mutakhir?",
          "Informasi Pemilik Manfaat yang tidak akurat atau tidak terverifikasi meningkatkan risiko transparansi korporasi dan APU/PPT.",
          "Perpres No. 13 Tahun 2018 dan ketentuan verifikasi/pengawasan Pemilik Manfaat yang berlaku.",
          "Dapat memicu temuan kepatuhan/administratif dan meningkatkan exposure saat onboarding bank, transaksi korporasi, atau pemeriksaan otoritas.",
          ["Identifikasi ultimate beneficial owner", "Verifikasi dokumen dan kontrol/kepemilikan", "Pastikan data BO pada sistem/administrasi berwenang tetap mutakhir"]),
        R("litigation_exposure", "Sengketa & Kontinjensi", "Apakah perusahaan mempunyai register sengketa, somasi, klaim, atau potensi perkara material dalam 12 bulan terakhir beserta owner dan strategi penanganannya?",
          "Sengketa yang tidak dicatat dan dimitigasi dapat menimbulkan kewajiban kontinjensi, kehilangan tenggat, atau strategi litigasi yang terlambat.",
          "Hukum acara, kontrak, ketenagakerjaan, perpajakan, dan regulasi sektoral sesuai jenis sengketa.",
          "Konsekuensi dapat berupa putusan ganti rugi, kewajiban pembayaran, sita/eksekusi, biaya sengketa, atau sanksi sektoral sesuai perkara.",
          ["Buat litigation & claims register", "Catat deadline, forum, nilai eksposur dan counsel/PIC", "Tetapkan legal hold dan preservasi bukti"] ,
          options=O(("yes","Tidak ada sengketa material / seluruhnya termonitor"),("partial","Ada potensi sengketa dan mitigasi belum lengkap"),("no","Ada perkara berjalan tanpa governance/strategy memadai"))),
    ],

    "Tech/PDP": [
        R("privacy", "Data Governance", "Apakah dasar pemrosesan, privacy notice, data inventory/ROPA, tujuan pemrosesan dan retensi data terdokumentasi?",
          "Pemrosesan data pribadi tanpa dasar, transparansi, tujuan, atau retensi yang memadai.",
          "UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi dan regulasi pelaksana yang berlaku.",
          "Dapat berujung sanksi administratif termasuk peringatan, penghentian pemrosesan, penghapusan/pemusnahan data dan denda administratif; perbuatan tertentu juga dapat memicu pidana.",
          ["Buat data inventory/ROPA", "Dokumentasikan dasar pemrosesan per tujuan", "Perbarui privacy notice dan jadwal retensi/pemusnahan"], severity="HIGH"),
        R("dpo", "Data Governance", "Jika memenuhi kriteria yang mewajibkan fungsi/pejabat Pelindungan Data Pribadi, apakah perusahaan sudah menunjuk dan memberi kewenangan yang memadai?",
          "Ketiadaan fungsi PDP ketika diwajibkan dapat melemahkan tata kelola, independensi pengawasan, dan respons kepatuhan.",
          "UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi dan ketentuan pelaksana yang berlaku.",
          "Dapat meningkatkan exposure administratif ketika kewajiban tata kelola tidak dipenuhi.",
          ["Uji apakah kriteria penunjukan fungsi PDP terpenuhi", "Tetapkan mandat, independensi, jalur eskalasi dan sumber daya", "Dokumentasikan penunjukan dan conflict management"],
          options=O(("yes","Ya, fungsi/pejabat sudah efektif"),("partial","Peran dirangkap / mandat belum memadai"),("no","Wajib tetapi belum ditunjuk"),("na","Tidak memenuhi kriteria / belum relevan"))),
        R("dpia_transfer", "Data Governance", "Untuk pemrosesan berisiko tinggi atau transfer data lintas batas/pihak ketiga, apakah DPIA/transfer assessment dan safeguard dilakukan bila dipersyaratkan?",
          "Pemrosesan berisiko tinggi atau transfer data dapat berjalan tanpa asesmen dampak, dasar, dan safeguard yang memadai.",
          "UU Pelindungan Data Pribadi dan ketentuan mengenai asesmen dampak serta transfer data yang berlaku.",
          "Dapat menimbulkan perintah remediasi, pembatasan pemrosesan/transfer, denda administratif, atau tanggung jawab lain sesuai pelanggaran.",
          ["Tentukan trigger DPIA/transfer assessment", "Dokumentasikan risiko dan mitigasi", "Verifikasi klausul/safeguard lintas batas dan third-party transfer"] ,
          options=O(("yes","Ya, dilakukan bila trigger terpenuhi"),("partial","Hanya sebagian proyek/transfer"),("no","Belum ada mekanisme assessment"),("na","Tidak ada pemrosesan/transfer yang memicu"))),
        R("data_subject_rights", "Hak Subjek Data", "Apakah tersedia mekanisme terukur untuk akses, koreksi, penarikan persetujuan, penghapusan, dan hak subjek data lain yang relevan?",
          "Permintaan subjek data dapat terlambat, tidak tercatat, atau tidak dapat dieksekusi secara konsisten.",
          "UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi.",
          "Dapat memicu pengaduan, remediasi, ganti rugi, dan sanksi administratif sesuai pelanggaran.",
          ["Buat data subject request workflow", "Tetapkan SLA, verifikasi identitas dan exception handling", "Simpan audit trail penyelesaian permintaan"] ,
          options=O(("yes","Ya, workflow tersedia & terukur"),("partial","Masih manual / SLA belum jelas"),("no","Belum tersedia mekanisme"))),
        R("consent_notice", "Hak Subjek Data", "Apakah privacy notice/consent ditampilkan secara jelas pada titik pengumpulan dan tidak bergantung pada dark pattern atau persetujuan terselubung?",
          "Persetujuan/transparansi dapat dipersoalkan bila notice tidak jelas, tidak granular, atau tidak tercatat.",
          "UU Pelindungan Data Pribadi dan prinsip transparansi/akuntabilitas pemrosesan.",
          "Dapat memicu penghentian/pembatasan pemrosesan, remediasi consent, pengaduan dan sanksi administratif.",
          ["Review seluruh collection point", "Pisahkan consent yang memang memerlukan persetujuan", "Simpan consent record/versioning"] ,
          options=O(("yes","Opt-in/notice jelas & tercatat"),("partial","Hanya tautan statis / pencatatan terbatas"),("no","Tidak ditampilkan / tidak tercatat"))),
        R("security", "Keamanan & Insiden", "Apakah kontrol keamanan, akses, logging, backup dan respons insiden diterapkan serta diuji?",
          "Kegagalan menjaga kerahasiaan/integritas data dan ketidakmampuan merespons insiden kebocoran.",
          "UU Pelindungan Data Pribadi dan kewajiban keamanan sistem elektronik yang relevan.",
          "Paparan sanksi administratif, kewajiban remediasi/notifikasi, ganti rugi, serta konsekuensi sektoral bila sistem elektronik diatur khusus.",
          ["Terapkan least privilege dan MFA", "Uji backup/restore dan incident response plan", "Tetapkan alur asesmen dan notifikasi insiden"], severity="HIGH"),
        R("incident_drill", "Keamanan & Insiden", "Apakah Data Breach Incident Response Plan tersedia, memiliki PIC, jalur eskalasi, dan pernah diuji/simulasikan?",
          "Rencana respons yang belum diuji meningkatkan risiko keterlambatan containment, assessment, notification dan preservasi bukti.",
          "UU Pelindungan Data Pribadi dan kewajiban keamanan/notifikasi insiden yang berlaku.",
          "Dapat meningkatkan exposure administratif, ganti rugi, reputasi, dan konsekuensi sektoral bila respons insiden tidak memenuhi kewajiban.",
          ["Tetapkan incident commander dan contact tree", "Lakukan tabletop exercise berkala", "Siapkan template notification, evidence log dan post-incident review"] ,
          options=O(("yes","Lengkap & diuji berkala"),("partial","Dokumen ada tetapi belum diuji"),("no","Belum ada prosedur resmi"))),
        R("processor", "Third-Party & Processor", "Apakah kontrak vendor/prosesor data mengatur instruksi, keamanan, subprosesor, breach notice, audit rights dan penghapusan data?",
          "Asimetri tanggung jawab dengan vendor/prosesor dan hilangnya kontrol atas data pribadi yang diproses pihak ketiga.",
          "UU Pelindungan Data Pribadi dan prinsip akuntabilitas pengendali/prosesor.",
          "Eksposur administratif/perdata dapat tetap melekat pada pengendali meski pemrosesan dialihdayakan.",
          ["Gunakan data processing agreement", "Audit vendor dan subprosesor", "Atur breach notice, return/deletion dan audit rights"]),
        R("privacy_training", "Third-Party & Processor", "Apakah karyawan yang mengelola data sensitif mendapat pelatihan berkala tentang keamanan dan pelindungan data?",
          "Human error, phishing, salah kirim, atau pemrosesan tidak sah meningkat ketika awareness tidak dipelihara.",
          "Kewajiban akuntabilitas, keamanan pemrosesan, dan kebijakan internal yang relevan.",
          "Dapat memperbesar exposure administratif/perdata dan memperburuk posisi perusahaan saat insiden karena kontrol organisasi tidak memadai.",
          ["Tetapkan annual role-based training", "Uji phishing/security awareness bila relevan", "Simpan attendance, materi, dan hasil evaluasi"] ,
          options=O(("yes","Berkala & terdokumentasi"),("partial","Hanya onboarding / tidak rutin"),("no","Belum pernah ada pelatihan formal"))),
    ],

    "Employment": [
        R("employment_docs", "Status Kerja & Tata Kelola", "Apakah perjanjian kerja, Peraturan Perusahaan/PKB dan dokumen status pekerja lengkap, sah, dan masih berlaku?",
          "Status hubungan kerja, hak/kewajiban dan dasar tindakan disiplin/PHK berpotensi diperselisihkan.",
          "UU Ketenagakerjaan sebagaimana diubah dan peraturan pelaksana termasuk PP No. 35 Tahun 2021 sepanjang relevan.",
          "Dapat menimbulkan kewajiban pembayaran hak pekerja, perselisihan hubungan industrial, dan sanksi administratif untuk pelanggaran tertentu.",
          ["Audit PKWT/PKWTT dan job description", "Pastikan PP/PKB berlaku dan disosialisasikan", "Lengkapi bukti penerimaan dokumen oleh pekerja"]),
        R("pkwt_registration", "Status Kerja & Tata Kelola", "Apakah PKWT dicatatkan/didaftarkan sesuai mekanisme dan tenggat yang berlaku serta kompensasinya dikelola?",
          "Administrasi PKWT yang tidak sesuai dapat meningkatkan sengketa status hubungan kerja dan hak kompensasi.",
          "PP No. 35 Tahun 2021 dan ketentuan ketenagakerjaan terkait PKWT yang berlaku.",
          "Dapat memicu kewajiban pembayaran hak/kompensasi, perselisihan status, dan sanksi administratif sesuai pelanggaran.",
          ["Audit seluruh PKWT aktif", "Periksa pencatatan dan tanggal mulai/akhir", "Rekonsiliasi kompensasi PKWT dan bukti pembayaran"] ,
          options=O(("yes","Ya, seluruh PKWT tertib"),("partial","Sebagian belum lengkap/terlambat"),("no","Tidak ada proses pencatatan yang memadai"),("na","Tidak menggunakan PKWT"))),
        R("tka", "Status Kerja & Tata Kelola", "Jika menggunakan Tenaga Kerja Asing, apakah persetujuan/rencana penggunaan dan dokumen keimigrasian yang diperlukan masih aktif?",
          "Penggunaan TKA tanpa dokumen yang tepat dapat menimbulkan exposure ketenagakerjaan dan keimigrasian.",
          "Ketentuan penggunaan Tenaga Kerja Asing dan keimigrasian yang berlaku.",
          "Dapat memicu sanksi administratif, penghentian/pembatasan penggunaan TKA, denda atau tindakan keimigrasian sesuai pelanggaran.",
          ["Buat register TKA dan masa berlaku dokumen", "Verifikasi jabatan/lokasi/masa kerja dengan approval yang dimiliki", "Pasang reminder perpanjangan"] ,
          options=O(("yes","Ya, seluruh dokumen aktif"),("partial","Ada yang dalam proses perpanjangan"),("no","Menggunakan TKA tanpa dokumen memadai"),("na","Tidak menggunakan TKA"))),
        R("wage", "Upah & Hak Normatif", "Apakah upah, lembur, THR, BPJS dan hak normatif dibayar serta didokumentasikan sesuai ketentuan yang berlaku?",
          "Kekurangan pembayaran hak normatif pekerja dan kegagalan kepesertaan/jaminan sosial.",
          "Peraturan ketenagakerjaan, pengupahan, THR dan jaminan sosial yang berlaku.",
          "Dapat memicu kewajiban pembayaran kekurangan, denda/sanksi administratif, perselisihan industrial dan pada pelanggaran tertentu konsekuensi pidana menurut unsur pasal yang berlaku.",
          ["Rekonsiliasi payroll dengan absensi/lembur", "Audit THR dan kepesertaan BPJS", "Simpan bukti pembayaran dan persetujuan lembur"], severity="HIGH"),
        R("discipline", "Disiplin & PHK", "Apakah Surat Peringatan/sanksi disiplin, investigasi pelanggaran, dan bukti pendukung diatur serta terdokumentasi secara konsisten?",
          "Tindakan disiplin yang tidak konsisten atau tanpa bukti dapat melemahkan dasar tindakan lanjutan dan memicu sengketa.",
          "PP/PKB/perjanjian kerja dan ketentuan hubungan industrial yang berlaku.",
          "Eksposur terutama berupa perselisihan PHI, pembatalan/ketidakefektifan tindakan disiplin, dan kewajiban pembayaran hak.",
          ["Tetapkan SOP investigasi dan disciplinary matrix", "Jaga konsistensi perlakuan antar kasus", "Simpan bukti pelanggaran, klarifikasi, dan pemberitahuan"] ,
          options=O(("yes","Ya, SOP & bukti kuat"),("partial","Aturan ada tetapi administrasi bukti belum konsisten"),("no","Tidak ada SOP tertulis"))),
        R("termination", "Disiplin & PHK", "Apakah prosedur PHK memiliki dasar, bukti, pemberitahuan, proses penyelesaian, dan perhitungan hak yang terdokumentasi?",
          "PHK dapat dipersoalkan karena dasar/prosedur tidak memadai atau hak terminasi tidak dipenuhi.",
          "UU Ketenagakerjaan sebagaimana diubah, PP No. 35 Tahun 2021, dan mekanisme PPHI.",
          "Eksposur berupa perselisihan PHI, kewajiban pembayaran hak, pemulihan hubungan kerja pada keadaan tertentu, dan biaya sengketa.",
          ["Dokumentasikan pelanggaran/kinerja dan tahapan pembinaan", "Hitung hak terminasi dengan dasar yang berlaku", "Siapkan bipartit dan bukti penyampaian pemberitahuan"], severity="HIGH"),
        R("termination_reserve", "Disiplin & PHK", "Apakah perusahaan memiliki perencanaan/cadangan likuiditas untuk memenuhi kewajiban kompensasi PHK/pensiun ketika timbul?",
          "Kewajiban terminasi yang tidak direncanakan dapat menimbulkan tekanan arus kas dan sengketa pembayaran hak pekerja.",
          "Ketentuan hak terminasi/pensiun dan kebijakan akuntansi/keuangan yang relevan.",
          "Eksposur berupa tunggakan hak, sengketa PHI, denda/konsekuensi administratif tertentu, dan gangguan likuiditas.",
          ["Buat termination liability forecast", "Rekonsiliasi dengan HR/payroll/finance", "Tetapkan approval dan sumber dana untuk pembayaran tepat waktu"] ,
          options=O(("yes","Ya, diperhitungkan & tersedia"),("partial","Mengandalkan arus kas berjalan"),("no","Tidak ada perencanaan/cadangan"))),
        R("outsourcing", "Alih Daya & Vendor", "Jika menggunakan outsourcing/alih daya, apakah legalitas dan kepatuhan vendor terhadap upah, BPJS, kontrak dan kewajiban pekerja diaudit berkala?",
          "Kegagalan vendor dapat menimbulkan sengketa operasional, reputasi, dan exposure kontraktual/regulator pada perusahaan pengguna sesuai hubungan dan kewajiban yang berlaku.",
          "PP No. 35 Tahun 2021, kontrak alih daya, dan ketentuan ketenagakerjaan/jaminan sosial yang relevan.",
          "Dapat memicu sengketa hubungan industrial, terminasi vendor, klaim indemnity, dan sanksi sesuai pelanggaran underlying.",
          ["Audit legalitas dan kepatuhan vendor", "Minta bukti payroll/BPJS secara berkala", "Atur audit rights, indemnity, dan replacement plan"] ,
          options=O(("yes","Ya, diaudit berkala"),("partial","Hanya due diligence awal"),("no","Tidak pernah diaudit"),("na","Tidak menggunakan outsourcing"))),
        R("k3", "K3 & Workplace Conduct", "Apakah sistem K3, pelaporan kecelakaan, pelatihan keselamatan, serta mekanisme pengaduan kekerasan/pelecehan di tempat kerja tersedia dan berjalan?",
          "Kelemahan K3 dan workplace conduct dapat menimbulkan kecelakaan, klaim pekerja, gangguan operasional, serta kegagalan duty of care.",
          "UU No. 1 Tahun 1970 tentang Keselamatan Kerja dan ketentuan ketenagakerjaan/K3 lain yang berlaku.",
          "Dapat memicu sanksi K3/ketenagakerjaan sesuai pelanggaran, ganti rugi, penghentian kegiatan tertentu, serta risiko pidana bila unsur delik lain terpenuhi.",
          ["Lakukan hazard/risk assessment", "Dokumentasikan pelatihan, APD, inspeksi dan incident log", "Sediakan kanal pengaduan dan anti-retaliation"]),
    ],

    "Commercial": [
        R("contracts", "Contract Architecture", "Apakah kontrak material memuat objek, kewajiban, pembayaran, wanprestasi, cure period, terminasi dan sengketa secara jelas?",
          "Klausul tidak lengkap/ambigu dapat membuka wanprestasi, dispute interpretasi dan liability yang tidak teralokasi.",
          "KUHPerdata/Burgerlijk Wetboek sepanjang masih berlaku dan regulasi sektoral yang menyimpang atau melengkapinya.",
          "Eksposur utama berupa pemenuhan prestasi, pembatalan, ganti rugi, biaya sengketa dan konsekuensi sektoral bila objek kontrak diatur khusus.",
          ["Review kontrak material dengan clause checklist", "Tetapkan notice/cure/termination yang operasional", "Pastikan dispute resolution dan enforcement path jelas"]),
        R("liability_indemnity", "Contract Architecture", "Apakah kontrak utama memiliki limitation of liability dan indemnity yang proporsional, jelas, dan selaras dengan risiko transaksi?",
          "Liability yang tidak dibatasi atau indemnity sepihak dapat memunculkan eksposur kerugian yang tidak proporsional.",
          "Hukum perjanjian, prinsip kebebasan berkontrak, dan regulasi sektoral yang membatasi klausul tertentu.",
          "Eksposur utama berupa ganti rugi yang besar/tidak terukur dan sengketa interpretasi klausul.",
          ["Tetapkan liability cap dan carve-out yang rasional", "Bedakan direct/indirect loss bila relevan", "Selaraskan indemnity dengan insurance dan control rights"] ,
          options=O(("yes","Ya, seimbang & terukur"),("partial","Hanya kontrak tertentu / redaksi belum konsisten"),("no","Tidak diatur / sepihak"))),
        R("warranty_sla", "Contract Architecture", "Apakah warranty/SLA, service credits atau kompensasi kegagalan layanan diatur dengan parameter objektif dan batas tanggung jawab yang jelas?",
          "Jaminan/SLA yang kabur dapat menciptakan ekspektasi kinerja dan ganti rugi yang sulit dikendalikan.",
          "Hukum perjanjian, perlindungan konsumen bila relevan, dan regulasi sektoral.",
          "Dapat memicu klaim wanprestasi, refund/service credit, ganti rugi atau sanksi sektoral bila standar layanan diwajibkan.",
          ["Definisikan KPI/SLA dan measurement source", "Atur cure/escalation serta exclusive remedy bila sah", "Selaraskan warranty dengan capability operasional"] ,
          options=O(("yes","Ya, SLA & remedy terukur"),("partial","Ada tetapi parameter/remedy ambigu"),("no","Tidak ada pengaturan tertulis"),("na","Tidak relevan untuk model transaksi"))),
        R("consumer", "Consumer & Market Conduct", "Apakah informasi produk/jasa, harga, syarat, garansi dan penanganan keluhan konsumen transparan dan diaudit?",
          "Informasi atau klausul baku dapat merugikan konsumen atau membatasi hak konsumen secara tidak sah.",
          "UU Perlindungan Konsumen dan regulasi sektoral terkait produk/jasa.",
          "Dapat menimbulkan ganti rugi, sanksi administratif, penarikan/larangan tertentu dan pidana untuk pelanggaran yang memenuhi unsur undang-undang.",
          ["Audit terms & conditions dan klausul baku", "Pastikan price/fee disclosure transparan", "Bangun SOP complaint, refund dan product recall bila relevan"], severity="HIGH"),
        R("standard_clause", "Consumer & Market Conduct", "Apakah klausul baku/Terms & Conditions telah ditinjau untuk menghindari pengalihan tanggung jawab sepihak atau ketentuan yang dilarang?",
          "Klausul baku yang tidak seimbang atau dilarang dapat tidak efektif dan memicu klaim konsumen.",
          "UU Perlindungan Konsumen dan regulasi sektoral terkait klausul baku.",
          "Dapat menimbulkan ketidakberlakuan klausul tertentu, ganti rugi, sanksi administratif, atau konsekuensi lain sesuai pelanggaran.",
          ["Lakukan standard terms audit", "Hapus klausul eksonerasi yang bermasalah", "Gunakan approval legal untuk perubahan T&C"] ,
          options=O(("yes","Sudah direview legal"),("partial","Masih menggunakan template umum"),("no","Belum pernah diaudit"))),
        R("competition", "Consumer & Market Conduct", "Apakah strategi harga, diskon eksklusif, bundling, distribusi atau posisi dominan telah diuji dari perspektif persaingan usaha?",
          "Praktik komersial tertentu dapat memicu dugaan perjanjian/praktik anti-persaingan atau penyalahgunaan posisi dominan.",
          "UU Persaingan Usaha dan regulasi/pedoman KPPU yang relevan.",
          "Dapat memicu pemeriksaan KPPU, denda administratif, perintah perubahan perilaku/perjanjian, serta kerugian reputasi/komersial.",
          ["Lakukan competition-law screening untuk pricing/distribution", "Dokumentasikan objective justification", "Review exclusivity, MFN, bundling dan market-share sensitivity"] ,
          options=O(("yes","Sudah diuji dan tidak ada red flag material"),("partial","Ada potensi risiko / belum ada legal review lengkap"),("no","Belum pernah dinilai"))),
        R("credit_enforcement", "Credit & Enforcement", "Apakah kontrak mengatur jatuh tempo, late payment, default, suspension/termination, jaminan, dan langkah penagihan secara operasional?",
          "Hak tagih dapat melemah jika trigger default, bukti pembayaran, notice atau remedy tidak jelas.",
          "Hukum perjanjian, jaminan, kepailitan/PKPU bila relevan, dan regulasi sektoral.",
          "Eksposur berupa piutang macet, biaya penagihan, sengketa wanprestasi, restrukturisasi atau insolvency exposure.",
          ["Tetapkan aging dan collection workflow", "Pastikan default/notice/cure terdefinisi", "Evaluasi jaminan, set-off, suspension dan enforcement options"] ,
          options=O(("yes","Diatur detail & dijalankan"),("partial","Ada tetapi tidak lengkap/konsisten"),("no","Tidak ada mekanisme memadai"))),
        R("dispute_forum", "Credit & Enforcement", "Apakah pilihan hukum, forum/yurisdiksi/arbitrase, domisili, notice dan enforcement route ditentukan secara jelas?",
          "Forum yang ambigu dapat memicu sengketa kompetensi, biaya tambahan, dan kesulitan enforcement.",
          "Hukum acara/perjanjian, arbitrase bila dipilih, dan aturan yurisdiksi yang relevan.",
          "Eksposur berupa dismissal/objection prosedural, proses paralel, biaya sengketa dan keterlambatan enforcement.",
          ["Tentukan governing law & forum", "Uji enforceability klausul arbitrase/jurisdiksi", "Samakan notice address, language dan service mechanism"] ,
          options=O(("yes","Forum & enforcement route jelas"),("partial","Mengikuti aturan umum / redaksi ambigu"),("no","Belum diatur"))),
        R("third_party", "Third-Party Risk", "Apakah due diligence mitra, distributor, agen dan vendor dilakukan sebelum kontrak dan diperbarui secara berkala?",
          "Risiko hukum mitra dapat berpindah menjadi liability kontraktual, reputasi, fraud atau pelanggaran kepatuhan perusahaan.",
          "Kewajiban kontraktual, prinsip kehati-hatian dan regulasi sektoral yang relevan.",
          "Konsekuensi bergantung pelanggaran underlying: ganti rugi, terminasi kontrak, sanksi administratif atau pidana bila unsur pelanggaran terpenuhi.",
          ["Lakukan KYB dan beneficial ownership check", "Gunakan compliance representations/warranties", "Sediakan audit, suspension dan termination rights"]),
    ],

    "Financial/AML": [
        R("aml_scope", "Scope & Governance", "Apakah sudah dipastikan apakah entitas termasuk Pihak Pelapor/PJK atau tunduk pada kewajiban APU/PPT/PPPSPM sektoral tertentu?",
          "Salah menentukan scope kewajiban dapat membuat program AML terlalu lemah atau salah sasaran.",
          "UU No. 8 Tahun 2010, regulasi PPATK, OJK/BI dan regulator sektoral sesuai jenis entitas.",
          "Jika ternyata termasuk pihak wajib, kegagalan menerapkan program dapat memicu sanksi administratif sektoral dan exposure lain sesuai pelanggaran.",
          ["Buat regulatory applicability memo", "Petakan regulator dan jenis kewajiban pelaporan", "Tetapkan owner fungsi APU/PPT"] ,
          options=O(("yes","Scope sudah dipetakan & terdokumentasi"),("partial","Ada asumsi tetapi belum ada assessment formal"),("no","Belum pernah dipetakan"))),
        R("aml", "CDD / Customer Risk", "Jika entitas termasuk pihak wajib, apakah program APU/PPT, KYC/CDD, identifikasi Beneficial Owner dan pemantauan transaksi diterapkan berbasis risiko?",
          "Kegagalan mengenali nasabah/beneficial owner, memantau transaksi, atau memenuhi kewajiban APU/PPT.",
          "UU No. 8 Tahun 2010 tentang Pencegahan dan Pemberantasan TPPU serta regulasi PPATK/OJK/otoritas sektor yang relevan.",
          "Dapat menimbulkan sanksi administratif sektoral termasuk denda/pembatasan/pembekuan sampai pencabutan izin; keterlibatan dalam TPPU dapat memicu pertanggungjawaban pidana.",
          ["Tetapkan risk-based CDD/KYC", "Verifikasi beneficial owner dan source of funds/source of wealth sesuai risk", "Bangun transaction monitoring dan escalation workflow"], severity="HIGH"),
        R("pep_edd", "CDD / Customer Risk", "Apakah sistem mampu mengidentifikasi PEP/keluarga/close associate dan menerapkan EDD untuk customer berisiko tinggi?",
          "PEP/high-risk customer dapat diperlakukan sama seperti risiko biasa sehingga sumber dana/kekayaan dan approval tidak diuji memadai.",
          "Ketentuan APU/PPT regulator sektoral, termasuk kewajiban risk-based CDD/EDD yang berlaku.",
          "Dapat memicu temuan pengawasan, remedial order, denda/pembatasan kegiatan usaha, dan exposure lain sesuai sektor.",
          ["Gunakan PEP screening yang dapat diaudit", "Tetapkan senior management approval", "Dokumentasikan source of funds/source of wealth dan enhanced monitoring"] ,
          options=O(("yes","PEP teridentifikasi & EDD diterapkan"),("partial","Hanya self-declaration / EDD belum konsisten"),("no","Tidak ada klasifikasi PEP/high-risk"))),
        R("sanctions_lists", "Sanctions / TPPT / Proliferation", "Apakah DTTOT dan daftar pendanaan proliferasi/daftar pembatasan yang relevan diperbarui dan digunakan dalam screening?",
          "Nasabah/mitra yang terkait daftar pembatasan dapat lolos onboarding atau transaksi tanpa eskalasi.",
          "Ketentuan APU/PPT/PPPSPM PPATK/OJK/otoritas sektor yang berlaku.",
          "Dapat memicu kewajiban pemblokiran/pelaporan, sanksi administratif, pembatasan kegiatan, dan exposure pidana bila unsur tindak pidana terpenuhi.",
          ["Automasi/periodikkan list update", "Screen onboarding dan ongoing customer", "Simpan match disposition dan evidence"] ,
          options=O(("yes","Otomatis/terjadwal & auditable"),("partial","Manual berkala"),("no","Belum ada screening list")), severity="HIGH"),
        R("sanctions_match", "Sanctions / TPPT / Proliferation", "Apakah tersedia SOP untuk true/false match, penghentian/pemblokiran yang diwajibkan, eskalasi, dan pelaporan kepada otoritas?",
          "Match berisiko tinggi dapat ditangani terlambat atau tidak konsisten.",
          "Ketentuan APU/PPT/PPPSPM dan instruksi regulator/otoritas yang berlaku.",
          "Dapat memicu sanksi administratif, tindakan pengawasan, dan exposure lain bila kewajiban pemblokiran/pelaporan tidak dipenuhi.",
          ["Buat sanctions match playbook", "Tetapkan maker-checker/legal escalation", "Simpan audit trail keputusan dan pelaporan"] ,
          options=O(("yes","SOP lengkap & diuji"),("partial","Ada eskalasi ad hoc"),("no","Belum ada SOP khusus")), severity="HIGH"),
        R("reporting", "Monitoring & Reporting", "Apakah trigger dan pelaporan transaksi/aktivitas wajib kepada PPATK/regulator dipetakan, diuji, dan dilakukan tepat waktu?",
          "Keterlambatan atau kegagalan pelaporan wajib kepada otoritas.",
          "UU TPPU dan ketentuan pelaporan regulator/PPATK sesuai jenis pihak pelapor.",
          "Dapat memicu sanksi administratif, denda dan tindakan pengawasan; konsekuensi spesifik bergantung status pihak pelapor dan jenis kewajiban.",
          ["Petakan jenis laporan dan trigger", "Tetapkan maker-checker dan kalender regulator", "Simpan audit trail pengiriman dan koreksi laporan"], severity="HIGH"),
        R("transaction_monitoring", "Monitoring & Reporting", "Apakah transaction monitoring menggunakan skenario/threshold berbasis risiko, alert investigation, escalation dan tuning berkala?",
          "Transaksi mencurigakan dapat tidak terdeteksi atau alert tidak ditindaklanjuti secara konsisten.",
          "Program APU/PPT berbasis risiko dan ketentuan pemantauan transaksi yang berlaku sesuai sektor.",
          "Dapat memicu temuan regulator, remedial order, denda/pembatasan dan kegagalan pelaporan transaksi mencurigakan.",
          ["Dokumentasikan scenario library dan threshold", "Ukur alert aging/disposition", "Lakukan tuning dan QA berkala"] , severity="HIGH"),
        R("aml_audit", "Internal Control & Training", "Apakah fungsi kepatuhan dan/atau audit independen menilai efektivitas program APU/PPT secara berkala?",
          "Kelemahan desain dan implementasi program dapat berulang tanpa independent challenge.",
          "Ketentuan tata kelola APU/PPT regulator sektoral yang berlaku.",
          "Dapat memicu temuan pengawasan, remediation plan, denda/pembatasan atau konsekuensi lain sesuai sektor.",
          ["Tetapkan annual AML audit plan", "Track issue-to-closure", "Laporkan material findings ke Direksi/Komisaris sesuai governance"] ,
          options=O(("yes","Audit berkala & independen"),("partial","Hanya review saat ada masalah"),("no","Belum pernah audit khusus"))),
        R("aml_training", "Internal Control & Training", "Apakah staf frontliner, keuangan, compliance dan manajemen mendapat pelatihan APU/PPT berbasis peran secara berkala?",
          "Karyawan dapat gagal mengenali red flags, eskalasi, atau kewajiban pelaporan.",
          "Ketentuan program APU/PPT terkait SDM dan pelatihan yang berlaku sesuai sektor.",
          "Dapat memperburuk temuan regulator dan menunjukkan lemahnya control environment.",
          ["Tetapkan annual role-based AML training", "Gunakan case study/red flag sesuai unit", "Dokumentasikan attendance dan assessment"] ,
          options=O(("yes","Berkala minimal tahunan/berbasis risiko"),("partial","Hanya onboarding / tidak konsisten"),("no","Belum ada pelatihan formal"))),
        R("financial_controls", "Internal Control & Training", "Apakah rekonsiliasi, segregasi tugas, approval limit dan audit trail transaksi berjalan efektif?",
          "Fraud, misappropriation, transaksi tidak sah atau laporan yang tidak dapat direkonsiliasi.",
          "Ketentuan tata kelola/kehati-hatian sektor keuangan dan kewajiban pembukuan yang relevan.",
          "Dapat memicu remedial order, sanksi administratif, pembatasan kegiatan usaha dan liability personal; pidana bergantung perbuatan dan unsur delik.",
          ["Pisahkan maker-checker-approver", "Rekonsiliasi harian/periodik dan exception report", "Audit privileged access dan transaksi manual"]),
    ],
}


def normalize_category(category: str) -> str:
    raw = (category or "General Corporate").strip()
    return CATEGORY_ALIASES.get(raw.lower(), raw if raw in RULES else "General Corporate")


def question_set(category: str) -> List[Dict]:
    cat = normalize_category(category)
    return [
        {
            "key": r["key"],
            "group": r.get("group", "Assessment"),
            "question": r["question"],
            "options": list(r.get("options") or DEFAULT_OPTIONS),
        }
        for r in RULES[cat]
    ]


def _level_for(value: str, severity: str, sanctions: str) -> str:
    value = (value or "yes").lower()
    if value in {"yes", "na"}:
        return "LOW"
    severe_text = any(k in sanctions.lower() for k in (
        "pidana", "pencabutan izin", "pembekuan sampai pencabutan",
        "penghentian kegiatan", "pemblokiran", "pembatasan kegiatan",
    ))
    severe = severity == "HIGH" or severe_text
    if value == "no":
        return "HIGH" if severe else "MEDIUM"
    return "MEDIUM" if severe else "LOW"


def _normalize_custom_rules(custom_rules) -> List[Dict]:
    """Normalize user-defined controls and their user-defined answer options.

    A custom control may define its own answer choices. Each choice carries a
    risk impact (LOW/MEDIUM/HIGH/NA) chosen by the user. This lets progressive
    controls affect the category Risk Profile without forcing generic
    yes/partial/no semantics onto unrelated questions.
    """
    out = []
    for idx, raw in enumerate((custom_rules or [])[:30]):
        if not isinstance(raw, dict):
            continue
        question = str(raw.get("question") or "").strip()
        if not question:
            continue
        key = str(raw.get("key") or f"custom_{idx+1}").strip()
        key = "".join(c if c.isalnum() or c in "_-" else "_" for c in key)[:80] or f"custom_{idx+1}"
        severity = str(raw.get("severity") or "MEDIUM").upper()
        if severity not in {"LOW", "MEDIUM", "HIGH"}:
            severity = "MEDIUM"
        actions = raw.get("actions") or []
        if isinstance(actions, str):
            actions = [x.strip() for x in actions.split("\n") if x.strip()]

        options = []
        for opt_idx, opt in enumerate((raw.get("options") or [])[:8]):
            if not isinstance(opt, dict):
                continue
            label = str(opt.get("label") or "").strip()
            if not label:
                continue
            impact = str(opt.get("risk_level") or opt.get("impact") or "MEDIUM").upper()
            if impact not in {"LOW", "MEDIUM", "HIGH", "NA"}:
                impact = "MEDIUM"
            value = str(opt.get("value") or f"opt_{opt_idx+1}").strip()
            value = "".join(c if c.isalnum() or c in "_-" else "_" for c in value)[:80] or f"opt_{opt_idx+1}"
            options.append({"value": value, "label": label[:300], "risk_level": impact})

        # Backward compatibility for controls created before flexible answer options.
        if len(options) < 2:
            options = [
                {"value": "yes", "label": "Ya / tersedia", "risk_level": "LOW"},
                {"value": "partial", "label": "Sebagian / perlu perbaikan", "risk_level": "MEDIUM"},
                {"value": "no", "label": "Tidak / belum tersedia", "risk_level": "HIGH"},
                {"value": "na", "label": "N/A — tidak relevan", "risk_level": "NA"},
            ]

        out.append({
            "key": key,
            "group": str(raw.get("group") or "Kontrol Tambahan").strip()[:120],
            "question": question[:700],
            "risk": str(raw.get("risk") or "Potensi ketidakpatuhan pada kontrol tambahan yang ditetapkan pengguna.").strip()[:900],
            "basis": str(raw.get("basis") or "Dasar hukum belum diisi — wajib diverifikasi oleh profesional hukum.").strip()[:900],
            "sanctions": str(raw.get("sanctions") or "Konsekuensi/sanksi belum diisi — wajib diverifikasi sebelum dipakai sebagai kesimpulan hukum.").strip()[:900],
            "actions": [str(x)[:500] for x in actions[:10]] or ["Tetapkan PIC, bukti implementasi, tenggat remediasi, dan verifikasi dasar hukum yang relevan."],
            "severity": severity,
            "options": options,
            "custom": True,
        })
    return out

def build_risk_matrix(category: str, answers: Dict[str, str], custom_rules=None) -> Dict:
    cat = normalize_category(category)
    custom = _normalize_custom_rules(custom_rules)
    rules = list(RULES[cat]) + custom
    matrix = []
    numeric = {"LOW": 15, "MEDIUM": 50, "HIGH": 85}
    applicable_scores = []

    for rule in rules:
        value = str(answers.get(rule["key"], "yes")).lower()
        answer_label = value

        if rule.get("custom"):
            selected = next((o for o in rule.get("options", []) if str(o.get("value", "")).lower() == value), None)
            if selected is None and rule.get("options"):
                selected = rule["options"][0]
                value = str(selected.get("value") or "").lower()
            impact = str((selected or {}).get("risk_level") or "MEDIUM").upper()
            answer_label = str((selected or {}).get("label") or value)
            if impact == "NA":
                level = "LOW"
                control_status = "NA"
                ident = f"Tidak diterapkan pada assessment ini: {rule['question']}"
                justification = (
                    f"LOW / NOT APPLICABLE berdasarkan opsi jawaban pengguna: {answer_label}. "
                    f"Dasar hukum: {rule['basis']} Applicability wajib diverifikasi bila fakta/ruang lingkup berubah."
                )
            else:
                level = impact if impact in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM"
                control_status = level
                ident = rule["risk"] if level != "LOW" else f"Risiko residual terkendali: {rule['risk'].lower()}"
                justification = (
                    f"{level} berdasarkan opsi jawaban pengguna: {answer_label}. "
                    f"Materialitas kontrol: {rule.get('severity','MEDIUM')}. Dasar hukum: {rule['basis']} "
                    f"Konsekuensi yang relevan: {rule['sanctions']}"
                )
                applicable_scores.append(numeric[level])
        else:
            level = _level_for(value, rule.get("severity", "MEDIUM"), rule["sanctions"])
            control_status = value.upper()
            if value == "na":
                ident = f"Tidak diterapkan pada assessment ini: {rule['question']}"
                justification = (
                    f"LOW / NOT APPLICABLE berdasarkan jawaban pengguna. Dasar regulasi tetap dicatat: {rule['basis']} "
                    "Applicability wajib diverifikasi bila fakta/ruang lingkup berubah."
                )
            elif value == "yes":
                ident = f"Kontrol tersedia: risiko residual terkait {rule['risk'].lower()}"
                justification = (
                    f"LOW karena kontrol dinyatakan tersedia. Dasar hukum: {rule['basis']} "
                    "Risiko residual tetap perlu diuji melalui bukti implementasi."
                )
                applicable_scores.append(numeric[level])
            elif value == "partial":
                ident = rule["risk"]
                justification = (
                    f"{level} karena kontrol baru sebagian. Dasar hukum: {rule['basis']} "
                    f"Konsekuensi yang relevan: {rule['sanctions']}"
                )
                applicable_scores.append(numeric[level])
            else:
                ident = rule["risk"]
                justification = (
                    f"{level} karena kontrol dinyatakan tidak tersedia. Dasar hukum: {rule['basis']} "
                    f"Konsekuensi yang relevan: {rule['sanctions']}"
                )
                applicable_scores.append(numeric[level])

        matrix.append({
            "control_key": rule["key"],
            "control_group": rule.get("group", "Assessment"),
            "control_status": control_status,
            "answer_value": value,
            "answer_label": answer_label,
            "risk_identification": ident,
            "risk_level": level,
            "legal_justification": justification,
            "sanction_basis": rule["sanctions"],
            "legal_basis": rule["basis"],
            "mitigation_checklist": list(rule["actions"]),
            "professional_verification": "PENDING",
            "source": "USER_DEFINED" if rule.get("custom") else "SYSTEM",
        })

    score = round(sum(applicable_scores) / max(len(applicable_scores), 1))
    active_rows = [r for r in matrix if r["control_status"] != "NA"]
    overall = (
        "HIGH" if any(r["risk_level"] == "HIGH" for r in active_rows)
        else "MEDIUM" if any(r["risk_level"] == "MEDIUM" for r in active_rows)
        else "LOW"
    )
    return {
        "category": cat,
        "matrix": matrix,
        "score": score,
        "risk_level": overall,
        "question_count": len(rules),
        "system_question_count": len(RULES[cat]),
        "custom_question_count": len(custom),
        "applicable_question_count": len(active_rows),
    }
