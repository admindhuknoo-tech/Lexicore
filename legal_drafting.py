"""LexiCore legal-drafting template registry.

Templates are structural working papers, not a substitute for professional
verification.  They deliberately avoid inventing citations; any legal basis
must be verified through Legal Research/Regulatory Corpus before filing/use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

def _working_note():
    from identity_profile import get_identity_profile
    profile=get_identity_profile()
    return (
        f"\n\nCATATAN LEXICORE | {profile['display_name']}\n"
        "DRAFT KERJA — Professional Verification: PENDING. Verifikasi identitas, kewenangan, fakta, bukti, "
        "kompetensi absolut/relatif, hukum yang berlaku, tenggat, serta konsistensi posita/petitum atau dalil/permohonan sebelum digunakan."
    )

WORKING_NOTE = _working_note()

@dataclass(frozen=True)
class TemplateSpec:
    name: str
    category: str
    p1: str
    p2: str
    prompt: str
    duration: bool = False
    forum_sensitive: bool = False

SPECS: List[TemplateSpec] = [
    TemplateSpec("Perjanjian Kerjasama","Kontrak","Pihak Pertama","Pihak Kedua","Objek, deliverable, pembayaran, risiko dan klausul khusus",True),
    TemplateSpec("Non-Disclosure Agreement","Kontrak","Pihak Pengungkap / Pihak 1","Pihak Penerima / Pihak 2","Tujuan pengungkapan dan jenis informasi rahasia",True),
    TemplateSpec("Perjanjian Kerja","Ketenagakerjaan","Pemberi Kerja","Pekerja","Jabatan, tugas, pola kerja, upah dan ketentuan khusus",True),
    TemplateSpec("Perjanjian Sewa Menyewa","Kontrak","Pemberi Sewa","Penyewa","Objek/alamat dan bukti penguasaan, tujuan penggunaan, harga/deposit, jangka waktu, kondisi awal, utilitas, pemeliharaan, larangan, terminasi, pengembalian dan kondisi khusus",True),
    TemplateSpec("Perjanjian Utang Piutang","Kontrak","Kreditur","Debitur","Jumlah, tujuan, cara pembayaran, jaminan, jatuh tempo dan default",True),
    TemplateSpec("Perjanjian Perdamaian","Penyelesaian Sengketa","Pihak Pertama","Pihak Kedua","Sengketa, konsesi, kewajiban, pelepasan klaim dan pelaksanaan",False),
    TemplateSpec("Surat Kuasa Khusus","Litigasi","Pemberi Kuasa","Penerima Kuasa","Perkara, objek dan tindakan yang dikuasakan",False,True),
    TemplateSpec("Somasi","Pra-Litigasi","Klien / Pemberi Somasi","Pihak yang Disomasi","Kronologi, pelanggaran, tuntutan, bukti dan tenggang",False),
    TemplateSpec("Gugatan Perdata","Litigasi Perdata","Penggugat","Tergugat","Hubungan hukum, kronologi, kerugian, bukti awal dan tujuan gugatan",False,True),
    TemplateSpec("Jawaban Tergugat","Litigasi Perdata","Tergugat","Penggugat","Eksepsi, bantahan posita, jawaban pokok perkara dan petitum jawaban",False,True),
    TemplateSpec("Eksepsi Perdata","Litigasi Perdata","Tergugat","Penggugat","Kompetensi, error in persona, obscuur libel, prematur atau eksepsi lain",False,True),
    TemplateSpec("Replik","Litigasi Perdata","Penggugat","Tergugat","Tanggapan atas jawaban/eksepsi secara isu-per-isu",False,True),
    TemplateSpec("Duplik","Litigasi Perdata","Tergugat","Penggugat","Tanggapan atas replik dan penegasan posisi jawaban",False,True),
    TemplateSpec("Kesimpulan Perdata","Litigasi Perdata","Pihak / Kuasa","Lawan","Ringkasan fakta terbukti, bukti, isu, norma dan permohonan akhir",False,True),
    TemplateSpec("Permohonan Perdata","Litigasi Perdata","Pemohon","Pihak Terkait","Dasar kepentingan, fakta, bukti, kewenangan dan petitum permohonan",False,True),
    TemplateSpec("Memori Banding","Upaya Hukum","Pembanding","Terbanding","Keberatan terhadap pertimbangan/amar putusan dan permohonan banding",False,True),
    TemplateSpec("Kontra Memori Banding","Upaya Hukum","Terbanding","Pembanding","Tanggapan terhadap alasan banding dan pertahanan putusan",False,True),
    TemplateSpec("Memori Kasasi","Upaya Hukum","Pemohon Kasasi","Termohon Kasasi","Alasan kasasi yang relevan dan keberatan penerapan hukum",False,True),
    TemplateSpec("Kontra Memori Kasasi","Upaya Hukum","Termohon Kasasi","Pemohon Kasasi","Tanggapan atas alasan kasasi dan permohonan akhir",False,True),
    TemplateSpec("Permohonan Praperadilan","Litigasi Pidana","Pemohon","Termohon","Objek praperadilan, tindakan yang diuji, fakta, bukti dan petitum",False,True),
    TemplateSpec("Eksepsi Pidana","Litigasi Pidana","Terdakwa / Penasihat Hukum","Penuntut Umum","Keberatan terhadap surat dakwaan/kompetensi atau aspek formil lain",False,True),
    TemplateSpec("Nota Pembelaan / Pledoi","Litigasi Pidana","Terdakwa / Penasihat Hukum","Penuntut Umum","Fakta persidangan, unsur dakwaan, pembuktian, pembelaan dan permohonan",False,True),
    TemplateSpec("Legal Opinion","Advisory","Klien / Pemohon","Pihak / Objek Terkait","Pertanyaan hukum, fakta utama, dokumen tersedia dan tujuan pendapat",False),
    TemplateSpec("Legal Memorandum","Advisory","Klien / Matter","Pihak / Objek Terkait","Issue, short answer, facts, authorities, analysis, counter-analysis dan rekomendasi",False),
    TemplateSpec("Addendum Perjanjian","Kontrak","Pihak Pertama","Pihak Kedua","Perjanjian induk, pasal yang diubah, alasan perubahan dan tanggal efektif",False),
    TemplateSpec("Memorandum of Understanding (MoU)","Kontrak","Pihak Pertama","Pihak Kedua","Tujuan kerja sama, ruang lingkup awal, sifat mengikat/tidak mengikat dan tindak lanjut",True),
    TemplateSpec("Perjanjian Jasa Hukum","Kontrak","Klien","Advokat / Kantor Hukum","Ruang lingkup jasa, honorarium, biaya, kewajiban klien, kerahasiaan dan penghentian",True),
    TemplateSpec("Perjanjian Lisensi / Hak Kekayaan Intelektual","Kontrak","Pemberi Lisensi","Penerima Lisensi","Objek HKI, wilayah, eksklusivitas, royalti, penggunaan dan penghentian",True),
    TemplateSpec("Surat Pernyataan","Dokumen Pernyataan","Pemberi Pernyataan","Pihak Terkait","Fakta/pernyataan yang dinyatakan, tujuan penggunaan dan lampiran pendukung",False),
    TemplateSpec("Tanggapan Somasi","Pra-Litigasi","Klien / Penerima Somasi","Pihak Pemberi Somasi","Identifikasi somasi, posisi fakta, bantahan/pengakuan terbatas dan usulan penyelesaian",False),
    TemplateSpec("Gugatan PHI","Litigasi Ketenagakerjaan","Penggugat","Tergugat","Hubungan kerja, perselisihan, proses bipartit/mediasi, hak normatif, bukti dan petitum",False,True),
    TemplateSpec("Jawaban PHI","Litigasi Ketenagakerjaan","Tergugat","Penggugat","Eksepsi bila relevan, bantahan hubungan kerja/hak, bukti dan petitum jawaban",False,True),
    TemplateSpec("Gugatan PTUN","Litigasi TUN","Penggugat","Tergugat / Badan atau Pejabat TUN","Objek keputusan/tindakan, tenggat, upaya administratif, kepentingan, alasan gugatan dan petitum",False,True),
    TemplateSpec("Jawaban PTUN","Litigasi TUN","Tergugat","Penggugat","Kompetensi, tenggat, upaya administratif, legalitas objek, bantahan dan petitum",False,True),
    TemplateSpec("Eksepsi PTUN","Litigasi TUN","Tergugat","Penggugat","Kompetensi absolut/relatif, tenggat, upaya administratif, objek sengketa, kedudukan hukum atau eksepsi lain yang relevan",False,True),
    TemplateSpec("Replik PTUN","Litigasi TUN","Penggugat","Tergugat","Tanggapan atas jawaban/eksepsi Tergugat secara isu-per-isu, penegasan posita dan petitum",False,True),
    TemplateSpec("Duplik PTUN","Litigasi TUN","Tergugat","Penggugat","Tanggapan atas replik, penegasan jawaban/eksepsi dan petitum",False,True),
    TemplateSpec("Permohonan Eksekusi","Eksekusi","Pemohon Eksekusi","Termohon Eksekusi","Putusan berkekuatan hukum, amar yang belum dipenuhi, riwayat teguran dan objek eksekusi",False,True),
    TemplateSpec("Permohonan Penangguhan Penahanan","Litigasi Pidana","Tersangka / Terdakwa","Penyidik / Penuntut Umum / Majelis","Status penahanan, alasan, jaminan, alamat, komitmen hadir dan permohonan",False,True),
    TemplateSpec("Gugatan Cerai","Peradilan Agama / Keluarga","Penggugat","Tergugat","Perkawinan, anak, alasan perceraian, upaya damai, hak terkait dan petitum",False,True),
    TemplateSpec("Permohonan Cerai Talak","Peradilan Agama / Keluarga","Pemohon","Termohon","Perkawinan, anak, alasan talak, upaya damai, kewajiban akibat talak dan petitum",False,True),
    TemplateSpec("Permohonan Penetapan Ahli Waris","Peradilan Agama / Waris","Pemohon","Pihak Terkait","Pewaris, silsilah, ahli waris, harta terkait, bukti status dan petitum",False,True),
    TemplateSpec("Surat Pengaduan / Laporan Hukum","Pra-Litigasi / Pelaporan","Pelapor / Pengadu","Instansi Tujuan","Kronologi, pihak, bukti, kerugian/akibat, dasar kewenangan instansi dan permohonan tindak lanjut",False),
]

TEMPLATE_REGISTRY: Dict[str, TemplateSpec] = {x.name: x for x in SPECS}


def template_catalog():
    return [
        {"name": s.name, "category": s.category, "party1_label": s.p1, "party2_label": s.p2,
         "prompt_label": s.prompt, "duration": s.duration, "forum_sensitive": s.forum_sensitive}
        for s in SPECS
    ]


def _header(title: str, date: str) -> str:
    return f"{title.upper()}\n\nTanggal: {date or '[TANGGAL]'}\n"


def _litigation(title, p1, p2, instruction, date, sections):
    body=[_header(title,date), f"PIHAK / KAPASITAS UTAMA\n{p1 or '[PIHAK UTAMA]'}\n\nPIHAK LAWAN / TERKAIT\n{p2 or '[PIHAK LAWAN/TERKAIT]'}"]
    for n,(h,t) in enumerate(sections,1): body.append(f"\n{n}. {h}\n{t}")
    body.append(f"\nINSTRUKSI / FAKTA MATTER\n{instruction}")
    body.append("\nDASAR HUKUM\n[Masukkan hanya peraturan/pasal/putusan yang telah diverifikasi melalui Regulatory Corpus/Legal Research.]")
    body.append("\nPENUTUP / PERMOHONAN\n[Sesuaikan secara konsisten dengan posisi, bukti, forum, dan hukum acara yang berlaku.]")
    return "\n".join(body)+_working_note()


CONTRACT_TYPES = {
    "Perjanjian Kerjasama", "Non-Disclosure Agreement", "Perjanjian Kerja",
    "Perjanjian Sewa Menyewa", "Perjanjian Utang Piutang", "Perjanjian Perdamaian",
    "Addendum Perjanjian", "Memorandum of Understanding (MoU)",
    "Perjanjian Jasa Hukum", "Perjanjian Lisensi / Hak Kekayaan Intelektual",
}


def _ensure_contract_core_clauses(clauses):
    """Append mandatory contract architecture only when an equivalent clause is absent."""
    rows=list(clauses)
    normalized=[]
    for heading, text in rows:
        h=heading
        hu=h.upper()
        if 'PERNYATAAN & JAMINAN' in hu and 'REPRESENTATIONS & WARRANTIES' not in hu:
            h = h + ' (REPRESENTATIONS & WARRANTIES)'
        if 'WANPRESTASI' in hu and 'DEFAULT' not in hu:
            h = h.replace('WANPRESTASI', 'WANPRESTASI / DEFAULT')
        elif 'CIDERA JANJI' in hu and 'DEFAULT' not in hu:
            h = h.replace('CIDERA JANJI', 'WANPRESTASI / DEFAULT')
        hu=h.upper()
        if hu == 'PENYELESAIAN PERSELISIHAN':
            h='PENYELESAIAN PERSELISIHAN / SENGKETA'
        elif hu == 'SENGKETA':
            h='PENYELESAIAN PERSELISIHAN / SENGKETA'
        elif hu == 'REMEDI & SENGKETA':
            h='REMEDI & PENYELESAIAN SENGKETA, FORUM & YURISDIKSI'
        normalized.append((h,text))
    rows=normalized
    headings=[h.upper() for h,_ in rows]
    def has_any(*tokens):
        return any(any(t in h for t in tokens) for h in headings)
    required=[
        (("DEFINISI",), ("DEFINISI", "Tetapkan istilah kunci, objek, Hari Kerja, Informasi Rahasia, Keadaan Memaksa, dan istilah transaksi lain yang mempengaruhi penafsiran. Definisi tidak boleh memperluas kewajiban secara tersembunyi.")),
        (("HAK & KEWAJIBAN","HAK DAN KEWAJIBAN"), ("HAK & KEWAJIBAN PARA PIHAK", "Rinci hak, kewajiban, prestasi/deliverable, standar pelaksanaan, dependensi, tenggat, bukti pemenuhan, dan kewajiban kerja sama masing-masing pihak secara seimbang.")),
        (("PERNYATAAN & JAMINAN","PERNYATAAN DAN JAMINAN"), ("PERNYATAAN & JAMINAN (REPRESENTATIONS & WARRANTIES)", "Masing-masing pihak menyatakan memiliki kapasitas dan kewenangan, informasi material yang diberikan tidak menyesatkan, serta pelaksanaan perjanjian tidak melanggar komitmen lain yang mengikatnya. Tambahkan jaminan sektoral hanya jika faktanya terverifikasi.")),
        (("WANPRESTASI","DEFAULT"), ("WANPRESTASI / DEFAULT & CURE PERIOD", "Definisikan pelanggaran material dan non-material, mekanisme pemberitahuan tertulis, jangka waktu perbaikan yang wajar, akibat kegagalan memperbaiki, serta hak penghentian/ganti rugi hanya sepanjang didukung kontrak dan hukum yang berlaku.")),
        (("FORCE MAJEURE","KEADAAN MEMAKSA"), ("KEADAAN MEMAKSA / FORCE MAJEURE", "Definisikan kejadian di luar kendali wajar, kewajiban pemberitahuan, pembuktian, mitigasi, penangguhan kewajiban yang terdampak, dan hak penghentian bila gangguan berlangsung melewati batas waktu yang disepakati.")),
        (("PENYELESAIAN PERSELISIHAN","SENGKETA"), ("PENYELESAIAN PERSELISIHAN / SENGKETA", "Atur tahapan negosiasi/musyawarah, mediasi bila dipilih, lalu forum yang berwenang. Pilihan pengadilan/arbitrase harus diisi setelah kompetensi, arbitrabilitas, dan klausul forum diverifikasi.")),
        (("DOMISILI HUKUM",), ("DOMISILI HUKUM", "Untuk pelaksanaan perjanjian, para pihak memilih domisili pada alamat resmi masing-masing dan/atau forum yang sah sebagaimana klausul penyelesaian sengketa. Pilihan domisili tidak boleh mengesampingkan kompetensi absolut yang bersifat memaksa.")),
    ]
    for tokens, clause in required:
        if not has_any(*tokens):
            rows.append(clause)
            headings.append(clause[0].upper())
    return rows


def build_legal_draft(doc_type: str, p1: str, p2: str, date: str, duration: int|str, prompt: str):
    spec=TEMPLATE_REGISTRY.get(doc_type) or TEMPLATE_REGISTRY["Perjanjian Kerjasama"]
    instruction=(prompt or "[URAIKAN FAKTA / INSTRUKSI KHUSUS]").strip()
    duration=str(duration or "[___]")

    if doc_type in {"Gugatan Perdata","Jawaban Tergugat","Eksepsi Perdata","Replik","Duplik","Kesimpulan Perdata","Permohonan Perdata"}:
        map_sections={
            "Gugatan Perdata":[
                ("IDENTITAS PARA PIHAK","[Uraikan identitas, alamat, kapasitas, kewenangan bertindak, dan kedudukan masing-masing pihak secara lengkap.]"),
                ("KEWENANGAN MENGADILI","[Uji kompetensi absolut dan relatif sebelum masuk pokok perkara.]"),
                ("POSITA / FUNDAMENTUM PETENDI — FAKTA HUKUM KRONOLOGIS","[Susun bernomor dan kronologis: peristiwa → hubungan hukum → hak/kewajiban → tindakan/kelalaian → wanprestasi/PMH atau dasar lain → kerugian → kausalitas. Bedakan fakta dari argumentasi.]"),
                ("DASAR HUKUM & KONSTRUKSI PER ISU","[Kaitkan setiap fakta material dan bukti dengan norma/pasal/putusan yang telah diverifikasi.]"),
                ("PETITUM PRIMAIR","[Rinci tuntutan satu per satu; setiap petitum harus memiliki landasan dalam posita.]"),
                ("PETITUM SUBSIDAIR","[Rumusan subsidair/ex aequo et bono hanya sepanjang tepat dan tidak menggantikan petitum yang wajib spesifik.]"),
            ],
            "Jawaban Tergugat":[
                ("IDENTITAS PARA PIHAK","[Pastikan identitas dan kapasitas sesuai gugatan.]"),
                ("EKSEPSI","[Ajukan hanya eksepsi yang memiliki dasar faktual/prosedural.]"),
                ("POSITA / FUNDAMENTUM PETENDI YANG DITANGGAPI","[Tanggapi setiap dalil secara bernomor: diakui, dibantah, atau tidak diketahui; susun counter-facts secara kronologis.]"),
                ("JAWABAN POKOK PERKARA & BUKTI","[Kaitkan bantahan dengan bukti dan dasar hukum.]"),
                ("PETITUM PRIMAIR JAWABAN","[Rumusan terhadap eksepsi dan pokok perkara.]"),
                ("PETITUM SUBSIDAIR","[Rumusan alternatif yang konsisten dengan posisi Tergugat.]"),
            ],
            "Eksepsi Perdata":[
                ("IDENTITAS PARA PIHAK","[Pastikan pihak, kapasitas, dan objek gugatan yang menjadi dasar eksepsi.]"),
                ("POSITA / FUNDAMENTUM PETENDI TERKAIT EKSEPSI","[Petakan dalil gugatan dan fakta prosedural yang menimbulkan cacat formil.]"),
                ("ANALISIS EKSEPSI","[Kompetensi, error in persona, plurium litis consortium, obscuur libel, prematuritas, ne bis in idem, atau lainnya hanya bila relevan dan didukung fakta.]"),
                ("PETITUM PRIMAIR EKSEPSI","[Rumusan sesuai jenis eksepsi.]"),
                ("PETITUM SUBSIDAIR","[Rumusan alternatif bila diperlukan.]"),
            ],
            "Replik":[
                ("IDENTITAS PARA PIHAK","[Pertahankan konsistensi identitas dan kapasitas.]"),
                ("POSITA / FUNDAMENTUM PETENDI — PENEGASAN KRONOLOGI","[Jawab eksepsi/jawaban isu-per-isu dan tegaskan kembali fakta hukum secara kronologis, tanpa memperkenalkan klaim baru yang tidak semestinya.]"),
                ("TANGGAPAN BUKTI & KONSTRUKSI HUKUM","[Hubungkan fakta/bukti dengan norma yang telah diverifikasi.]"),
                ("PETITUM PRIMAIR","[Tegaskan tuntutan utama.]"),
                ("PETITUM SUBSIDAIR","[Tegaskan tuntutan alternatif bila relevan.]"),
            ],
            "Duplik":[
                ("IDENTITAS PARA PIHAK","[Pertahankan konsistensi identitas dan kapasitas.]"),
                ("POSITA / FUNDAMENTUM PETENDI YANG DITANGGAPI","[Jawab replik secara isu-per-isu dan tegaskan counter-chronology/fakta pembantah.]"),
                ("PENEGASAN JAWABAN, BUKTI & HUKUM","[Pertahankan hanya dalil yang masih relevan dan didukung.]"),
                ("PETITUM PRIMAIR","[Tegaskan permohonan utama.]"),
                ("PETITUM SUBSIDAIR","[Tegaskan alternatif bila relevan.]"),
            ],
            "Kesimpulan Perdata":[
                ("IDENTITAS PARA PIHAK","[Identifikasi posisi para pihak.]"),
                ("POSITA / FAKTA YANG TERBUKTI","[Susun kronologi final dan petakan fakta terhadap alat bukti.]"),
                ("ANALISIS HUKUM","[Fakta → bukti → norma → konsekuensi hukum.]"),
                ("PETITUM / PERMOHONAN PRIMAIR","[Rumusan akhir sesuai proses persidangan.]"),
                ("PETITUM / PERMOHONAN SUBSIDAIR","[Rumusan alternatif bila relevan.]"),
            ],
            "Permohonan Perdata":[
                ("IDENTITAS PARA PIHAK / PEMOHON","[Uraikan identitas, kapasitas, kedudukan dan pihak terkait.]"),
                ("POSITA / FUNDAMENTUM PETENDI","[Susun kepentingan, fakta dan hubungan hukum secara kronologis.]"),
                ("DASAR KEWENANGAN & BUKTI","[Uji kompetensi dan daftar bukti relevan.]"),
                ("PETITUM PRIMAIR","[Permohonan yang diminta secara spesifik.]"),
                ("PETITUM SUBSIDAIR","[Alternatif bila secara hukum tepat.]"),
            ],
        }
        return _litigation(doc_type,p1,p2,instruction,date,map_sections[doc_type]), len(map_sections[doc_type])

    if doc_type in {"Gugatan PHI","Jawaban PHI","Gugatan PTUN","Jawaban PTUN","Eksepsi PTUN","Replik PTUN","Duplik PTUN","Permohonan Eksekusi","Permohonan Penangguhan Penahanan","Gugatan Cerai","Permohonan Cerai Talak","Permohonan Penetapan Ahli Waris"}:
        special={
          "Gugatan PHI":[("KOMPETENSI & TAHAP PRA-LITIGASI","[Verifikasi kewenangan PHI serta proses bipartit/mediasi yang diwajibkan.]"),("HUBUNGAN KERJA & KRONOLOGI","[Status, masa kerja, upah, tindakan yang disengketakan.]"),("HAK NORMATIF / KERUGIAN","[Rinci komponen berdasarkan bukti; jangan mengarang formula.]"),("BUKTI","[Perjanjian kerja, PKB/PP, slip upah, surat, risalah.]"),("PETITUM","[Konsisten dengan posita dan kewenangan forum.]")],
          "Jawaban PHI":[("KOMPETENSI / EKSEPSI","[Ajukan hanya bila relevan.]"),("JAWABAN HUBUNGAN KERJA","[Akui/bantah fakta secara bernomor.]"),("JAWABAN HAK NORMATIF","[Uji dasar dan perhitungan terhadap bukti.]"),("BUKTI","[Dokumen perusahaan/pekerja.]"),("PETITUM JAWABAN","[Rumusan akhir.]")],
          "Gugatan PTUN":[("IDENTITAS PARA PIHAK","[Identitas Penggugat dan Badan/Pejabat TUN, kapasitas, alamat dan kedudukan hukum.]"),("OBJEK, KOMPETENSI, TENGGAT & UPAYA ADMINISTRATIF","[Identifikasi keputusan/tindakan, forum, tanggal diketahui, tenggat dan upaya administratif.]"),("POSITA / FUNDAMENTUM PETENDI — KRONOLOGI FAKTA HUKUM","[Susun peristiwa administratif secara berurutan hingga timbul kerugian/kepentingan yang dirugikan.]"),("LEGAL CONSTRUCTION","[Uji kewenangan, prosedur, substansi, AUPB dan dasar hukum yang telah diverifikasi.]"),("PETITUM PRIMAIR","[Rinci tuntutan yang berada dalam kewenangan PTUN.]"),("PETITUM SUBSIDAIR","[Rumusan alternatif bila relevan.]")],
          "Jawaban PTUN":[("IDENTITAS PARA PIHAK","[Pastikan identitas, jabatan/kewenangan, dan kapasitas.]"),("EKSEPSI / KOMPETENSI / TENGGAT","[Uji forum, objek, tenggat dan upaya administratif.]"),("POSITA / FUNDAMENTUM PETENDI YANG DITANGGAPI","[Tanggapi kronologi dan dalil Penggugat secara bernomor.]"),("LEGALITAS OBJEK & BUKTI ADMINISTRASI","[Uji kewenangan, prosedur, substansi, AUPB, serta dokumen administratif.]"),("PETITUM PRIMAIR","[Rumusan jawaban utama.]"),("PETITUM SUBSIDAIR","[Rumusan alternatif bila relevan.]")],
          "Eksepsi PTUN":[("IDENTITAS PARA PIHAK","[Pastikan pihak dan kapasitas.]"),("POSITA / FUNDAMENTUM PETENDI TERKAIT EKSEPSI","[Petakan dalil yang berkaitan dengan kompetensi, objek, tenggat, upaya administratif atau kedudukan hukum.]"),("ANALISIS EKSEPSI","[Uraikan kontradiksi/cacat prosedural secara terpisah dan terverifikasi.]"),("PETITUM PRIMAIR","[Rumusan eksepsi utama.]"),("PETITUM SUBSIDAIR","[Alternatif bila relevan.]")],
          "Replik PTUN":[("IDENTITAS PARA PIHAK","[Konsistensi identitas dan kapasitas.]"),("POSITA / FUNDAMENTUM PETENDI — PENEGASAN KRONOLOGI","[Tanggapi jawaban/eksepsi dan tegaskan kronologi administratif.]"),("TANGGAPAN LEGALITAS & BUKTI","[Kaitkan dengan objek, kewenangan, prosedur, substansi dan AUPB.]"),("PETITUM PRIMAIR","[Tegaskan tuntutan utama.]"),("PETITUM SUBSIDAIR","[Alternatif bila relevan.]")],
          "Duplik PTUN":[("IDENTITAS PARA PIHAK","[Konsistensi identitas dan kapasitas.]"),("POSITA / FUNDAMENTUM PETENDI YANG DITANGGAPI","[Jawab replik isu-per-isu.]"),("PENEGASAN LEGALITAS & BUKTI","[Pertahankan dalil yang didukung dokumen administratif.]"),("PETITUM PRIMAIR","[Tegaskan permohonan utama.]"),("PETITUM SUBSIDAIR","[Alternatif bila relevan.]")],
          "Permohonan Eksekusi":[("IDENTITAS PUTUSAN","[Nomor, tanggal, amar, status inkracht.]"),("KEWAJIBAN YANG BELUM DIPENUHI","[Petakan amar dan pelaksanaan.]"),("RIWAYAT PEMENUHAN / TEGURAN","[Tanggal dan bukti.]"),("OBJEK EKSEKUSI","[Identifikasi bila relevan.]"),("PERMOHONAN","[Minta tindakan dalam kewenangan pengadilan.]")],
          "Permohonan Penangguhan Penahanan":[("STATUS PENAHANAN","[Instansi, dasar, tanggal, jenis penahanan.]"),("ALASAN PERMOHONAN","[Fakta personal/prosedural yang relevan; hindari klaim tanpa bukti.]"),("JAMINAN / KOMITMEN","[Orang/uang bila ada, alamat, hadir, tidak menghilangkan bukti.]"),("DOKUMEN PENDUKUNG","[Identitas, domisili, kesehatan/keluarga bila relevan.]"),("PERMOHONAN","[Penangguhan/pengalihan sesuai kewenangan.]")],
          "Gugatan Cerai":[("KOMPETENSI","[Verifikasi absolut/relatif dan status para pihak.]"),("PERKAWINAN & KELUARGA","[Akta nikah, anak, domisili.]"),("ALASAN & KRONOLOGI","[Fakta spesifik, upaya damai.]"),("HAK TERKAIT","[Anak, nafkah, harta bila dimohon dan forum berwenang.]"),("PETITUM","[Konsisten dengan fakta dan kewenangan.]")],
          "Permohonan Cerai Talak":[("KOMPETENSI","[Verifikasi absolut/relatif.]"),("PERKAWINAN & KELUARGA","[Akta nikah, anak, domisili.]"),("ALASAN TALAK & UPAYA DAMAI","[Fakta spesifik.]"),("KEWAJIBAN AKIBAT TALAK","[Identifikasi isu yang perlu diverifikasi.]"),("PETITUM","[Permohonan izin ikrar talak dan terkait bila relevan.]")],
          "Permohonan Penetapan Ahli Waris":[("KOMPETENSI","[Verifikasi forum berdasarkan status para pihak.]"),("IDENTITAS PEWARIS","[Kematian, perkawinan, domisili.]"),("SILSILAH / AHLI WARIS","[Hubungan keluarga dan bukti.]"),("DOKUMEN PENDUKUNG","[Akta, KK, nikah, kematian, dll.]"),("PETITUM","[Penetapan pihak yang dimohon sebagai ahli waris.]")],
        }
        return _litigation(doc_type,p1,p2,instruction,date,special[doc_type]), len(special[doc_type])

    if doc_type in {"Memori Banding","Kontra Memori Banding","Memori Kasasi","Kontra Memori Kasasi"}:
        sections=[("IDENTITAS PUTUSAN YANG DIUJI","[Nomor perkara, pengadilan, tanggal putusan, posisi pihak.]"),("TENGGAT & FORMALITAS UPAYA HUKUM","[Verifikasi tenggat dan syarat formal.]"),("ALASAN / TANGGAPAN UPAYA HUKUM","[Susun per isu dan kaitkan dengan pertimbangan putusan.]"),("ANALISIS HUKUM & BUKTI","[Bedakan isu fakta, pembuktian, dan penerapan hukum.]"),("PERMOHONAN","[Rumusan akhir sesuai jenis upaya hukum.]")]
        return _litigation(doc_type,p1,p2,instruction,date,sections), len(sections)

    if doc_type in {"Permohonan Praperadilan","Eksepsi Pidana","Nota Pembelaan / Pledoi"}:
        sections={
            "Permohonan Praperadilan":[("OBJEK YANG DIUJI","[Nyatakan tindakan/proses yang menjadi objek secara spesifik.]"),("KRONOLOGI PROSEDURAL","[Tanggal tindakan, pemberitahuan, pemeriksaan dan upaya paksa.]"),("FAKTA & BUKTI","[Pisahkan source fact dan argument.]"),("ISU HUKUM ACARA","[Uji dasar kewenangan, prosedur dan alat bukti.]"),("PETITUM","[Permohonan yang berada dalam ruang lingkup kewenangan forum.]")],
            "Eksepsi Pidana":[("IDENTITAS & BENTUK SURAT DAKWAAN","[Nomor, tanggal, bentuk dakwaan, pasal yang didakwakan, dan identitas Terdakwa.]"),("UJI SYARAT FORMIL DAN MATERIIL DAKWAAN — PASAL 143 KUHAP","[Fokus pada kecermatan, kejelasan, kelengkapan serta syarat formil/materiil surat dakwaan. Pasal 143 KUHAP harus diverifikasi terhadap KUHAP yang berlaku menurut tempus perkara sebelum dijadikan dasar final.]"),("KEBERATAN KOMPETENSI / YURIDIS LAIN","[Ajukan hanya jika termasuk ruang lingkup eksepsi dan didukung fakta/prosedur.]"),("FAKTA & DOKUMEN PENDUKUNG","[Pisahkan fakta prosedural, kutipan dakwaan, dan argumentasi hukum.]"),("PETITUM / PERMOHONAN","[Rumusan konsekuensi yang dimohon sesuai cacat yang teridentifikasi dan kewenangan Majelis.]" )],
            "Nota Pembelaan / Pledoi":[("RINGKASAN DAKWAAN & TUNTUTAN","[Jangan mengubah isi; petakan setiap dakwaan dan unsur pasal.]"),("FAKTA PERSIDANGAN & ALAT BUKTI","[Fakta yang benar-benar muncul di persidangan, sumber alat bukti, dan kontradiksi material.]"),("MATRIS PEMBUKTIAN UNSUR PASAL","[Uji unsur demi unsur: unsur objektif, subjektif/mens rea, perbuatan, akibat/kausalitas, kualitas subjek, dan pertanggungjawaban individual sesuai delik.]"),("ANALISIS BEBAN & KEKUATAN PEMBUKTIAN","[Kaitkan setiap unsur dengan alat bukti yang diajukan Penuntut Umum dan counter-evidence pembelaan.]"),("COUNTER-ANALYSIS TERHADAP TUNTUTAN","[Tanggapi konstruksi Penuntut Umum, inferensi, kontradiksi, dan missing link.]"),("HAL MERINGANKAN / MITIGASI","[Hanya yang didukung fakta dan relevan bila pembelaan alternatif diperlukan.]"),("PETITUM / PERMOHONAN","[Rumuskan bebas/lepas atau permohonan alternatif hanya jika konsisten dengan analisis dan hukum yang berlaku.]" )],
        }[doc_type]
        return _litigation(doc_type,p1,p2,instruction,date,sections), len(sections)

    if doc_type == "Surat Kuasa Khusus":
        content=f"""SURAT KUASA KHUSUS\n\nTanggal: {date}\n\nPEMBERI KUASA\n{p1}\n[Identitas/alamat]\n\nPENERIMA KUASA\n{p2}\n[Identitas/profesi/alamat]\n\n-------------------------------- KHUSUS --------------------------------\n{instruction}\n\nLINGKUP KUASA\n1. Menghadap forum/instansi yang relevan sesuai ruang lingkup perkara;\n2. Mengajukan, menerima, menandatangani dan menanggapi dokumen yang secara sah diperlukan;\n3. Menghadiri mediasi, pemeriksaan, persidangan atau tindakan prosedural yang termasuk objek kuasa;\n4. [Rinci kewenangan khusus lain.]\n\nBATASAN / SUBSTITUSI / PERDAMAIAN / UPAYA HUKUM\n[Nyatakan secara tegas; jangan diasumsikan otomatis.]\n\nPemberi Kuasa,                         Penerima Kuasa,\n\n{p1}                                  {p2}"""+_working_note()
        return content,4

    if doc_type == "Somasi":
        content=f"""SOMASI / TEGURAN HUKUM\n\nTanggal: {date}\nKepada Yth.\n{p2}\n\nDari / untuk kepentingan: {p1}\n\nI. KRONOLOGI & HUBUNGAN HUKUM\n{instruction}\n\nII. KEWAJIBAN / PELANGGARAN YANG DIPERSOALKAN\n[Uraikan prestasi, pelanggaran, tanggal dan bukti.]\n\nIII. TUNTUTAN\n1. [Tindakan konkret];\n2. [Pemulihan/pembayaran bila memiliki dasar];\n3. Jawaban tertulis dalam [___] hari sejak diterima.\n\nIV. RESERVASI HAK\nApabila tidak diselesaikan, pemberi somasi akan mempertimbangkan langkah hukum yang tersedia berdasarkan fakta, bukti, forum berwenang dan hukum yang berlaku."""+_working_note()
        return content,4

    if doc_type in {"Legal Opinion","Legal Memorandum"}:
        sections=[
            ("KASUS POSISI (FAKTA)", instruction + "\n[Susun kronologi, para pihak, dokumen, transaksi/tindakan, dan fakta material. Tandai fakta yang belum terverifikasi.]"),
            ("ISU HUKUM (LEGAL ISSUES)", "[Rumusan pertanyaan hukum secara bernomor dan terukur; pisahkan isu utama, turunan, kompetensi, tempus, dan pembuktian bila relevan.]"),
            ("DASAR HUKUM / REGULASI (LEGAL FRAMEWORK)", "[Cantumkan hanya regulasi, pasal/ayat, putusan, dan doktrin yang telah diverifikasi; jelaskan status berlaku, hierarki, tempus, dan relevansinya.]"),
            ("ANALISIS HUKUM PER ISU (LEGAL ANALYSIS)", "[Untuk setiap isu: Rule → Facts → Application → Counter-argument → Conclusion. Kaitkan fakta dan bukti dengan norma secara eksplisit.]"),
            ("KESIMPULAN & REKOMENDASI MITIGASI", "[Jawab setiap isu secara singkat; bedakan kesimpulan pasti, bersyarat, dan belum terverifikasi. Susun tindakan mitigasi, dokumen tambahan, tenggat, forum, dan next steps secara prioritas.]"),
        ]
        body=[_header(doc_type,date),f"Klien/Matter: {p1 or '[KLIEN / MATTER]'}\nPihak/Objek terkait: {p2 or '[PIHAK / OBJEK TERKAIT]'}"]
        for i,(h,t) in enumerate(sections,1): body.append(f"\n{i}. {h}\n{t}")
        return "\n".join(body)+_working_note(), len(sections)

    if doc_type == "Perjanjian Perdamaian":
        clauses=[("LATAR BELAKANG SENGKETA",instruction),("RUANG LINGKUP PERDAMAIAN","Definisikan klaim/isu yang diselesaikan."),("KEWAJIBAN PARA PIHAK","Rinci tindakan, jumlah, tenggat dan bukti pemenuhan."),("PELEPASAN / RESERVASI KLAIM","Batasi secara spesifik; jangan menghapus hak yang tidak dimaksudkan."),("KERAHASIAAN BILA RELEVAN","Atur proporsional."),("WANPRESTASI ATAS PERDAMAIAN","Atur cure period dan konsekuensi."),("PENYELESAIAN SENGKETA","Tentukan forum setelah diverifikasi."),("PENUTUP","Kewenangan, perubahan, pemberitahuan dan tanda tangan.")]
    elif doc_type == "Non-Disclosure Agreement":
        clauses=[("DEFINISI INFORMASI RAHASIA","Definisikan ruang lingkup dan pengecualian."),("TUJUAN PENGUNGKAPAN",instruction),("KEWAJIBAN PENERIMA","Pembatasan akses, penggunaan dan pengamanan."),("PENGECUALIAN","Informasi publik/sah/wajib diungkap."),("JANGKA WAKTU",f"Sejak {date} selama {duration} bulan atau periode lain yang sah."),("PENGEMBALIAN / PEMUSNAHAN","Atur retensi wajib hukum."),("DATA PRIBADI","Atur peran dan kewajiban pemrosesan bila relevan."),("REMEDI & SENGKETA","Remedi dan forum secara proporsional.")]
    elif doc_type == "Perjanjian Kerja":
        clauses=[("PARA PIHAK & JABATAN",instruction),("JENIS & JANGKA HUBUNGAN KERJA",f"Mulai {date}; durasi input {duration} bulan. Sesuaikan dengan ketentuan berlaku."),("TEMPAT/WAKTU KERJA","Rinci jam, istirahat, lembur dan pola kerja."),("UPAH & TUNJANGAN","Rinci komponen, jadwal, pajak dan jaminan sosial."),("HAK & KEWAJIBAN","Tugas, standar, keselamatan, kebijakan."),("KERAHASIAAN & DATA","Proporsional dan sesuai hukum."),("DISIPLIN / PELANGGARAN","Prosedur dan dokumentasi."),("BERAKHIRNYA HUBUNGAN KERJA","Hak normatif tidak boleh ditiadakan kontrak."),("SENGKETA","Ikuti mekanisme hubungan industrial yang berlaku.")]
    elif doc_type == "Perjanjian Sewa Menyewa":
        # v1.3.13 — lease template expanded from the supplied Indonesian house-lease
        # structure.  Placeholders are intentional: LexiCore must not invent title,
        # certificate, payment, deposit, forum, or factual condition data.
        clauses=[
            ("IDENTITAS, KAPASITAS & KEWENANGAN PARA PIHAK",
             f"PEMBERI SEWA: {p1 or '[NAMA / IDENTITAS LENGKAP / ALAMAT / NIK / KAPASITAS]'}\n"
             f"PENYEWA: {p2 or '[NAMA / IDENTITAS LENGKAP / ALAMAT / NIK / KAPASITAS]'}\n"
             "Masing-masing pihak menyatakan memiliki kecakapan dan kewenangan untuk menandatangani perjanjian ini. "
             "Jika bertindak untuk badan hukum/kuasa/pemilik bersama, cantumkan dasar kewenangannya."),
            ("OBJEK SEWA & STATUS PENGUASAAN",
             instruction + "\nRinci alamat lengkap, jenis/luas bangunan atau ruang, batas/nomor unit bila relevan, fasilitas yang ikut disewa, "
             "serta dokumen yang menunjukkan hak/kewenangan Pemberi Sewa. Lampiran foto/denah/inventaris dapat menjadi bagian perjanjian."),
            ("TUJUAN & BATAS PENGGUNAAN",
             "Tentukan penggunaan yang diperbolehkan (misalnya tempat tinggal) dan penggunaan yang dilarang. "
             "Perubahan tujuan penggunaan memerlukan persetujuan tertulis Pemberi Sewa."),
            ("JANGKA WAKTU SEWA",
             f"Sewa dimulai pada {date or '[TANGGAL MULAI]'} untuk jangka waktu {duration} bulan, sampai [TANGGAL BERAKHIR]. "
             "Nyatakan kapan penyerahan kunci/penguasaan efektif dilakukan dan apakah ada masa persiapan."),
            ("HARGA SEWA, CARA PEMBAYARAN & BUKTI PELUNASAN",
             "Cantumkan nilai sewa dalam angka dan huruf, jadwal/termin, rekening atau metode pembayaran, tanggal jatuh tempo, "
             "serta bukti pembayaran. Tegaskan apakah pembayaran di muka merupakan pelunasan seluruh masa sewa atau pembayaran periodik."),
            ("DEPOSIT / UANG JAMINAN BILA DISEPAKATI",
             "Jika ada deposit, cantumkan jumlah, tujuan penggunaannya, kondisi pemotongan, kewajiban pembuktian biaya, "
             "dan batas waktu pengembalian saldo setelah objek dikembalikan. Jika tidak ada deposit, nyatakan secara tegas."),
            ("SERAH TERIMA, KONDISI AWAL & INVENTARIS",
             "Buat Berita Acara Serah Terima yang mencatat kondisi bangunan, meter listrik/air, jumlah kunci, furnitur/peralatan, "
             "foto kondisi awal, kerusakan yang sudah ada, dan tanda tangan para pihak."),
            ("JAMINAN PEMBERI SEWA & KENIKMATAN TENTERAM",
             "Pemberi Sewa menjamin mempunyai kewenangan menyewakan objek, mengungkapkan sengketa/beban yang material bila ada, "
             "dan tidak mengganggu penggunaan yang sah oleh Penyewa selama Penyewa memenuhi kewajibannya."),
            ("HAK & KEWAJIBAN PEMBERI SEWA",
             "Atur kewajiban menyerahkan objek sesuai kondisi yang disepakati, menangani kerusakan yang menjadi tanggung jawabnya, "
             "memberikan bukti pembayaran, serta mekanisme pemberitahuan jika perlu memasuki objek."),
            ("HAK & KEWAJIBAN PENYEWA",
             "Atur kewajiban menggunakan secara wajar, menjaga kebersihan/keamanan, membayar kewajiban tepat waktu, "
             "memberitahukan kerusakan penting, dan mengembalikan objek sesuai kondisi yang disepakati dengan memperhitungkan keausan wajar."),
            ("UTILITAS, IURAN, PAJAK & BIAYA LAIN",
             "Pisahkan secara jelas siapa menanggung listrik, air/PDAM, internet, iuran lingkungan, kebersihan, keamanan, "
             "pajak atau biaya lain yang relevan. Catat meter awal dan prosedur pelunasan saat sewa berakhir."),
            ("PEMELIHARAAN, PERBAIKAN & KERUSAKAN",
             "Bedakan pemeliharaan rutin, kerusakan akibat kesalahan/kelalaian Penyewa, kerusakan struktural, kerusakan yang sudah ada, "
             "dan keausan wajar. Atur pemberitahuan, persetujuan perbaikan, bukti biaya, serta keadaan darurat."),
            ("LARANGAN PENGALIHAN, SUBSEWA & PERUBAHAN OBJEK",
             "Penyewa tidak boleh mengalihkan/submenyewakan tanpa persetujuan tertulis. Atur pula renovasi, perubahan struktur/instalasi, "
             "perubahan warna, penambahan bangunan, pengeboran/penggalian, dan kewajiban pemulihan jika relevan."),
            ("AKSES / PEMERIKSAAN OBJEK",
             "Pemberi Sewa dapat melakukan pemeriksaan atau perbaikan dengan pemberitahuan yang wajar, kecuali keadaan darurat. "
             "Tentukan cara pemberitahuan dan batas agar tidak mengganggu penggunaan Penyewa secara tidak semestinya."),
            ("FORCE MAJEURE / KEADAAN MEMAKSA",
             "Definisikan kejadian di luar kendali wajar para pihak, kewajiban pemberitahuan, mitigasi, pengaruh terhadap kewajiban, "
             "serta hak para pihak apabila objek tidak dapat digunakan untuk jangka waktu tertentu."),
            ("CIDERA JANJI, PEMBERITAHUAN & CURE PERIOD",
             "Definisikan pelanggaran material secara objektif. Sebelum pengakhiran karena pelanggaran yang masih dapat diperbaiki, "
             "atur pemberitahuan tertulis dan jangka waktu perbaikan yang disepakati. Bedakan tunggakan pembayaran dengan pelanggaran non-pembayaran."),
            ("PENGAKHIRAN SEBELUM JATUH TEMPO",
             "Atur kondisi penghentian oleh Penyewa maupun Pemberi Sewa, jangka pemberitahuan, kewajiban yang harus diselesaikan, "
             "perlakuan atas sewa yang telah dibayar/deposit, serta konsekuensi apabila pengakhiran terjadi karena pelanggaran pihak lainnya."),
            ("BERAKHIRNYA SEWA & PENGEMBALIAN OBJEK",
             "Pada akhir sewa, atur pengosongan, penyerahan kunci, pemeriksaan akhir, pencatatan meter, pelunasan utilitas, "
             "inventaris, perbaikan kerusakan yang menjadi tanggung jawab Penyewa, dan Berita Acara Pengembalian."),
            ("PERPANJANGAN / PEMBARUAN SEWA",
             "Tentukan apakah perpanjangan otomatis atau harus berdasarkan kesepakatan tertulis baru/addendum, "
             "kapan permohonan perpanjangan diajukan, dan bahwa harga/periode baru harus disepakati."),
            ("PEMBERITAHUAN RESMI",
             "Cantumkan alamat, nomor/email yang disepakati untuk pemberitahuan; tentukan kapan pemberitahuan dianggap diterima dan kewajiban memperbarui alamat kontak."),
            ("PENYELESAIAN PERSELISIHAN",
             "Atur tahapan musyawarah/negosiasi terlebih dahulu. Pilihan forum atau mekanisme berikutnya harus diisi setelah "
             "kompetensi dan klausul penyelesaian sengketa diverifikasi berdasarkan keadaan konkret."),
            ("PERUBAHAN, KETERPISAHAN & KESELURUHAN PERJANJIAN",
             "Perubahan hanya berlaku jika dibuat tertulis dan disepakati para pihak. Atur keterpisahan klausul yang tidak dapat dilaksanakan, "
             "hubungan perjanjian dengan lampiran, dan dokumen mana yang berlaku jika terdapat pertentangan."),
            ("PENUTUP, RANGKAP, LAMPIRAN & TANDA TANGAN",
             "Nyatakan tempat/tanggal penandatanganan, jumlah rangkap, lampiran yang menjadi satu kesatuan, serta tanda tangan para pihak. "
             "Sediakan saksi bila para pihak menghendaki dan ruang paraf pada lampiran/berita acara."),
        ]
    elif doc_type == "Perjanjian Utang Piutang":
        clauses=[("JUMLAH & TUJUAN",instruction),("PENCAIRAN / PENYERAHAN","Bukti penyerahan dana."),("JANGKA WAKTU",f"Sejak {date} selama {duration} bulan."),("PEMBAYARAN","Jadwal, rekening, bukti dan pelunasan dipercepat."),("BUNGA/IMBALAN BILA ADA","Pastikan dasar, kewajaran dan kepatuhan hukum."),("JAMINAN BILA ADA","Identifikasi objek dan perfection/pendaftaran yang diperlukan."),("CIDERa JANJI & CURE PERIOD","Definisikan objektif dan proporsional."),("PENAGIHAN / EKSEKUSI","Tidak boleh bertentangan dengan prosedur hukum yang berlaku."),("SENGKETA","Forum yang sah.")]
    else:
        clauses=[("LATAR BELAKANG & TUJUAN",instruction),("RUANG LINGKUP","Deliverable, standar, jadwal dan PIC."),("JANGKA WAKTU",f"Sejak {date} selama {duration} bulan."),("HAK & KEWAJIBAN","Prestasi dan dependensi."),("NILAI/PEMBAYARAN/PAJAK","Termin, invoice, bukti, pajak."),("PERNYATAAN & JAMINAN","Kewenangan dan jaminan material."),("KERAHASIAAN & DATA","Kerahasiaan/data pribadi bila relevan."),("WANPRESTASI & CURE PERIOD","Pelanggaran material, notice dan perbaikan."),("FORCE MAJEURE","Definisi, notice, mitigasi."),("PENGAKHIRAN","Sebab dan akibat."),("SENGKETA","Tahapan dan forum yang diverifikasi."),("PENUTUP","Perubahan, keterpisahan dan pemberitahuan.")]

    if doc_type in CONTRACT_TYPES:
        clauses = _ensure_contract_core_clauses(clauses)

    body=[_header(doc_type,date),f"Para pihak: {p1} dan {p2}"]
    for n,(h,t) in enumerate(clauses,1): body.append(f"\nPASAL {n}\n{h}\n{t}")
    body.append("\nTANDA TANGAN\n\n"+f"{p1 or 'Pihak Pertama'}                         {p2 or 'Pihak Kedua'}")
    return "\n".join(body)+_working_note(), len(clauses)
