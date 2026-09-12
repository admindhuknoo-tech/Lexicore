from exporters.common import prepare_case_export_for_reader
from services.document_posture_resolver import resolve_document_posture
from services.material_tempus_extractor import select_material_tempus
from services.case_working_paper import _legal_construction


def test_explicit_response_header_outranks_repeated_penetapan_body_terms():
    text=(
        'KOMISI PEMILIHAN UMUM KOTA BATU JAWABAN ATAS LAPORAN DUGAAN PELANGGARAN KODE ETIK '
        'NOMOR PENGADUAN 157-P/L-DKPP/VII/2021. Dalam Pokok Aduan: Teradu menolak seluruh dalil. '
        'Surat Keputusan penetapan anggota. Penetapan divisi. Penetapan susunan personalia. '
        'Berdasarkan putusan lain yang dikutip sebagai referensi.'
    )
    out=resolve_document_posture(
        {'ranah_hukum':'ETIK_ADMINISTRATIF','posisi_pengguna':'TERADU'},
        {'source_text':text},
    )
    assert out['posture']=='RESPONSE_TO_COMPLAINT'
    assert out['document_type']=='Jawaban atas Pengaduan Etik'
    assert out.get('basis')=='EXPLICIT_DOCUMENT_HEADER'


def test_lifecycle_date_can_anchor_tempus_without_domain_specific_rule():
    text=(
        'Pihak resmi mengundurkan diri dan diberhentikan dengan hormat sejak tanggal 16 Januari 2018. '
        'Kemudian ditetapkan sebagai pejabat berdasarkan keputusan tanggal 11 Juni 2019. '
        'Pengaduan diajukan pada tanggal 5 Maret 2021.'
    )
    out=select_material_tempus(text)
    assert out['status']=='MATERIAL_TEMPUS_CANDIDATE'
    assert out['value']=='2018-01-16'


def test_response_working_paper_synthesis_does_not_reuse_criminal_template():
    result={
        'source_text':'JAWABAN ATAS LAPORAN DUGAAN PELANGGARAN KODE ETIK. Dalam Pokok Aduan Teradu membantah dalil.',
        'domain_classification':{'ranah_hukum':'ETIK_ADMINISTRATIF','posisi_pengguna':'TERADU'},
        'document_posture_profile':{'posture':'RESPONSE_TO_COMPLAINT'},
        'legal_analysis':'Karena dokumen memuat eksepsi, pisahkan keberatan formil terhadap dakwaan.',
        'legal_issues':[], 'source_ledger':[], 'applicable_law':[], 'case_regulatory_snapshot':{},
    }
    out=_legal_construction(result,{})
    assert 'jawaban terhadap aduan' in out['synthesis'].lower()
    assert 'dakwaan' not in out['synthesis'].lower()
    assert 'eksepsi' not in out['synthesis'].lower()


def test_reader_export_hides_internal_codes_without_mutating_canonical_contract():
    meta=[
        ('Metode analisis','Analisis lokal deterministik'),
        ('Pembacaan dokumen','OCR_FALLBACK - teks asli 0 hlm - OCR 37 hlm - belum terbaca 0 hlm'),
        ('OCR','tesseract_fallback / ind+eng - 57723 karakter OCR - LOCAL FALLBACK'),
        ('OCR Diagnostics','Embedded OCR timeout setelah 12 detik; circuit breaker aktif.'),
    ]
    sections=[
        ('Element-by-Element Analysis',[
            'ISSUE 1: Isu contoh | Status mapping: DISPUTED | Kesimpulan hukum: VERIFICATION_REQUIRED',
            'ELEMENT: Unsur contoh | Mapping confidence: 79%',
            'SUPPORT #2: Bukti A',
            'COUNTER #3: Bukti B',
        ]),
        ('Pleading Strategy',['Output readiness: WORKING_DRAFT_ONLY','- SHOW CORRECTIVE ACTION']),
    ]
    clean_meta, clean_sections=prepare_case_export_for_reader(meta,sections)
    text='\n'.join([f'{k}: {v}' for k,v in clean_meta] + [h+'\n'+'\n'.join(lines) for h,lines in clean_sections])
    assert 'OCR Diagnostics' not in text
    assert 'OCR_FALLBACK' not in text
    assert 'LOCAL FALLBACK' not in text
    assert 'VERIFICATION_REQUIRED' not in text
    assert 'WORKING_DRAFT_ONLY' not in text
    assert 'ISSUE 1' not in text
    assert 'ELEMENT:' not in text
    assert 'SUPPORT #' not in text
    assert 'COUNTER #' not in text
    assert 'Analisis Unsur Hukum' in text
    assert 'ISU 1:' in text
    assert 'UNSUR:' in text
    assert 'BUKTI PENDUKUNG #2:' in text
    assert 'BUKTI KONTRA #3:' in text
