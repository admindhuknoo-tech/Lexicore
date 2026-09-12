from exporters.common import (
    LexiCoreCivilPresentationSanitizer,
    _case_export_sections,
    prepare_case_export_for_reader,
)


def _payload():
    return {
        'title': 'Case Analysis',
        'input_type': 'document',
        'filename': 'BAP_TERSANGKA.pdf',
        'professional_verification': 'PENDING',
        'source_text': (
            'BERITA ACARA PEMERIKSAAN TERSANGKA. '
            'Pemberian Kredityang diberikankepada Debitur A ditandatanganioleh DirekturUtama. '
            'Penyidik menyebut Pasal 3 Undang-Undang Nomor 31 Tahun 1999.'
        ),
        'document_reading': {'status': 'COMPLETE', 'segments_read': 1, 'segments_total': 1, 'characters': 500},
        'analysis_provenance': {'mode': 'LOCAL_DETERMINISTIC'},
        'case_working_paper': {
            'working_paper_percentage': {'percentage': 25, 'confidence': 'LOW'},
            'evidence_map': {
                'legal_basis': {'citation': 'KUHAP', 'note': 'uji bukti'},
                'rows': [],
            },
            'legal_construction': {'synthesis': 'Analisis awal.', 'chains': []},
            'action_plan': [],
        },
        'professional_review': {'review_status': 'VERIFICATION_REQUIRED', 'findings': []},
    }


def test_reader_section_order_context_first_and_review_after_evidence_map():
    meta, sections = _case_export_sections(_payload())
    _, reader_sections = prepare_case_export_for_reader(meta, sections)
    headings = [h for h, _ in reader_sections]
    assert headings[0] == 'Konteks Perkara, Duduk Perkara, dan Sumber'
    evidence_idx = headings.index('Pemetaan Bukti')
    review_idx = headings.index('Ringkasan Analisis Hukum')
    assert review_idx == evidence_idx + 1


def test_joined_word_repairs_are_presentation_only_and_bounded():
    raw = (
        'Pada hariini tanggal27 September, Kredityang diberikankepada debitur '
        'ditandatanganioleh DirekturUtama dan PenyidikKejaksaan Negeri.'
    )
    cleaned = LexiCoreCivilPresentationSanitizer.clean_text(raw)
    assert 'hari ini' in cleaned
    assert 'tanggal 27' in cleaned
    assert 'Kredit yang' in cleaned
    assert 'diberikan kepada' in cleaned
    assert 'ditandatangani oleh' in cleaned
    assert 'Direktur Utama' in cleaned
    assert 'Penyidik Kejaksaan' in cleaned


def test_non_target_legal_tokens_are_not_rewritten_by_typo_repair():
    raw = 'Pasal 3 jo Pasal 18 UU Nomor 31 Tahun 1999; tempus delicti.'
    assert LexiCoreCivilPresentationSanitizer.clean_text(raw) == raw
