from exporters.common import _case_export_sections, prepare_case_export_for_reader


def _sample_bap_payload():
    return {
        'title': 'Case Analysis',
        'input_type': 'document',
        'filename': 'BAP_TERSANGKA.pdf',
        'professional_verification': 'PENDING',
        'source_text': (
            'BERITA ACARA PEMERIKSAAN TERSANGKA. '
            'Nama lengkap Drs. CONTOH TERSANGKA. '
            'Pada saat menjabat Direktur Utama BPR Kota Contoh, tersangka menerangkan proses pemberian kredit kepada Debitur A. '
            'Diperlihatkan Perjanjian Kredit Nomor 101 tanggal 27 September 2022 yang ditandatangani selaku Direktur Utama. '
            'Penyidik menyebut Pasal 2 ayat (1), Pasal 3, dan Pasal 18 Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi '
            'sebagaimana diubah dengan Undang-Undang Nomor 20 Tahun 2001. '
        ),
        'document_reading': {'status':'COMPLETE','segments_read':1,'segments_total':1,'characters':1200},
        'analysis_provenance': {'mode':'LOCAL_DETERMINISTIC'},
        'professional_review': {
            'review_status':'VERIFICATION_REQUIRED',
            'document_structure': {
                'resolved_document_identity': {
                    'document_posture':'Berita Acara Pemeriksaan (BAP) / Interogasi Prosedural',
                    'speaker_role':'INTERROGATOR_AND_SUSPECT',
                }
            },
            'findings':[],
        },
        'applicable_law': [],
    }


def test_context_section_adds_duduk_perkara_articles_instruments_and_bap_caveat():
    meta, sections = _case_export_sections(_sample_bap_payload())
    _, reader_sections = prepare_case_export_for_reader(meta, sections)
    mapping = {heading: lines for heading, lines in reader_sections}
    heading = 'Konteks Perkara, Duduk Perkara, dan Sumber'
    assert heading in mapping
    text = '\n'.join(mapping[heading])
    assert 'Duduk perkara ringkas dari sumber:' in text
    assert 'Pasal yang disebut dalam sumber:' in text
    assert 'Pasal 2 ayat (1)' in text
    assert 'Pasal 3' in text
    assert 'Undang-undang/instrumen yang disebut dalam sumber:' in text
    assert 'Undang-Undang Nomor 31 Tahun 1999' in text
    assert 'sumber yang dianalisis adalah BAP/pemeriksaan tersangka' in text
    assert 'Tuntutan atau lama pidana yang diminta penuntut: tidak teridentifikasi' in text


def test_wrapper_analisis_terperinci_removed_but_detailed_audit_not_removed():
    payload = _sample_bap_payload()
    payload['case_working_paper'] = {
        'working_paper_percentage': {'percentage': 10, 'confidence': 'LOW'},
        'professional_review': {},
    }
    meta, sections = _case_export_sections(payload)
    _, reader_sections = prepare_case_export_for_reader(meta, sections)
    headings = [h for h, _ in reader_sections]
    assert 'Analisis Terperinci' not in headings
    # Audit is produced when professional_review exists in the working paper.
    # It must remain an independent substantive section, not be merged with a wrapper.
    assert all('Working Paper Terperinci' != h for h in headings)


def test_no_indictment_or_sentence_is_invented_from_bap():
    meta, sections = _case_export_sections(_sample_bap_payload())
    _, reader_sections = prepare_case_export_for_reader(meta, sections)
    text = '\n'.join(line for h, lines in reader_sections if h == 'Konteks Perkara, Duduk Perkara, dan Sumber' for line in lines)
    assert 'pidana penjara selama' not in text.lower()
    assert 'Surat dakwaan dan tuntutan pidana tidak boleh dianggap tersedia hanya dari dokumen ini.' in text
