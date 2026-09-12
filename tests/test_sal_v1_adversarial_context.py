from services.contract_enforcer import LexiCoreContractEnforcer
from services.semantic_admission import build_statement_contract, enrich_source_ledger_with_sal
from services.sal_source_of_truth import build_governed_pools


def _row(text):
    return {"statement": text, "evidence": text, "label": "SOURCE FACT"}


def test_prosecutor_declarative_accusation_preserves_fact_type_with_epistemic_bound():
    header = "KEJAKSAAN NEGERI BLITAR\nTANGGAPAN PENUNTUT UMUM TERHADAP NOTA PERLAWANAN"
    text = "Terdakwa Elya telah melakukan perbuatan melawan hukum dan menyalahgunakan kewenangannya pada tahun 2022."
    rows = enrich_source_ledger_with_sal([_row(text)], domain_contract={"primary_domain":"corruption"}, posture="TANGGAPAN_PENUNTUT_UMUM", raw_document_header=header)
    sal = rows[0]["sal_contract"]
    assert sal["semantic_envelope"]["semantic_type"] == "FACT_ASSERTION"
    assert rows[0]["sal_speaker_role"] == "PROSECUTOR"
    assert rows[0]["sal_position"] == "PROSECUTION"
    assert rows[0]["sal_epistemic_status"] == "UNVERIFIED_PROSECUTION_ALLEGATION"
    assert "Evidence Map" in sal["admission_contract"]["prohibited_routes"]


def test_defense_declarative_rebuttal_preserves_fact_type_with_epistemic_bound():
    header = "EKSEPSI\nPENASEHAT HUKUM TERDAKWA"
    text = "Pengadilan Tindak Pidana Korupsi bukan kewenangan untuk mengadili perkara ini karena terjadi error in persona."
    rows = enrich_source_ledger_with_sal([_row(text)], domain_contract={"primary_domain":"criminal"}, posture="EKSEPSI", raw_document_header=header)
    sal = rows[0]["sal_contract"]
    assert sal["semantic_envelope"]["semantic_type"] == "FACT_ASSERTION"
    assert rows[0]["sal_speaker_role"] == "DEFENSE_COUNSEL"
    assert rows[0]["sal_position"] == "DEFENSE"
    assert rows[0]["sal_epistemic_status"] == "UNVERIFIED_DEFENSE_REBUTTAL"


def test_neutral_document_does_not_demote_observable_fact():
    header = "LAPORAN INTERNAL BANK"
    text = "Direktur menyetujui pencairan kredit pada tanggal 2 Mei 2022."
    rows = enrich_source_ledger_with_sal([_row(text)], domain_contract={"primary_domain":"banking"}, posture="INTERNAL_REPORT", raw_document_header=header)
    assert rows[0]["sal_contract"]["semantic_envelope"]["semantic_type"] == "FACT_ASSERTION"
    assert rows[0]["sal_speaker_role"] == "UNKNOWN"


def test_frozen_schema_shape_is_preserved_after_adversarial_enforcement():
    p = build_statement_contract("Terdakwa telah melakukan perbuatan melawan hukum pada tahun 2022.", index=0, prefix="ADV", domain_contract={"primary_domain":"criminal"}, posture="TANGGAPAN")
    q = LexiCoreContractEnforcer.enforce_adversarial_context(p, "TANGGAPAN PENUNTUT UMUM TERHADAP NOTA PERLAWANAN")
    assert set(q["semantic_envelope"]) == {"semantic_type", "provenance", "modality_temporality", "domain_posture"}
    assert q["semantic_envelope"]["semantic_type"] == "FACT_ASSERTION"
    assert LexiCoreContractEnforcer.adversarial_context_from_payload(q)["epistemic_status"] == "UNVERIFIED_PROSECUTION_ALLEGATION"


def test_governed_pool_carries_binary_viewpoint_ownership():
    header = "KEJAKSAAN NEGERI BLITAR TANGGAPAN PENUNTUT UMUM TERHADAP NOTA PERLAWANAN"
    text = "Terdakwa telah melakukan perbuatan melawan hukum pada tahun 2022."
    rows = enrich_source_ledger_with_sal([_row(text)], domain_contract={"primary_domain":"corruption"}, posture="TANGGAPAN", raw_document_header=header)
    result={"source_ledger": rows, "source_text": text, "domain_contract":{"primary_domain":"corruption"}, "applicable_law": []}
    pools=build_governed_pools(result)
    token=next(iter(pools["route_token_ledger"].values()))
    assert token["speaker_role"] == "PROSECUTOR"
    assert token["position"] == "PROSECUTION"
    assert token["stance"] == "ALLEGATION"


def test_robust_prosecutor_fingerprint_survives_missing_header():
    body = """
    Nota Perlawanan Terdakwa telah kami pelajari.
    Bahwa Penuntut Umum memohon kepada Majelis Hakim untuk menolak seluruh dalil perlawanan.
    Pemeriksaan perkara dilanjutkan dengan agenda pembuktian untuk mendapatkan kepastian hukum.
    """
    identity = LexiCoreContractEnforcer.resolve_document_adversarial_identity(body)
    assert identity["speaker_role"] == "PROSECUTOR"
    assert identity["position"] == "PROSECUTION"
    assert identity["document_posture"] == "Tanggapan Penuntut Umum terhadap Nota Perlawanan"


def test_robust_defense_fingerprint_resolves_eksepsi():
    body = """
    EKSEPSI. Penasehat Hukum Terdakwa memohon agar dakwaan batal demi hukum.
    Pengadilan Tipikor tidak berwenang mengadili dan terdapat error in persona.
    """
    identity = LexiCoreContractEnforcer.resolve_document_adversarial_identity(body)
    assert identity["speaker_role"] == "DEFENSE_COUNSEL"
    assert identity["position"] == "DEFENSE"


def test_fact_type_preserved_but_prosecution_merits_is_epistemically_bound():
    text = "Terdakwa telah melakukan perbuatan melawan hukum dan menyalahgunakan kewenangan pada tahun 2022."
    body = "Penuntut Umum memohon menolak seluruh dalil Nota Perlawanan Terdakwa. " + text
    rows = enrich_source_ledger_with_sal([_row(text)], domain_contract={"primary_domain":"corruption"}, posture="TANGGAPAN", raw_extracted_text=body)
    sal = rows[0]["sal_contract"]
    assert sal["semantic_envelope"]["semantic_type"] == "FACT_ASSERTION"
    assert rows[0]["sal_speaker_role"] == "PROSECUTOR"
    assert rows[0]["sal_epistemic_status"] == "UNVERIFIED_PROSECUTION_ALLEGATION"


def test_defense_chronological_fact_remains_fact_with_owner_bound():
    text = "Direktur menjabat pada tahun 2022 dan rapat berlangsung pada tanggal 2 Mei 2022."
    body = "EKSEPSI Penasehat Hukum Terdakwa. " + text
    rows = enrich_source_ledger_with_sal([_row(text)], domain_contract={"primary_domain":"banking"}, posture="EKSEPSI", raw_extracted_text=body)
    sal = rows[0]["sal_contract"]
    assert sal["semantic_envelope"]["semantic_type"] == "FACT_ASSERTION"
    assert rows[0]["sal_speaker_role"] == "DEFENSE_COUNSEL"
    assert rows[0]["sal_epistemic_status"] == "CHRONOLOGICAL_FACT_REPORTED_BY_DEFENSE"


def test_governed_summary_excludes_unverified_prosecution_allegation():
    from services.sal_source_of_truth import build_governed_pools
    text = "Terdakwa telah melakukan perbuatan melawan hukum dan menyalahgunakan kewenangan pada tahun 2022."
    body = "Penuntut Umum memohon menolak seluruh dalil Nota Perlawanan Terdakwa. " + text
    rows = enrich_source_ledger_with_sal([_row(text)], domain_contract={"primary_domain":"corruption"}, posture="TANGGAPAN", raw_extracted_text=body)
    result = {"source_ledger": rows, "source_text": body, "domain_contract":{"primary_domain":"corruption"}, "applicable_law": []}
    pools = build_governed_pools(result)
    assert text not in pools["summary_fakta_kunci_pool"]


def test_general_orchestrator_corrects_jpu_document_posture_from_body_fingerprint():
    from services.general_case_orchestrator import apply_general_case_orchestration
    body = "Nota Perlawanan Terdakwa telah dipelajari. Penuntut Umum memohon menolak seluruh dalil dan melanjutkan pemeriksaan perkara dengan agenda pembuktian."
    out = apply_general_case_orchestration({"domain_classification":{"ranah_hukum":"PIDANA"}}, body)
    assert out["adversarial_document_identity"]["speaker_role"] == "PROSECUTOR"
    assert out["document_posture_profile"]["document_type"] == "Tanggapan Penuntut Umum terhadap Nota Perlawanan"


def test_bap_fingerprint_resolves_as_neutral_examination_record():
    body = """
    KEJAKSAAN NEGERI BLITAR TINDAK PIDANA KHUSUS
    BERITA ACARA PEMERIKSAAN TERSANGKA
    Pada hari ini telah memeriksa seorang yang dihadapan saya mengaku sebagai tersangka.
    Saya Jaksa Penyidik berdasarkan Surat Perintah Penyidikan.
    Diperlihatkan kepada saudara dokumen perjanjian kredit dan dipertanyakan kepada saudara.
    """
    identity = LexiCoreContractEnforcer.resolve_document_adversarial_identity(body)
    assert identity["speaker_role"] == "INTERROGATOR_AND_SUSPECT"
    assert identity["position"] == "NEUTRAL_RECORD"
    assert identity["document_posture"] == "Berita Acara Pemeriksaan (BAP) / Interogasi Prosedural"
    assert int(identity["bap_score"]) > int(identity["prosecution_score"])


def test_weak_or_tied_fingerprint_never_defaults_to_defense():
    identity = LexiCoreContractEnforcer.resolve_document_adversarial_identity(
        "Dokumen internal mengenai kronologi administrasi kredit dan rapat direksi."
    )
    assert identity["speaker_role"] == "UNKNOWN"
    assert identity["identity_status"] == "UNRESOLVED_SOURCE_OWNERSHIP"


def test_general_orchestrator_projects_bap_document_posture():
    from services.general_case_orchestrator import apply_general_case_orchestration
    body = "BERITA ACARA PEMERIKSAAN TERSANGKA. Saya Jaksa Penyidik berdasarkan Surat Perintah Penyidikan telah memeriksa seorang yang dihadapan saya mengaku sebagai tersangka."
    out = apply_general_case_orchestration({"domain_classification":{"ranah_hukum":"PIDANA"}}, body)
    assert out["adversarial_document_identity"]["speaker_role"] == "INTERROGATOR_AND_SUSPECT"
    assert out["document_posture_profile"]["document_type"] == "Berita Acara Pemeriksaan (BAP) / Interogasi Prosedural"
