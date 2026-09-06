"""Client communication drafting for LexiCore.

Produces professional, plain-language client updates and document requests.
No legal fact, deadline, sanction, or procedural posture is invented: unknown
values remain explicit placeholders or are described conservatively.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


FIRM_SIGNOFF = "ELF - Erfan's Law Firm"


def _clean(value, fallback=""):
    value = (value or "").strip() if isinstance(value, str) else value
    return value or fallback


def _lines(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        raw = value
    else:
        raw = str(value or "").replace(";", "\n").splitlines()
    out = []
    for item in raw:
        text = str(item).strip(" \t-•0123456789.)")
        if text and text not in out:
            out.append(text)
    return out


def _default_documents(matter: str) -> list[tuple[str, str]]:
    m = (matter or "").lower()
    if any(k in m for k in ("tanah", "sertip", "sertifikat", "ptsl", "properti")):
        return [
            ("Sertipikat/bukti hak, buku tanah atau dokumen alas hak yang tersedia", "Memastikan objek, status hak, riwayat penguasaan, dan identitas dokumen yang menjadi dasar posisi hukum."),
            ("Surat ukur/peta bidang/warkah atau dokumen pendaftaran tanah yang tersedia", "Menguji kesesuaian data fisik dan yuridis serta kronologi pendaftaran/peralihan."),
            ("Identitas para pihak dan bukti kewenangan bertindak", "Memastikan kapasitas hukum, kedudukan para pihak, serta kewenangan menandatangani atau bertindak."),
            ("Korespondensi, surat, pesan, atau bukti komunikasi terkait objek sengketa", "Merekonstruksi pengetahuan para pihak, keberatan, persetujuan, penolakan, atau pemberitahuan yang relevan."),
            ("Bukti pembayaran/transaksi dan kronologi bertanggal", "Menghubungkan fakta material dengan tindakan para pihak dan memperkuat pembuktian kronologis."),
        ]
    if any(k in m for k in ("waris", "ahli waris", "warisan")):
        return [
            ("Akta/surat kematian pewaris", "Menentukan peristiwa hukum terbukanya warisan dan titik awal kronologi kewarisan."),
            ("Dokumen hubungan keluarga/ahli waris yang tersedia", "Memetakan hubungan hukum dan pihak yang berpotensi memiliki kepentingan terhadap harta warisan."),
            ("Dokumen kepemilikan atau daftar aset yang disengketakan", "Memastikan objek warisan dan dasar penguasaan/kepemilikannya."),
            ("Akta pembagian waris, hibah, jual beli, atau peralihan sebelumnya bila ada", "Menguji apakah telah terjadi perbuatan hukum yang memengaruhi bagian atau hak para pihak."),
            ("Kronologi dan komunikasi antar pihak", "Menguji konsistensi dalil, pengetahuan, persetujuan, serta waktu terjadinya peristiwa material."),
        ]
    if any(k in m for k in ("kontrak", "perjanjian", "sewa", "kerjasama", "utang", "piutang")):
        return [
            ("Perjanjian utama yang ditandatangani beserta seluruh lampirannya", "Menetapkan hak, kewajiban, prestasi, jangka waktu, forum, serta mekanisme wanprestasi yang disepakati."),
            ("Addendum, perubahan, side letter, atau korespondensi perubahan kesepakatan", "Menguji apakah ketentuan awal pernah diubah, dikesampingkan, atau ditafsirkan bersama secara berbeda."),
            ("Invoice, kuitansi, bukti transfer, atau bukti pelaksanaan prestasi", "Membuktikan pelaksanaan atau kegagalan pemenuhan kewajiban secara konkret."),
            ("Somasi/pemberitahuan dan bukti pengirimannya", "Menguji adanya pemberitahuan, kelalaian, kesempatan memperbaiki pelanggaran, dan jejak komunikasi formal."),
            ("Identitas dan dokumen kewenangan para penandatangan", "Memastikan kapasitas serta kewenangan pihak yang membuat atau melaksanakan perjanjian."),
        ]
    if any(k in m for k in ("kerja", "karyawan", "ketenagakerjaan", "phk")):
        return [
            ("Perjanjian kerja, peraturan perusahaan/PKB, dan addendum", "Menetapkan dasar hubungan kerja, hak-kewajiban, serta ketentuan internal yang relevan."),
            ("Slip upah, bukti pembayaran, absensi, dan data masa kerja", "Menguji pemenuhan hak finansial serta fakta masa dan pelaksanaan hubungan kerja."),
            ("Surat peringatan, evaluasi, atau dokumen disiplin bila ada", "Menguji dasar tindakan perusahaan dan konsistensi proses sebelum keputusan ketenagakerjaan."),
            ("Surat PHK/pengunduran diri atau korespondensi terkait berakhirnya hubungan kerja", "Menetapkan alasan, waktu, dan proses berakhirnya hubungan kerja."),
            ("Kronologi kejadian dan komunikasi para pihak", "Menghubungkan dokumen formal dengan fakta pelaksanaan hubungan kerja."),
        ]
    return [
        ("Dokumen utama yang membentuk hubungan hukum/peristiwa hukum", "Menetapkan dasar hak, kewajiban, dan objek yang sedang ditangani."),
        ("Identitas para pihak dan bukti kewenangan bertindak", "Memastikan kapasitas hukum serta siapa yang berwenang membuat keputusan atau pernyataan."),
        ("Kronologi bertanggal beserta dokumen pendukung", "Menguji urutan fakta dan konsistensi antara keterangan dengan bukti."),
        ("Korespondensi, surat, pesan, atau notifikasi yang relevan", "Merekam pemberitahuan, persetujuan, penolakan, keberatan, atau pengetahuan para pihak."),
        ("Bukti pembayaran, transaksi, serah-terima, atau pelaksanaan kewajiban", "Menguji apakah prestasi telah dipenuhi dan dampak hukum dari tindakan para pihak."),
    ]


def _requested_items(matter: str, requested_docs) -> list[tuple[str, str]]:
    custom = _lines(requested_docs)
    if not custom:
        return _default_documents(matter)
    return [(doc, "Diperlukan untuk menguji fakta, hubungan hukum, relevansi pembuktian, dan konsistensi posisi perkara; alasan spesifik akan dikonfirmasi setelah dokumen ditelaah.") for doc in custom]


def build_client_communication(payload: dict) -> dict:
    kind = _clean(payload.get("document_type"), "client_update")
    client = _clean(payload.get("client_name"), "Bapak/Ibu Klien")
    matter = _clean(payload.get("matter"), "perkara/pekerjaan hukum yang sedang kami tangani")
    next_step = _clean(payload.get("next_step"), "melanjutkan penelaahan dan menentukan langkah hukum berikutnya berdasarkan fakta serta dokumen yang terverifikasi")
    progress = _clean(payload.get("progress"), "penanganan masih berada pada tahap penelaahan dan verifikasi fakta/dokumen yang tersedia")
    deadline = _clean(payload.get("deadline"), "[TANGGAL / JAM YANG DISEPAKATI]")

    if kind == "client_update":
        subject = f"Pembaruan Perkara — {matter}"
        message = (
            f"Yth. {client},\n\n"
            f"Kami menyampaikan pembaruan mengenai {matter}.\n\n"
            f"Status saat ini\n{progress}.\n\n"
            "Makna bagi posisi hukum Anda\n"
            "Pada tahap ini, kami belum menarik kesimpulan melampaui fakta dan dokumen yang telah terverifikasi. "
            "Setiap perkembangan akan kami nilai berdasarkan kekuatan bukti, tenggat/prosedur yang relevan, serta konsekuensinya terhadap strategi perkara.\n\n"
            f"Langkah berikutnya\n{next_step}.\n\n"
            "Yang kami perlukan dari Anda\n"
            "Mohon menjaga seluruh dokumen asli, komunikasi, dan bukti elektronik terkait perkara serta tidak mengubah atau menghapus data yang mungkin relevan. "
            "Apabila terdapat perkembangan baru, mohon informasikan kepada kami sebelum mengambil tindakan atau memberikan tanggapan substantif kepada pihak lain.\n\n"
            "Kami akan menjaga komunikasi tetap terukur dan akan menyampaikan segera apabila terdapat perkembangan yang memerlukan keputusan Anda.\n\n"
            f"Hormat kami,\n{FIRM_SIGNOFF}"
        )
        return {"subject": subject, "message": message, "document_items": [], "professional_status": "DRAFT_FOR_LAWYER_REVIEW"}

    if kind == "document_request":
        items = _requested_items(matter, payload.get("requested_documents"))
        rows = []
        structured = []
        for idx, (doc, reason) in enumerate(items, 1):
            rows.append(f"{idx}. {doc}\n   Tenggat: {deadline}\n   Alasan hukum/strategis: {reason}")
            structured.append({"priority": idx, "document": doc, "deadline": deadline, "legal_reason": reason})
        subject = f"Permintaan Dokumen — {matter}"
        message = (
            f"Yth. {client},\n\n"
            f"Untuk memastikan penanganan {matter} dapat dilakukan secara akurat dan tidak didasarkan pada asumsi, kami memerlukan dokumen/informasi berikut secara berurutan:\n\n"
            + "\n\n".join(rows)
            + "\n\nCara pengiriman\nMohon kirimkan salinan yang terbaca jelas. Dokumen asli tetap disimpan dengan aman dan akan kami minta apabila verifikasi fisik diperlukan. "
              "Untuk bukti elektronik, mohon pertahankan file asli beserta metadata apabila tersedia.\n\n"
              "Apabila salah satu dokumen belum tersedia, cukup informasikan kepada kami dokumen mana yang belum dapat diperoleh dan alasannya. Hal tersebut akan kami masukkan sebagai gap pembuktian, bukan diasumsikan telah ada.\n\n"
            f"Setelah dokumen diterima\n{next_step}.\n\n"
            "Dokumen akan digunakan terbatas untuk kepentingan penanganan hukum dan penelaahan profesional perkara.\n\n"
            f"Hormat kami,\n{FIRM_SIGNOFF}"
        )
        return {"subject": subject, "message": message, "document_items": structured, "professional_status": "DRAFT_FOR_LAWYER_REVIEW"}

    subject = f"Pemberitahuan Hukum — {matter}"
    message = (
        f"Yth. {client},\n\n"
        f"Kami menyampaikan pemberitahuan terkait {matter}. {next_step}.\n\n"
        "Dokumen ini masih berupa draf komunikasi klien. Fakta, dasar hukum, tenggat, pihak tujuan, dan konsekuensi hukum harus diverifikasi lawyer sebelum dikirim atau dipergunakan secara eksternal.\n\n"
        f"Hormat kami,\n{FIRM_SIGNOFF}"
    )
    return {"subject": subject, "message": message, "document_items": [], "professional_status": "DRAFT_FOR_LAWYER_REVIEW"}
