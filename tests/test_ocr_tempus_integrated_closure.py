from services import document_ocr as ocr
from services.material_tempus_extractor import select_material_tempus, extract_material_tempus_candidates


def test_ocr_budget_planning_slice_is_fair_but_not_a_hard_engine_timeout():
    # Planning still distributes the document budget, but RUNTIME RECOVERY no
    # longer turns a 2-6 second planning slice into a hard OCR deadline.
    slice_seconds = ocr._page_time_slice(180.0, 37)
    assert 3.0 <= slice_seconds < 10.0
    assert ocr._adaptive_engine_timeout(engine='rapid', remaining_document=180.0, remaining_pages=37) >= 8.0
    assert ocr._adaptive_engine_timeout(engine='tesseract', remaining_document=170.0, remaining_pages=37) >= 12.0


def test_ocr_budget_planning_slice_increases_as_remaining_pages_drop():
    early = ocr._page_time_slice(120.0, 30)
    late = ocr._page_time_slice(60.0, 5)
    assert early <= late
    assert late <= 20.0


def test_tempus_admin_ethics_resignation_date_is_material_candidate():
    text = (
        'Teradu mengundurkan diri dari kepengurusan organisasi pada tanggal 16 Januari 2018. '
        'Pengaduan kemudian diajukan pada tanggal 3 April 2021.'
    )
    selected = select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_CANDIDATE'
    assert selected['value'] == '2018-01-16'
    assert selected['selection_basis'] == 'UNIQUE_MATERIAL_EVENT_DATE'
    # Extraction never self-promotes to legal tempus verification.
    assert 'verified' not in selected


def test_tempus_admin_ethics_multiple_material_status_dates_fail_closed():
    text = (
        'Teradu mengundurkan diri pada tanggal 16 Januari 2018. '
        'Teradu kemudian ditetapkan sebagai Anggota KPU pada tanggal 11 Juni 2019.'
    )
    selected = select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_AMBIGUOUS'
    assert selected['value'] is None
    assert selected['selection_basis'] == 'MULTIPLE_COMPETING_MATERIAL_EVENT_DATES'


def test_tempus_procedural_complaint_date_is_not_material_without_event_nexus():
    text = (
        'Nomor Pengaduan 157-P/L-DKPP/VII/2021. '
        'Pengaduan diajukan pada tanggal 3 April 2021 dan sidang dilaksanakan tanggal 20 Oktober 2021.'
    )
    selected = select_material_tempus(text)
    assert selected['status'] == 'MATERIAL_TEMPUS_UNKNOWN'
    assert selected['value'] is None


def test_tempus_candidates_keep_provenance_for_professional_review():
    rows = extract_material_tempus_candidates(
        'Menerima pengunduran diri dan memberhentikan Teradu sejak tanggal 29 Desember 2017.'
    )
    assert rows
    material = [r for r in rows if r['role'] == 'material_event']
    assert material
    assert material[0]['value'] == '2017-12-29'
    assert 'context' in material[0]
    assert 'reasons' in material[0]


def test_ocr_manual_review_gate_tracks_80_percent_coverage(monkeypatch):
    monkeypatch.setenv('LEXICORE_OCR_MIN_ACCEPTABLE_COVERAGE', '0.80')
    low = ocr.OCRDiagnostics(pages_total=10, pages_ocr=7, pages_failed=3).to_dict()
    high = ocr.OCRDiagnostics(pages_total=10, pages_ocr=8, pages_failed=2).to_dict()
    assert low['manual_review_required'] is True
    assert high['manual_review_required'] is False
