import json
from pathlib import Path


def test_debug_logging_disabled_is_noop(monkeypatch, tmp_path):
    import services.document_ocr as ocr
    out = tmp_path / "ocr_debug.jsonl"
    monkeypatch.delenv("LEXICORE_OCR_DEBUG", raising=False)
    monkeypatch.setenv("LEXICORE_OCR_DEBUG_FILE", str(out))
    ocr._log_ocr_debug("TEST_EVENT", page=1)
    assert not out.exists()


def test_debug_logging_enabled_writes_jsonl(monkeypatch, tmp_path):
    import services.document_ocr as ocr
    out = tmp_path / "ocr_debug.jsonl"
    monkeypatch.setenv("LEXICORE_OCR_DEBUG", "1")
    monkeypatch.setenv("LEXICORE_OCR_DEBUG_FILE", str(out))
    ocr._log_ocr_debug("TEST_EVENT", page=2, engine="rapid", elapsed=0.25, text_len=12)
    row = json.loads(out.read_text(encoding="utf-8").strip())
    assert row["event"] == "TEST_EVENT"
    assert row["page"] == 2
    assert row["engine"] == "rapid"
    assert row["text_len"] == 12
