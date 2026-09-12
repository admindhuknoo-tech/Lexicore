import os
import services.document_ocr as ocr


def test_adaptive_global_budget_for_37_scan_pages(monkeypatch):
    monkeypatch.delenv('LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS', raising=False)
    assert ocr._ocr_total_timeout_seconds(37) == 356.0


def test_adaptive_global_budget_has_360_cap(monkeypatch):
    monkeypatch.delenv('LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS', raising=False)
    assert ocr._ocr_total_timeout_seconds(100) == 360.0


def test_explicit_global_budget_override_is_respected(monkeypatch):
    monkeypatch.setenv('LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS', '240')
    assert ocr._ocr_total_timeout_seconds(37) == 240.0


def test_first_pass_can_disable_tesseract(monkeypatch):
    monkeypatch.setattr(ocr, '_ocr_embedded', lambda image, diagnostics: '')
    called = {'tess': 0}
    def tess(image, diagnostics):
        called['tess'] += 1
        return 'fallback'
    monkeypatch.setattr(ocr, '_ocr_tesseract_optional', tess)
    d = ocr.OCRDiagnostics()
    assert ocr._ocr_pil_image(object(), d, allow_tesseract=False) == ''
    assert called['tess'] == 0
    assert ocr._ocr_pil_image(object(), d, allow_tesseract=True) == 'fallback'
    assert called['tess'] == 1
