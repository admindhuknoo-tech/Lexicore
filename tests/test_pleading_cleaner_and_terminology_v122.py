from extractors.pleading_cleaner import identify_civil_posture, semantic_override, sanitize_strategy
from exporters.common import clean_section_13_chain, sanitize_section_14_text
from services.semantic_admission import classify_semantic_type
from services.document_posture_resolver import resolve_document_posture


def test_repliek_spelling_is_resolved_as_civil_replik():
    text = "REPLIEK PERKARA NOMOR 44/Pdt.G/2026/PN.Kpn. Penggugat mengajukan repliek atas jawaban Para Tergugat."
    assert identify_civil_posture(text)["posture"] == "Replik Perdata"
    resolved = resolve_document_posture({"ranah_hukum": "PERDATA"}, {"source_text": text})
    assert resolved["document_subtype"] == "REPLIK"
    assert resolved["document_type"] == "Replik"


def test_dupliek_spelling_is_resolved_as_civil_duplik():
    text = "DUPLIEK dalam perkara 12/Pdt.G/2026/PN.X atas Replik Penggugat."
    resolved = resolve_document_posture({"ranah_hukum": "PERDATA"}, {"source_text": text})
    assert resolved["document_subtype"] == "DUPLIK"
    assert resolved["document_type"] == "Duplik"


def test_civil_filing_intro_is_metadata_not_key_fact():
    text = "Bersama ini mohon diperkenankan untuk mengajukan Replik atas jawaban Para Tergugat."
    src = {"_semantic_context": "CIVIL_PLEADING"}
    assert semantic_override(text, source_item=src)["override_type"] == "METADATA"
    assert classify_semantic_type(text, src) == "METADATA"


def test_civil_doctrinal_assertion_is_party_argument_not_fact():
    text = "Tentang Exceptio Plurium Litis Consortium, PTSL tidak bisa kita libatkan sebagai pihak dalam perkara ini."
    src = {"_semantic_context": "CIVIL_PLEADING"}
    assert classify_semantic_type(text, src) == "PARTY_ARGUMENT"


def test_same_phrase_outside_civil_context_not_forced():
    text = "Bersama ini mohon diperkenankan hadir."
    assert semantic_override(text, posture="Catatan Konsultasi", corpus="umum")["override_type"] is None


def test_strategy_sanitizer_is_safe_and_non_eval():
    data={"priorities":["Tunjukkan bagian dakwaan yang diserang dan cacat surat dakwaan di Pengadilan Tipikor."], "n": 3}
    out=sanitize_strategy(data, domain="PERDATA")
    assert "dakwaan" not in out["priorities"][0].lower()
    assert "pengadilan tipikor" not in out["priorities"][0].lower()
    assert out["n"] == 3
    assert data["priorities"][0] != out["priorities"][0]


def test_section_13_reader_terms_are_cleaned():
    raw="UJI UNSUR: Not established | counter-evidence | impact | chain cannot support a final conclusion while a required gate or element remains unresolved."
    out=clean_section_13_chain(raw)
    for forbidden in ("Not established", "counter-evidence", "impact", "chain cannot support"):
        assert forbidden.lower() not in out.lower()


def test_section_14_internal_variables_are_hidden():
    raw="Sistem mendeteksi ranah_hukum=PERDATA, posisi_pengguna=TIDAK_TERIDENTIFIKASI dengan keyakinan rendah."
    out=sanitize_section_14_text(raw)
    assert "ranah_hukum=" not in out
    assert "posisi_pengguna=" not in out
    assert "kategori perkara: Perdata" in out
    assert "kedudukan pengguna belum teridentifikasi" in out
