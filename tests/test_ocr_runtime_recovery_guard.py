import copy
import os
from pathlib import Path

import services.document_ocr as ocr


def _diag(pages_ocr, total=37):
    return {
        'pages_total': total,
        'pages_native': 0,
        'pages_ocr': pages_ocr,
        'pages_failed': total-pages_ocr,
        'coverage_ratio': round(pages_ocr/total, 4),
        'warnings': [],
        'mode': 'OCR_FALLBACK',
        'authoritative_for_analysis': pages_ocr/total >= 0.20,
    }


def test_adaptive_timeouts_are_not_regression_level_1_to_5_seconds():
    rapid = ocr._adaptive_engine_timeout(engine='rapid', remaining_document=180, remaining_pages=37)
    tess = ocr._adaptive_engine_timeout(engine='tesseract', remaining_document=170, remaining_pages=37)
    assert rapid >= 8
    assert rapid <= 12
    assert tess >= 12
    assert tess <= 20


def test_monotonic_guard_restores_previous_better_extraction(tmp_path, monkeypatch):
    monkeypatch.setenv('LEXICORE_OCR_SEVERE_COVERAGE_FLOOR', '0.20')
    f = tmp_path / 'same.pdf'
    f.write_bytes(b'same document bytes')
    ocr._OCR_BEST_CACHE.clear()

    best_text, best_diag = ocr._apply_monotonic_coverage_guard(str(f), 'BEST TEXT', _diag(30))
    assert best_text == 'BEST TEXT'
    assert best_diag['coverage_guard_status'] == 'OCR_FIRST_OBSERVATION'
    assert best_diag['authoritative_for_analysis'] is True

    restored_text, restored_diag = ocr._apply_monotonic_coverage_guard(str(f), 'BAD TEXT', _diag(1))
    assert restored_text == 'BEST TEXT'
    assert restored_diag['coverage_guard_status'] == 'OCR_REGRESSED_PREVIOUS_BEST_RESTORED'
    assert restored_diag['attempt_coverage_ratio'] == round(1/37, 4)
    assert restored_diag['previous_best_coverage_ratio'] == round(30/37, 4)
    assert restored_diag['authoritative_for_analysis'] is True


def test_first_observation_below_20_percent_is_diagnostic_only(tmp_path, monkeypatch):
    monkeypatch.setenv('LEXICORE_OCR_SEVERE_COVERAGE_FLOOR', '0.20')
    f = tmp_path / 'low.pdf'
    f.write_bytes(b'low coverage document')
    ocr._OCR_BEST_CACHE.clear()
    text, diag = ocr._apply_monotonic_coverage_guard(str(f), 'PARTIAL', _diag(1))
    assert text == 'PARTIAL'
    assert diag['authoritative_for_analysis'] is False
    assert diag['coverage_guard_status'] == 'OCR_FIRST_OBSERVATION'


def test_previous_lower_extraction_is_replaced_by_improvement(tmp_path):
    f = tmp_path / 'improve.pdf'
    f.write_bytes(b'improve document')
    ocr._OCR_BEST_CACHE.clear()
    _, d1 = ocr._apply_monotonic_coverage_guard(str(f), 'OLD', _diag(7))
    t2, d2 = ocr._apply_monotonic_coverage_guard(str(f), 'NEW', _diag(30))
    assert t2 == 'NEW'
    assert d2['coverage_guard_status'] == 'OCR_IMPROVED_OR_EQUAL'
    assert d2['previous_best_coverage_ratio'] == round(7/37, 4)


def test_circuit_failure_threshold_defaults_to_three(monkeypatch):
    monkeypatch.delenv('LEXICORE_RAPIDOCR_CIRCUIT_FAILURES', raising=False)
    # Contract is deliberately source-visible and env-controlled; a single
    # timeout must not trip the circuit anymore.
    source = Path(ocr.__file__).read_text(encoding='utf-8')
    assert 'LEXICORE_RAPIDOCR_CIRCUIT_FAILURES", "3"' in source
    assert '_RAPID_CONSECUTIVE_TIMEOUTS >= threshold' in source


def _reset_rapid_runtime_state():
    with ocr._RAPID_STATE_LOCK:
        ocr._RAPID_CALL_INFLIGHT = False
        ocr._RAPID_CIRCUIT_OPEN = False
        ocr._RAPID_TIMEOUT_COUNT = 0
        ocr._RAPID_CONSECUTIVE_TIMEOUTS = 0
        ocr._RAPID_CIRCUIT_OPENED_AT = None


def test_embedded_ocr_timeout_returns_control_and_allows_fallback(monkeypatch):
    """One RapidOCR timeout falls back but must not open the circuit."""
    import time

    _reset_rapid_runtime_state()
    monkeypatch.setenv('LEXICORE_RAPIDOCR_CIRCUIT_FAILURES', '3')
    monkeypatch.setattr(ocr, '_embedded_timeout_seconds', lambda: 0.01)
    monkeypatch.setattr(
        ocr,
        '_adaptive_engine_timeout',
        lambda **kwargs: 0.01,
    )

    def slow_core(_image):
        time.sleep(0.03)
        return ('late text', 0.9)

    monkeypatch.setattr(ocr, '_ocr_embedded_core', slow_core)
    monkeypatch.setattr(ocr, '_ocr_tesseract_optional', lambda image, diagnostics: 'fallback text')

    diagnostics = ocr.OCRDiagnostics()
    result = ocr._ocr_pil_image(object(), diagnostics)

    assert result == 'fallback text'
    assert ocr._RAPID_TIMEOUT_COUNT == 1
    assert ocr._RAPID_CONSECUTIVE_TIMEOUTS == 1
    assert ocr._RAPID_CIRCUIT_OPEN is False

    # Allow the daemon worker to leave the in-flight state before the next test.
    time.sleep(0.04)
    _reset_rapid_runtime_state()


def test_rapid_circuit_opens_only_after_consecutive_timeout_threshold(monkeypatch):
    """Circuit opens after the configured consecutive timeout threshold, not before."""
    import time

    _reset_rapid_runtime_state()
    monkeypatch.setenv('LEXICORE_RAPIDOCR_CIRCUIT_FAILURES', '3')
    monkeypatch.setattr(ocr, '_embedded_timeout_seconds', lambda: 0.01)
    monkeypatch.setattr(ocr, '_adaptive_engine_timeout', lambda **kwargs: 0.01)

    calls = {'core': 0}

    def slow_core(_image):
        calls['core'] += 1
        time.sleep(0.03)
        return ('late text', 0.9)

    monkeypatch.setattr(ocr, '_ocr_embedded_core', slow_core)
    monkeypatch.setattr(ocr, '_ocr_tesseract_optional', lambda image, diagnostics: 'fallback text')

    diagnostics = ocr.OCRDiagnostics()

    for expected in (1, 2):
        assert ocr._ocr_pil_image(object(), diagnostics) == 'fallback text'
        assert ocr._RAPID_CONSECUTIVE_TIMEOUTS == expected
        assert ocr._RAPID_CIRCUIT_OPEN is False
        time.sleep(0.04)

    assert ocr._ocr_pil_image(object(), diagnostics) == 'fallback text'
    assert ocr._RAPID_CONSECUTIVE_TIMEOUTS == 3
    assert ocr._RAPID_CIRCUIT_OPEN is True
    time.sleep(0.04)

    # While open and before cooldown, RapidOCR must be skipped and fallback used.
    before = calls['core']
    assert ocr._ocr_pil_image(object(), diagnostics) == 'fallback text'
    assert calls['core'] == before

    _reset_rapid_runtime_state()


def test_successful_rapid_ocr_resets_consecutive_timeout_counter(monkeypatch):
    """A successful RapidOCR page resets the consecutive failure counter."""
    _reset_rapid_runtime_state()
    ocr._RAPID_TIMEOUT_COUNT = 2
    ocr._RAPID_CONSECUTIVE_TIMEOUTS = 2

    monkeypatch.setattr(ocr, '_embedded_timeout_seconds', lambda: 0.05)
    monkeypatch.setattr(ocr, '_adaptive_engine_timeout', lambda **kwargs: 0.05)
    monkeypatch.setattr(ocr, '_ocr_embedded_core', lambda image: ('rapid success', 0.95))

    diagnostics = ocr.OCRDiagnostics()
    result = ocr._ocr_pil_image(object(), diagnostics)

    assert result == 'rapid success'
    # Total timeout telemetry is cumulative, but the *consecutive* breaker state resets.
    assert ocr._RAPID_TIMEOUT_COUNT == 2
    assert ocr._RAPID_CONSECUTIVE_TIMEOUTS == 0
    assert ocr._RAPID_CIRCUIT_OPEN is False

    _reset_rapid_runtime_state()
