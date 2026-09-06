"""Portable OCR support for scanned legal documents.

LexiCore OCR policy (v1.3.10):
- native PDF text first,
- OCR only weak/empty pages,
- embedded RapidOCR/ONNX is the primary OCR engine,
- no OS-level Tesseract installation is required,
- optional Tesseract fallback remains supported when explicitly available,
- all OCR runs on the LexiCore host; uploaded document bytes are not sent to a cloud OCR service.

This design is suitable when LexiCore is deployed on a server/container and accessed
from a phone/tablet/browser: the client only uploads the document, while OCR executes
inside the LexiCore application runtime.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import queue
import threading
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


_RAPID_ENGINE = None
_RAPID_ENGINE_ERROR: Optional[str] = None
_RAPID_STATE_LOCK = threading.Lock()
_RAPID_CALL_INFLIGHT = False
_RAPID_CIRCUIT_OPEN = False
_RAPID_TIMEOUT_COUNT = 0
_OCR_BUDGET_LOCAL = threading.local()


@dataclass
class OCRDiagnostics:
    enabled: bool = True
    available: bool = False
    engine: str = "embedded_rapidocr"
    engine_chain: List[str] = None
    portable: bool = True
    language: str = "multilingual_latin"
    mode: str = "NONE"
    pages_total: int = 0
    pages_native: int = 0
    pages_ocr: int = 0
    pages_failed: int = 0
    characters_native: int = 0
    characters_ocr: int = 0
    average_confidence: Optional[float] = None
    tesseract_cmd: Optional[str] = None
    warnings: List[str] = None
    total_timeout_seconds: Optional[float] = None
    total_timeout_exceeded: bool = False
    elapsed_ocr_seconds: Optional[float] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.engine_chain is None:
            self.engine_chain = ["embedded_rapidocr"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clean_text(text: str) -> str:
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _meaningful_chars(text: str) -> int:
    return len(re.sub(r"[^A-Za-zÀ-ÿ0-9]", "", text or ""))


def _native_text_is_useful(text: str, threshold: int = 80) -> bool:
    cleaned = _clean_text(text)
    if _meaningful_chars(cleaned) < threshold:
        return False
    words = re.findall(r"\b[\wÀ-ÿ]{2,}\b", cleaned, flags=re.UNICODE)
    return len(words) >= 12


def embedded_ocr_available() -> bool:
    """Cheap capability check; does not initialize ONNX models."""
    required = ("rapidocr", "onnxruntime", "numpy", "PIL", "pymupdf")
    return all(importlib.util.find_spec(name) is not None for name in required)


def _get_rapidocr_engine():
    """Lazy-load the embedded OCR engine once per process."""
    global _RAPID_ENGINE, _RAPID_ENGINE_ERROR
    if _RAPID_ENGINE is not None:
        return _RAPID_ENGINE
    if _RAPID_ENGINE_ERROR:
        raise RuntimeError(_RAPID_ENGINE_ERROR)
    try:
        from rapidocr import RapidOCR
        _RAPID_ENGINE = RapidOCR()
        return _RAPID_ENGINE
    except Exception as exc:
        _RAPID_ENGINE_ERROR = f"Embedded RapidOCR gagal diinisialisasi: {exc}"
        raise RuntimeError(_RAPID_ENGINE_ERROR) from exc


def _prepare_image(image):
    """Light preprocessing for photographed/scanned legal pleadings."""
    from PIL import ImageOps, ImageEnhance

    image = image.convert("L")
    max_dim = int(os.environ.get("LEXICORE_OCR_MAX_IMAGE_DIM", "4200") or 4200)
    if max(image.size) > max_dim:
        ratio = max_dim / float(max(image.size))
        image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))))
    image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageEnhance.Sharpness(image).enhance(1.35)
    return image.convert("RGB")


def _box_xy(box) -> Tuple[float, float, float]:
    """Return top-y, left-x and approximate line height from a RapidOCR polygon."""
    try:
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        return min(ys), min(xs), max(1.0, max(ys) - min(ys))
    except Exception:
        return 0.0, 0.0, 12.0


def _rapidocr_result_to_text(result, min_confidence: float) -> Tuple[str, Optional[float]]:
    """Normalize RapidOCR result into stable legal-document reading order."""
    if not result:
        return "", None
    rows = []
    scores: List[float] = []
    for item in result:
        try:
            box, text, score = item[0], str(item[1]).strip(), float(item[2])
        except Exception:
            continue
        if not text or score < min_confidence:
            continue
        y, x, h = _box_xy(box)
        rows.append((y, x, h, text, score))
        scores.append(score)
    if not rows:
        return "", None

    rows.sort(key=lambda r: (r[0], r[1]))
    # Group items that occupy the same visual line. This preserves two-part headings
    # without concatenating unrelated paragraphs.
    lines: List[List[Tuple[float, float, float, str, float]]] = []
    for row in rows:
        if not lines:
            lines.append([row]); continue
        prev_y = sum(x[0] for x in lines[-1]) / len(lines[-1])
        avg_h = sum(x[2] for x in lines[-1]) / len(lines[-1])
        if abs(row[0] - prev_y) <= max(7.0, avg_h * 0.55):
            lines[-1].append(row)
        else:
            lines.append([row])
    text_lines = []
    for line in lines:
        line.sort(key=lambda r: r[1])
        text_lines.append(" ".join(r[3] for r in line).strip())
    avg = sum(scores) / len(scores) if scores else None
    return _clean_text("\n".join(text_lines)), avg


def _ocr_total_timeout_seconds() -> float:
    """Wall-clock OCR budget for one document.

    This is separate from the per-engine timeout.  It prevents a long scanned
    PDF from consuming one per-page timeout repeatedly and holding the request
    for many minutes.  The default is 180 seconds and can be overridden with
    LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS.
    """
    raw = os.environ.get("LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS", "180")
    try:
        return max(5.0, float(raw or 180))
    except Exception:
        return 180.0


def _set_ocr_budget(deadline: Optional[float]) -> None:
    _OCR_BUDGET_LOCAL.deadline = deadline


def _remaining_ocr_budget() -> Optional[float]:
    deadline = getattr(_OCR_BUDGET_LOCAL, "deadline", None)
    if deadline is None:
        return None
    return max(0.0, float(deadline) - time.monotonic())


def _embedded_timeout_seconds() -> float:
    """Hard wall-clock budget for one embedded OCR attempt.

    RapidOCR/ONNX does not expose a portable inference timeout.  The OCR call
    therefore runs in a daemon thread and the request thread waits only for
    this bounded interval.  A timed-out embedded engine is circuit-broken for
    the remainder of the process so repeated pages cannot accumulate stuck
    ONNX calls; the normal Tesseract fallback remains available.
    """
    raw = os.environ.get("LEXICORE_EMBEDDED_OCR_TIMEOUT_SECONDS")
    if raw is None:
        raw = os.environ.get("LEXICORE_OCR_TIMEOUT_SECONDS", "45")
    try:
        return max(0.25, float(raw or 45))
    except Exception:
        return 45.0


def _ocr_embedded_core(image) -> Tuple[str, Optional[float]]:
    """Execute the potentially blocking RapidOCR/ONNX work without mutating diagnostics."""
    import numpy as np
    prepared = _prepare_image(image)
    arr = np.asarray(prepared)
    engine = _get_rapidocr_engine()
    result = engine(arr)
    min_conf = float(os.environ.get("LEXICORE_OCR_MIN_CONFIDENCE", "0.45") or 0.45)
    # RapidOCR >=2 returns RapidOCROutput with boxes/txts/scores.
    # Keep compatibility with the older tuple/list result shape.
    if hasattr(result, "boxes") and hasattr(result, "txts") and hasattr(result, "scores"):
        # RapidOCR >=3 returns numpy arrays for ``boxes``.  Never use
        # ``array or []`` here: numpy deliberately raises on ambiguous
        # truth-value evaluation.
        boxes = result.boxes if result.boxes is not None else []
        txts = result.txts if result.txts is not None else []
        scores = result.scores if result.scores is not None else []
        packed = list(zip(boxes, txts, scores))
    elif isinstance(result, tuple) and len(result) >= 1:
        packed = result[0]
    else:
        packed = result
    return _rapidocr_result_to_text(packed, min_conf)


def _ocr_embedded(image, diagnostics: OCRDiagnostics) -> str:
    global _RAPID_CALL_INFLIGHT, _RAPID_CIRCUIT_OPEN, _RAPID_TIMEOUT_COUNT

    # One stuck ONNX invocation is enough to disable embedded OCR until the
    # process is restarted.  This deliberately fails closed to the local
    # Tesseract fallback rather than letting every scanned page create another
    # permanently blocked worker.
    with _RAPID_STATE_LOCK:
        if _RAPID_CIRCUIT_OPEN:
            diagnostics.warnings.append("Embedded OCR dilewati: circuit breaker aktif setelah timeout sebelumnya.")
            return ""
        if _RAPID_CALL_INFLIGHT:
            diagnostics.warnings.append("Embedded OCR sedang digunakan request lain; memakai fallback lokal.")
            return ""
        _RAPID_CALL_INFLIGHT = True

    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _runner():
        try:
            result_queue.put((True, _ocr_embedded_core(image)))
        except Exception as exc:
            try:
                result_queue.put((False, exc))
            except Exception:
                pass

    worker = threading.Thread(target=_runner, name="lexicore-rapidocr", daemon=True)
    worker.start()
    timeout = _embedded_timeout_seconds()
    remaining = _remaining_ocr_budget()
    if remaining is not None:
        if remaining <= 0:
            with _RAPID_STATE_LOCK:
                _RAPID_CALL_INFLIGHT = False
            diagnostics.warnings.append("Embedded OCR dilewati: anggaran waktu OCR dokumen telah habis.")
            return ""
        timeout = min(timeout, remaining)
    worker.join(timeout)

    if worker.is_alive():
        with _RAPID_STATE_LOCK:
            _RAPID_CALL_INFLIGHT = False
            _RAPID_CIRCUIT_OPEN = True
            _RAPID_TIMEOUT_COUNT += 1
        diagnostics.warnings.append(
            f"Embedded OCR timeout setelah {timeout:g} detik; beralih ke Tesseract fallback. "
            "Embedded OCR dinonaktifkan sampai proses LexiCore direstart."
        )
        return ""

    with _RAPID_STATE_LOCK:
        _RAPID_CALL_INFLIGHT = False

    try:
        ok, payload = result_queue.get_nowait()
    except queue.Empty:
        diagnostics.warnings.append("Embedded OCR selesai tanpa hasil; memakai fallback lokal.")
        return ""

    if not ok:
        diagnostics.warnings.append(f"Embedded OCR gagal: {payload}")
        return ""

    text, avg = payload
    diagnostics.available = True
    diagnostics.engine = "embedded_rapidocr"
    diagnostics.engine_chain = ["embedded_rapidocr"]
    diagnostics.language = "multilingual_latin"
    diagnostics.portable = True
    if avg is not None:
        diagnostics.average_confidence = round(avg, 4)
    return text


def find_tesseract() -> Optional[str]:
    """Optional legacy fallback only; not required by LexiCore v1.3.9+."""
    configured = (os.environ.get("LEXICORE_TESSERACT_CMD") or "").strip().strip('"')
    if configured and os.path.isfile(configured):
        return configured
    in_path = shutil.which("tesseract")
    if in_path:
        return in_path
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Tesseract-OCR", "tesseract.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _ocr_tesseract_optional(image, diagnostics: OCRDiagnostics) -> str:
    if os.environ.get("LEXICORE_OCR_ALLOW_TESSERACT_FALLBACK", "1").strip().lower() in {"0","false","no","off"}:
        return ""
    try:
        import pytesseract
    except Exception:
        return ""
    cmd = find_tesseract()
    if not cmd:
        return ""
    try:
        pytesseract.pytesseract.tesseract_cmd = cmd
        desired = os.environ.get("LEXICORE_OCR_LANG", "ind+eng")
        try:
            installed = set(pytesseract.get_languages(config=""))
            langs = [x for x in desired.split("+") if x in installed]
            lang = "+".join(langs) if langs else ("eng" if "eng" in installed else desired)
        except Exception:
            lang = desired
        timeout = max(5.0, float(os.environ.get("LEXICORE_OCR_TIMEOUT_SECONDS", "45") or 45))
        remaining = _remaining_ocr_budget()
        if remaining is not None:
            if remaining <= 0:
                diagnostics.warnings.append("Tesseract dilewati: anggaran waktu OCR dokumen telah habis.")
                return ""
            timeout = max(0.25, min(timeout, remaining))
        config = os.environ.get("LEXICORE_OCR_CONFIG", "--oem 3 --psm 3 -c preserve_interword_spaces=1")
        text = pytesseract.image_to_string(_prepare_image(image), lang=lang, config=config, timeout=timeout)
        if text.strip():
            diagnostics.engine = "tesseract_fallback"
            diagnostics.engine_chain = ["embedded_rapidocr", "tesseract_fallback"]
            diagnostics.tesseract_cmd = cmd
            diagnostics.language = lang
            diagnostics.available = True
            diagnostics.portable = False
        return _clean_text(text)
    except Exception as exc:
        diagnostics.warnings.append(f"Tesseract fallback gagal: {exc}")
        return ""


def _ocr_pil_image(image, diagnostics: OCRDiagnostics) -> str:
    """Primary embedded OCR, then optional legacy Tesseract fallback."""
    text = _ocr_embedded(image, diagnostics)
    if text:
        return text
    return _ocr_tesseract_optional(image, diagnostics)


def extract_image_text(file_path: str) -> Tuple[str, Dict[str, Any]]:
    diagnostics = OCRDiagnostics(pages_total=1)
    try:
        from PIL import Image
        with Image.open(file_path) as image:
            text = _ocr_pil_image(image, diagnostics)
    except Exception as exc:
        diagnostics.pages_failed = 1
        diagnostics.warnings.append(f"Gambar tidak dapat dibuka: {exc}")
        return "", diagnostics.to_dict()

    if text:
        diagnostics.pages_ocr = 1
        diagnostics.characters_ocr = len(text)
        diagnostics.mode = "OCR_IMAGE"
    else:
        diagnostics.pages_failed = 1
        diagnostics.mode = "OCR_UNAVAILABLE_OR_EMPTY"
    return text, diagnostics.to_dict()


def extract_pdf_text(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Extract PDF text with page-level native-text → embedded OCR fallback."""
    import pypdf

    diagnostics = OCRDiagnostics()
    page_texts: List[str] = []

    with open(file_path, "rb") as handle:
        reader = pypdf.PdfReader(handle)
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise ValueError("PDF terenkripsi/berpassword dan tidak dapat dibuka tanpa password.")
            except Exception as exc:
                raise ValueError("PDF terenkripsi/berpassword dan tidak dapat dibaca oleh LexiCore.") from exc

        diagnostics.pages_total = len(reader.pages)
        native: List[str] = []
        needs_ocr: List[bool] = []
        for page in reader.pages:
            try:
                txt = _clean_text(page.extract_text() or "")
            except Exception:
                txt = ""
            native.append(txt)
            useful = _native_text_is_useful(txt)
            needs_ocr.append(not useful)
            if useful:
                diagnostics.pages_native += 1
                diagnostics.characters_native += len(txt)

    if not any(needs_ocr):
        diagnostics.mode = "NATIVE_TEXT"
        diagnostics.available = embedded_ocr_available()
        return "\n\n".join(native).strip(), diagnostics.to_dict()

    try:
        import pymupdf
        from PIL import Image
    except Exception as exc:
        diagnostics.warnings.append(f"OCR renderer tidak tersedia (PyMuPDF/Pillow): {exc}")
        diagnostics.mode = "NATIVE_TEXT_PARTIAL"
        return "\n\n".join(native).strip(), diagnostics.to_dict()

    dpi = max(144, min(300, int(os.environ.get("LEXICORE_OCR_DPI", "220") or 220)))
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    total_timeout = _ocr_total_timeout_seconds()
    diagnostics.total_timeout_seconds = total_timeout
    ocr_started = time.monotonic()
    deadline = ocr_started + total_timeout
    _set_ocr_budget(deadline)
    doc = pymupdf.open(file_path)
    timeout_warning_added = False
    try:
        for idx in range(diagnostics.pages_total):
            if not needs_ocr[idx]:
                page_texts.append(native[idx])
                continue

            remaining = _remaining_ocr_budget()
            if remaining is not None and remaining <= 0:
                diagnostics.total_timeout_exceeded = True
                diagnostics.pages_failed += 1
                page_texts.append(native[idx])
                if not timeout_warning_added:
                    diagnostics.warnings.append(
                        f"Anggaran waktu total OCR dokumen {total_timeout:g} detik telah habis; "
                        "halaman scan tersisa dilewati agar request tetap responsif."
                    )
                    timeout_warning_added = True
                continue

            try:
                pix = doc.load_page(idx).get_pixmap(matrix=matrix, alpha=False)
                # Rendering itself is local, but re-check the document budget
                # before starting either OCR engine.
                remaining = _remaining_ocr_budget()
                if remaining is not None and remaining <= 0:
                    diagnostics.total_timeout_exceeded = True
                    diagnostics.pages_failed += 1
                    page_texts.append(native[idx])
                    if not timeout_warning_added:
                        diagnostics.warnings.append(
                            f"Anggaran waktu total OCR dokumen {total_timeout:g} detik telah habis; "
                            "halaman scan tersisa dilewati agar request tetap responsif."
                        )
                        timeout_warning_added = True
                    continue
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = _ocr_pil_image(image, diagnostics)
                if ocr_text:
                    diagnostics.pages_ocr += 1
                    diagnostics.characters_ocr += len(ocr_text)
                    page_texts.append(ocr_text)
                else:
                    diagnostics.pages_failed += 1
                    page_texts.append(native[idx])
            except Exception as exc:
                diagnostics.pages_failed += 1
                diagnostics.warnings.append(f"Halaman {idx+1}: {exc}")
                page_texts.append(native[idx])
    finally:
        diagnostics.elapsed_ocr_seconds = round(time.monotonic() - ocr_started, 3)
        _set_ocr_budget(None)
        doc.close()

    if diagnostics.pages_ocr and diagnostics.pages_native:
        diagnostics.mode = "HYBRID_NATIVE_OCR"
    elif diagnostics.pages_ocr:
        diagnostics.mode = "OCR_FALLBACK"
    elif diagnostics.pages_native:
        diagnostics.mode = "NATIVE_TEXT_PARTIAL"
    else:
        diagnostics.mode = "OCR_UNAVAILABLE_OR_EMPTY"
    return "\n\n".join(page_texts).strip(), diagnostics.to_dict()


def ocr_runtime_status(load_engine: bool = False) -> Dict[str, Any]:
    """Return a multi-engine readiness report.

    Embedded OCR is preferred for portable/server deployments.  A healthy
    Tesseract installation can still keep OCR operational as a local fallback
    while embedded-model problems are diagnosed; therefore ``available`` means
    at least one local OCR path is ready, while ``embedded_available`` exposes
    portability explicitly.
    """
    embedded = embedded_ocr_available()
    embedded_error = None
    if load_engine and embedded:
        try:
            _get_rapidocr_engine()
        except Exception as exc:
            embedded = False
            embedded_error = str(exc)

    tesseract_cmd = find_tesseract()
    tesseract_available = bool(tesseract_cmd)
    tesseract_languages: List[str] = []
    tesseract_error = None
    if tesseract_available:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            tesseract_languages = sorted(set(pytesseract.get_languages(config="")))
        except Exception as exc:
            tesseract_error = str(exc)

    preferred = "embedded_rapidocr" if embedded else ("tesseract_fallback" if tesseract_available else "none")
    overall = bool(embedded or tesseract_available)
    return {
        "enabled": True,
        "engine": preferred,
        "preferred_engine": "embedded_rapidocr",
        "available": overall,
        "embedded_available": bool(embedded),
        "portable": bool(embedded),
        "os_executable_required": False if embedded else bool(tesseract_available),
        "model_runtime": "onnxruntime",
        "language": "multilingual_latin",
        "dpi": int(os.environ.get("LEXICORE_OCR_DPI", "220") or 220),
        "min_confidence": float(os.environ.get("LEXICORE_OCR_MIN_CONFIDENCE", "0.45") or 0.45),
        "embedded_timeout_seconds": _embedded_timeout_seconds(),
        "total_timeout_seconds": _ocr_total_timeout_seconds(),
        "embedded_circuit_open": bool(_RAPID_CIRCUIT_OPEN),
        "embedded_timeout_count": int(_RAPID_TIMEOUT_COUNT),
        "policy": "NATIVE_TEXT_FIRST_PAGE_LEVEL_EMBEDDED_OCR_WITH_LOCAL_FALLBACK",
        "privacy": "LOCAL_HOST_PROCESSING",
        "optional_tesseract_fallback": tesseract_available,
        "tesseract_available": tesseract_available,
        "tesseract_cmd": tesseract_cmd,
        "tesseract_languages": tesseract_languages,
        "embedded_error": embedded_error,
        "tesseract_error": tesseract_error,
        "error": None if overall else (embedded_error or tesseract_error or "Tidak ada OCR engine lokal yang siap"),
    }

