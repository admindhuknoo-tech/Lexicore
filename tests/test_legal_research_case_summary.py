from services.case_law_summary import summarize_case_source, summarize_doctrine_source


def test_case_summary_four_mandatory_sections():
    text='''DUDUK PERKARA: Pada 1 Januari 2024 Penggugat mengajukan gugatan terhadap Tergugat mengenai perjanjian.\nPERTIMBANGAN HUKUM: Menimbang bahwa kewajiban yang telah jatuh tempo harus dipenuhi. Menurut Mahkamah, kelalaian setelah somasi merupakan wanprestasi.\nMENGADILI: Mengabulkan gugatan Penggugat untuk sebagian. Menghukum Tergugat memenuhi kewajibannya.'''
    r=summarize_case_source(text)
    assert '1 Januari 2024' in r['chronology']
    assert 'wanprestasi' in r['ratio_decidendi'].lower()
    assert 'Mengabulkan' in r['disposition']
    assert r['legal_rule']
    assert r['professional_verification']=='PENDING'


def test_missing_case_sections_fail_closed():
    r=summarize_case_source('Dokumen singkat ini tidak memuat amar maupun pertimbangan putusan secara lengkap. '*4)
    assert r['disposition'].startswith('TIDAK TERIDENTIFIKASI')
    assert r['legal_rule_status'] in {'UNVERIFIED','INFERRED_FROM_RATIO — PROFESSIONAL VERIFICATION REQUIRED'}


def test_explicit_legal_rule_preferred():
    text='''KRONOLOGI: Sengketa terjadi pada tahun 2024. PERTIMBANGAN HUKUM: Menimbang bahwa syarat formil harus dipenuhi. MENGADILI: Menolak permohonan. KAIDAH HUKUM: Gugatan yang tidak memenuhi syarat formil tidak dapat diterima.'''
    r=summarize_case_source(text)
    assert 'Gugatan' in r['legal_rule']
    assert r['legal_rule_status']=='EXPLICIT_IN_SOURCE'


def test_doctrine_summary_is_secondary_source_shape():
    text=('Menurut doktrin hukum perjanjian, asas itikad baik mengarahkan pelaksanaan hak dan kewajiban. '
          'Penulis berpendapat bahwa penilaian harus memperhatikan kepatutan. '
          'Dengan demikian penerapan klausul tidak boleh dilepaskan dari konteks hubungan hukum. ')*2
    r=summarize_doctrine_source(text)
    assert r['doctrine_topic']
    assert r['doctrine_thesis']
    assert r['doctrine_analysis']
    assert r['professional_verification']=='PENDING'
