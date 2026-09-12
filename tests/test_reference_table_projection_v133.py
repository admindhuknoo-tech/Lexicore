from io import BytesIO


def _payload():
    return (
        [("Judul", "Case Analysis")],
        [
            ("Ringkasan Analisis Hukum", [
                "Status: Tahan kesimpulan - verifikasi diperlukan",
                "Matriks temuan utama: [Aspek] | [Posisi/teks dokumen] | [Temuan] | [Rekomendasi]",
                "Celah tempus [KRITIS] | - | Tempus belum cukup teridentifikasi. | Verifikasi dokumen primer.",
                "Arah strategi yang direkomendasikan:",
                "- Uji tempus terlebih dahulu.",
            ]),
            ("Pemetaan Bukti", [
                "Dasar pemetaan: KUHAP yang berlaku",
                "TABEL: [Sumber/Bukti Potensial] | [Proposisi Faktual yang Perlu Diuji] | [Status Pembuktian] | [Uji Lanjut]",
                "[Dokumen A] | Peristiwa A | Belum terverifikasi | Cocokkan dokumen asli",
            ]),
            ("Rencana Tindakan", [
                "Langkah 1 | 0-3 hari | Prioritas 1 | Periksa dokumen primer | Tujuan: Verifikasi tempus | Kondisi: PERLU DIUJI",
            ]),
            ("Kandidat Dasar Hukum yang Perlu Diverifikasi", [
                "Ranah hukum: Pidana Materiil | Sumber: UU Contoh | Status: PERLU VERIFIKASI",
            ]),
        ],
    )


def test_pdf_projects_dense_reference_sections_to_tables(monkeypatch):
    import exporters.case_pdf as mod
    from pypdf import PdfReader

    monkeypatch.setattr(mod, "_case_export_sections", lambda x: _payload())
    monkeypatch.setattr(mod, "prepare_case_export_for_reader", lambda m, s: (m, s))

    bio = mod.export_case_pdf({"title": "Case Analysis", "source_text": ""})
    text = " ".join(" ".join((p.extract_text() or "").split()) for p in PdfReader(bio).pages)

    assert "Aspek Posisi/teks dokumen Temuan Rekomendasi" in text
    assert "Sumber/Bukti Potensial" in text
    assert "Waktu/Prioritas" in text
    assert "Ranah Hukum Instrumen / Sumber Status" in text
    assert "Tempus belum cukup teridentifikasi." in text
    assert "Verifikasi dokumen primer." in text


def test_docx_projects_dense_reference_sections_to_tables(monkeypatch):
    import exporters.case_docx as mod
    from docx import Document

    monkeypatch.setattr(mod, "_case_export_sections", lambda x: _payload())
    monkeypatch.setattr(mod, "prepare_case_export_for_reader", lambda m, s: (m, s))

    doc = Document(mod.export_case_docx({"title": "Case Analysis", "source_text": ""}))
    tables = doc.tables

    # masthead + metadata + four reference-style projection tables
    assert len(tables) >= 6
    table_text = "\n".join(" | ".join(c.text for c in row.cells) for t in tables for row in t.rows)
    assert "Aspek | Posisi/teks dokumen | Temuan | Rekomendasi" in table_text
    assert "Sumber/Bukti Potensial" in table_text
    assert "Waktu/Prioritas" in table_text
    assert "Ranah Hukum | Instrumen / Sumber | Status" in table_text
    assert "Tempus belum cukup teridentifikasi." in table_text
    assert "PERLU VERIFIKASI" in table_text
