from extractors.bap_noise_cleaner import classify_bap_noise, semantic_override
from services.semantic_admission import classify_semantic_type
from services.regulatory_retrieval import evaluate_law_weight_policy, load_law_weight_config


def _domains(*ids):
    return [{"id":x,"role":"PRIMARY" if i == 0 else "SECONDARY"} for i,x in enumerate(ids)]


def test_bap_question_is_question_not_fact():
    decision=classify_bap_noise(
        "Apakah sekarang Tersangka dalam keadaan sehat jasmani dan rohani serta bersedia memberikan keterangan yang benar ?",
        bap_context=True,
    )
    assert decision["override_type"] == "QUESTION"


def test_bap_procedural_right_fragment_is_normative_not_fact():
    text="Mengusahakan dan mengajukan Saksi dan/atau orang yang memiliki keahlian guna memberikan keterangan."
    decision=classify_bap_noise(text,bap_context=True)
    assert decision["override_type"] == "LAW_CITATION"
    assert classify_semantic_type(text,{"_semantic_context":"BAP_INTERROGATION"}) == "LAW_CITATION"


def test_bap_contractual_obligation_fragment_is_normative_not_fact():
    text="selama 36 (tigapuluh enam) bulan, debitur wajib melakukan pembayaran"
    assert classify_semantic_type(text,{"_semantic_context":"BAP_INTERROGATION"}) == "LAW_CITATION"


def test_bap_concrete_completed_event_is_not_overridden():
    text="Pada tanggal 27 September 2022 debitur telah menandatangani perjanjian kredit."
    decision=classify_bap_noise(text,bap_context=True)
    assert decision["override_type"] is None


def test_non_bap_same_phrase_does_not_activate_cleaner():
    decision=semantic_override(
        "selama 36 bulan debitur wajib melakukan pembayaran",
        posture="Catatan Konsultasi",
        corpus="perjanjian biasa",
    )
    assert decision["override_type"] is None


def test_kpk_employee_performance_regulation_rejected_for_tipikor_case():
    cfg=load_law_weight_config()
    row={
        "title":"Perubahan Atas Peraturan Komisi Pemberantasan Korupsi Nomor 10 Tahun 2010 Tentang Tata Cara Penilaian Kinerja Individu Penasihat dan Pegawai",
        "query":"Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
    }
    decision=evaluate_law_weight_policy(row,_domains("corruption","financial_services","criminal"),cfg)
    assert decision["status"] == "REJECTED_SUBJECT_MATTER_UNPROVEN"
    assert decision["disqualifying_hits"]


def test_tipikor_statute_title_has_positive_nexus():
    row={
        "title":"Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "query":"Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
    }
    decision=evaluate_law_weight_policy(row,_domains("corruption","criminal"))
    assert decision["status"] == "POSITIVE_NEXUS_VERIFIED"
    assert decision["positive_proof"] is True


def test_banking_law_has_positive_nexus_for_bpr_case():
    row={
        "title":"Undang-Undang Nomor 10 Tahun 1998 tentang Perubahan atas Undang-Undang Nomor 7 Tahun 1992 tentang Perbankan",
        "query":"Undang-Undang Nomor 10 Tahun 1998 tentang Perubahan atas Undang-Undang Nomor 7 Tahun 1992 tentang Perbankan",
    }
    decision=evaluate_law_weight_policy(row,_domains("financial_services","corruption"))
    assert decision["status"] == "POSITIVE_NEXUS_VERIFIED"
