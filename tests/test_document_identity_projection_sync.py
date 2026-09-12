from services.legal_review_engine import build_professional_review
from exporters.common import _executive_legal_review_lines, _resolved_document_header_label


def _base(text):
    return {
        "source_text": text,
        "domain_classification": {"ranah_hukum": "PIDANA"},
        "facts": [],
        "issues": [],
        "applicable_law": [],
    }


def test_jpu_report_header_reads_resolved_identity_not_legacy_classifier():
    text = "Nota Perlawanan Terdakwa telah dipelajari. Penuntut Umum memohon menolak seluruh dalil dan melanjutkan pemeriksaan perkara dengan agenda pembuktian."
    result = _base(text)
    result["professional_review"] = build_professional_review(result, text)
    label = _resolved_document_header_label(result)
    assert "Tanggapan Penuntut Umum terhadap Nota Perlawanan" in label
    assert "Kubu Penuntutan" in label
    lines = _executive_legal_review_lines(result)
    assert any("Tanggapan Penuntut Umum terhadap Nota Perlawanan" in x for x in lines)


def test_bap_report_header_reads_resolved_identity_not_eksepsi_default():
    text = "BERITA ACARA PEMERIKSAAN TERSANGKA. Saya Jaksa Penyidik berdasarkan Surat Perintah Penyidikan telah memeriksa seorang yang dihadapan saya mengaku sebagai tersangka. Diperlihatkan kepada saudara dokumen kredit."
    result = _base(text)
    result["professional_review"] = build_professional_review(result, text)
    label = _resolved_document_header_label(result)
    assert "Berita Acara Pemeriksaan (BAP) / Interogasi Prosedural" in label
    assert "Dokumen Pemeriksaan Resmi" in label
    assert "Nota Pembelaan" not in label


def test_defense_report_header_still_resolves_defense():
    text = "EKSEPSI. Penasehat Hukum Terdakwa memohon agar dakwaan batal demi hukum karena Pengadilan Tipikor tidak berwenang dan terdapat error in persona."
    result = _base(text)
    result["professional_review"] = build_professional_review(result, text)
    label = _resolved_document_header_label(result)
    assert "Nota Pembelaan / Eksepsi Terdakwa" in label
    assert "Kubu Pertahanan" in label
