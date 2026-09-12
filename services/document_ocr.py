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
import hashlib
import json
import copy
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
_RAPID_CONSECUTIVE_TIMEOUTS = 0
_RAPID_CIRCUIT_OPENED_AT: Optional[float] = None

# Diagnostic-only OCR telemetry. Disabled by default and deliberately kept
# outside OCR decision logic. It may be enabled for one process with
# LEXICORE_OCR_DEBUG=1. JSONL output is append-only and best-effort: telemetry
# failures must never change OCR behavior.
_OCR_DEBUG_LOCK = threading.Lock()
_OCR_DEBUG_RUN_ID = f"{os.getpid()}-{int(time.time() * 1000)}"
_OCR_DEBUG_START_MONOTONIC = time.monotonic()


def _ocr_debug_enabled() -> bool:
    return (os.environ.get("LEXICORE_OCR_DEBUG") or "").strip().lower() in {"1", "true", "yes", "on"}


def _ocr_debug_file() -> str:
    return (os.environ.get("LEXICORE_OCR_DEBUG_FILE") or "ocr_debug.jsonl").strip() or "ocr_debug.jsonl"


def _log_ocr_debug(
    event: str,
    *,
    page: Optional[int] = None,
    engine: Optional[str] = None,
    elapsed: Optional[float] = None,
    text_len: Optional[int] = None,
    error: Optional[Any] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one best-effort diagnostic event without changing OCR control flow."""
    if not _ocr_debug_enabled():
        return
    try:
        payload: Dict[str, Any] = {
            "run_id": _OCR_DEBUG_RUN_ID,
            "event": event,
            "page": page if page is not None else getattr(_OCR_BUDGET_LOCAL, "current_page", None),
            "engine": engine,
            "elapsed": round(float(elapsed), 4) if elapsed is not None else None,
            "text_len": int(text_len) if text_len is not None else None,
            "error": str(error) if error is not None else None,
            "elapsed_since_start": round(time.monotonic() - _OCR_DEBUG_START_MONOTONIC, 4),
            "remaining_document_budget": None,
            "rapid_timeout_count": int(_RAPID_TIMEOUT_COUNT),
            "rapid_consecutive_timeouts": int(_RAPID_CONSECUTIVE_TIMEOUTS),
            "rapid_circuit_open": bool(_RAPID_CIRCUIT_OPEN),
            "rapid_call_inflight": bool(_RAPID_CALL_INFLIGHT),
        }
        remaining = _remaining_ocr_budget()
        if remaining is not None:
            payload["remaining_document_budget"] = round(float(remaining), 4)
        if extra:
            payload.update(extra)
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with _OCR_DEBUG_LOCK:
            with open(_ocr_debug_file(), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:
        # Diagnostic logging is intentionally non-authoritative.
        return
_OCR_BUDGET_LOCAL = threading.local()
_OCR_BEST_CACHE: Dict[str, Tuple[str, Dict[str, Any]]] = {}
_OCR_BEST_CACHE_LOCK = threading.Lock()
_OCR_BEST_CACHE_MAX = 8

# Per-page wall-clock slice used by the document OCR scheduler.  This keeps a
# long scanned PDF from spending the entire document budget on a handful of
# difficult pages.  It is intentionally thread-local because Case Analysis is
# request-scoped.


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
    coverage_ratio: Optional[float] = None
    manual_review_required: bool = False
    review_status: str = "NOT_REQUIRED"
    partial_text_preserved: bool = True
    authoritative_for_analysis: bool = True
    coverage_guard_status: str = "OCR_CURRENT_RESULT"
    attempt_coverage_ratio: Optional[float] = None
    previous_best_coverage_ratio: Optional[float] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.engine_chain is None:
            self.engine_chain = ["embedded_rapidocr"]

    def to_dict(self) -> Dict[str, Any]:
        total=max(0,int(self.pages_total or 0))
        read=max(0,int(self.pages_native or 0))+max(0,int(self.pages_ocr or 0))
        self.coverage_ratio=round(read/total,4) if total else None
        failed=max(0,int(self.pages_failed or 0))
        try:
            minimum_coverage=max(0.0,min(1.0,float(os.environ.get('LEXICORE_OCR_MIN_ACCEPTABLE_COVERAGE','0.80') or 0.80)))
        except Exception:
            minimum_coverage=0.80
        coverage=(read/total) if total else 1.0
        self.manual_review_required=bool(total and coverage < minimum_coverage)
        self.review_status='MANUAL_REVIEW_REQUIRED' if self.manual_review_required else 'NOT_REQUIRED'
        self.partial_text_preserved=True
        if self.manual_review_required:
            msg=(f'OCR coverage parsial: {read}/{total} halaman terbaca; {failed} halaman belum terbaca. '
                 f'Target minimum coverage {minimum_coverage:.0%}; Manual review diperlukan sebelum analisis dijadikan dasar tindakan.')
            if msg not in self.warnings:
                self.warnings.append(msg)
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


def _ocr_total_timeout_seconds(scan_pages: Optional[int] = None) -> float:
    """Wall-clock OCR budget for one document.

    If the operator explicitly sets ``LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS`` we
    respect it exactly (subject to the existing >=5s safety floor).  Otherwise
    scan-heavy PDFs receive an adaptive bounded budget so later pages are not
    starved by an arbitrary 180-second ceiling.

    Default policy: max(180s, 60s + 8s * scan_pages), capped at 360s.
    For the 37-page DKPP benchmark this yields 356s.
    """
    raw = os.environ.get("LEXICORE_OCR_TOTAL_TIMEOUT_SECONDS")
    if raw not in (None, ""):
        try:
            return max(5.0, float(raw))
        except Exception:
            return 180.0
    pages = max(0, int(scan_pages or 0))
    adaptive = 60.0 + (8.0 * pages)
    return max(180.0, min(360.0, adaptive))


def _set_ocr_budget(deadline: Optional[float]) -> None:
    _OCR_BUDGET_LOCAL.deadline = deadline


def _remaining_ocr_budget() -> Optional[float]:
    deadline = getattr(_OCR_BUDGET_LOCAL, "deadline", None)
    if deadline is None:
        return None
    return max(0.0, float(deadline) - time.monotonic())


def _set_ocr_page_budget(seconds: Optional[float]) -> None:
    if seconds is None:
        _OCR_BUDGET_LOCAL.page_deadline = None
        return
    _OCR_BUDGET_LOCAL.page_deadline = time.monotonic() + max(0.25, float(seconds))


def _remaining_ocr_page_budget() -> Optional[float]:
    deadline = getattr(_OCR_BUDGET_LOCAL, "page_deadline", None)
    if deadline is None:
        return None
    return max(0.0, float(deadline) - time.monotonic())


def _page_time_slice(remaining_document: Optional[float], remaining_pages: int) -> Optional[float]:
    """Return an adaptive *planning* slice for a still-unread page.

    This is no longer a hard 2.5-6 second engine timeout.  The previous closure
    made the planning slice a hard deadline, which caused RapidOCR to time out
    around 1-2s and Tesseract around 5s on Windows.  Keep it only as telemetry /
    budget guidance; engine timeouts have their own bounded adaptive policy.
    """
    if remaining_document is None:
        return None
    pages = max(1, int(remaining_pages or 1))
    reserve = float(os.environ.get("LEXICORE_OCR_BUDGET_RESERVE_SECONDS", "8") or 8)
    distributable = max(1.0, float(remaining_document) - min(reserve, float(remaining_document) * 0.10))
    return max(1.0, distributable / pages)


def _adaptive_engine_timeout(*, engine: str, remaining_document: Optional[float], remaining_pages: int) -> float:
    """Bound one OCR engine attempt without starving the whole document.

    RapidOCR defaults to 8-12s and Tesseract to 12-20s.  The fair-share budget
    may reduce the upper bound near the document deadline, but never to the
    pathological 1-5 second values that caused the regression.
    """
    pages = max(1, int(remaining_pages or 1))
    if engine == "rapid":
        floor = max(4.0, float(os.environ.get("LEXICORE_RAPIDOCR_MIN_TIMEOUT_SECONDS", "8") or 8))
        ceiling = max(floor, float(os.environ.get("LEXICORE_RAPIDOCR_MAX_TIMEOUT_SECONDS", "12") or 12))
        factor = 1.25
    else:
        floor = max(6.0, float(os.environ.get("LEXICORE_TESSERACT_MIN_TIMEOUT_SECONDS", "12") or 12))
        ceiling = max(floor, float(os.environ.get("LEXICORE_TESSERACT_MAX_TIMEOUT_SECONDS", "20") or 20))
        factor = 2.0
    if remaining_document is None:
        return ceiling
    fair = max(floor, (max(0.0, remaining_document) / pages) * factor)
    return max(0.5, min(ceiling, fair, max(0.5, remaining_document)))


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
    global _RAPID_CONSECUTIVE_TIMEOUTS, _RAPID_CIRCUIT_OPENED_AT

    threshold = max(2, int(os.environ.get("LEXICORE_RAPIDOCR_CIRCUIT_FAILURES", "3") or 3))
    cooldown = max(5.0, float(os.environ.get("LEXICORE_RAPIDOCR_CIRCUIT_COOLDOWN_SECONDS", "30") or 30))

    with _RAPID_STATE_LOCK:
        # A circuit is temporary.  One timeout must never disable RapidOCR for
        # the entire process.  After cooldown the engine is allowed to probe
        # again; a successful page resets the consecutive failure counter.
        if _RAPID_CIRCUIT_OPEN:
            opened = _RAPID_CIRCUIT_OPENED_AT or 0.0
            if time.monotonic() - opened >= cooldown and not _RAPID_CALL_INFLIGHT:
                _RAPID_CIRCUIT_OPEN = False
                _RAPID_CONSECUTIVE_TIMEOUTS = 0
                _RAPID_CIRCUIT_OPENED_AT = None
            else:
                diagnostics.warnings.append(
                    f"Embedded OCR dilewati sementara: circuit breaker aktif setelah {_RAPID_CONSECUTIVE_TIMEOUTS} timeout beruntun."
                )
                _log_ocr_debug("CIRCUIT_SKIP", engine="rapid")
                return ""
        if _RAPID_CALL_INFLIGHT:
            diagnostics.warnings.append("Embedded OCR masih menyelesaikan halaman sebelumnya; memakai fallback lokal.")
            _log_ocr_debug("RAPID_INFLIGHT_SKIP", engine="rapid")
            return ""
        _RAPID_CALL_INFLIGHT = True

    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _runner():
        global _RAPID_CALL_INFLIGHT
        try:
            result_queue.put((True, _ocr_embedded_core(image)))
        except Exception as exc:
            try:
                result_queue.put((False, exc))
            except Exception:
                pass
        finally:
            # Important: if the request thread timed out, keep the inflight flag
            # until the actual ONNX call exits.  This prevents spawning many
            # permanently blocked RapidOCR workers.
            with _RAPID_STATE_LOCK:
                _RAPID_CALL_INFLIGHT = False

    worker = threading.Thread(target=_runner, name="lexicore-rapidocr", daemon=True)
    rapid_started = time.monotonic()
    _log_ocr_debug("RAPID_START", engine="rapid")
    worker.start()
    remaining = _remaining_ocr_budget()
    if remaining is not None and remaining <= 0:
        diagnostics.warnings.append("Embedded OCR dilewati: anggaran waktu OCR dokumen telah habis.")
        _log_ocr_debug("GLOBAL_BUDGET_EXHAUSTED", engine="rapid")
        return ""
    remaining_pages = max(1, int(getattr(_OCR_BUDGET_LOCAL, "remaining_pages", 1) or 1))
    timeout = min(_embedded_timeout_seconds(), _adaptive_engine_timeout(
        engine="rapid", remaining_document=remaining, remaining_pages=remaining_pages
    ))
    worker.join(timeout)

    if worker.is_alive():
        with _RAPID_STATE_LOCK:
            _RAPID_TIMEOUT_COUNT += 1
            _RAPID_CONSECUTIVE_TIMEOUTS += 1
            if _RAPID_CONSECUTIVE_TIMEOUTS >= threshold:
                _RAPID_CIRCUIT_OPEN = True
                _RAPID_CIRCUIT_OPENED_AT = time.monotonic()
        diagnostics.warnings.append(
            f"Embedded OCR timeout setelah {timeout:g} detik; beralih ke Tesseract fallback. "
            f"Circuit breaker baru aktif setelah {threshold} timeout beruntun."
        )
        _log_ocr_debug(
            "RAPID_TIMEOUT", engine="rapid", elapsed=time.monotonic() - rapid_started,
            extra={"timeout_seconds": round(timeout, 4), "circuit_threshold": threshold},
        )
        return ""

    try:
        ok, payload = result_queue.get_nowait()
    except queue.Empty:
        diagnostics.warnings.append("Embedded OCR selesai tanpa hasil; memakai fallback lokal.")
        return ""

    if not ok:
        with _RAPID_STATE_LOCK:
            _RAPID_CONSECUTIVE_TIMEOUTS = 0
        diagnostics.warnings.append(f"Embedded OCR gagal: {payload}")
        _log_ocr_debug("RAPID_ERROR", engine="rapid", elapsed=time.monotonic() - rapid_started, error=payload)
        return ""

    with _RAPID_STATE_LOCK:
        _RAPID_CONSECUTIVE_TIMEOUTS = 0
        _RAPID_CIRCUIT_OPEN = False
        _RAPID_CIRCUIT_OPENED_AT = None

    text, avg = payload
    diagnostics.available = True
    diagnostics.engine = "embedded_rapidocr"
    diagnostics.engine_chain = ["embedded_rapidocr"]
    diagnostics.language = "multilingual_latin"
    diagnostics.portable = True
    if avg is not None:
        diagnostics.average_confidence = round(avg, 4)
    _log_ocr_debug("RAPID_SUCCESS", engine="rapid", elapsed=time.monotonic() - rapid_started, text_len=len(text or ""))
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
        remaining = _remaining_ocr_budget()
        if remaining is not None and remaining <= 0:
            diagnostics.warnings.append("Tesseract dilewati: anggaran waktu OCR dokumen telah habis.")
            _log_ocr_debug("GLOBAL_BUDGET_EXHAUSTED", engine="tesseract")
            return ""
        remaining_pages = max(1, int(getattr(_OCR_BUDGET_LOCAL, "remaining_pages", 1) or 1))
        timeout = _adaptive_engine_timeout(
            engine="tesseract", remaining_document=remaining, remaining_pages=remaining_pages
        )
        explicit = (os.environ.get("LEXICORE_TESSERACT_PAGE_TIMEOUT_SECONDS") or "").strip()
        if explicit:
            try:
                timeout = min(timeout, max(1.0, float(explicit)))
            except Exception:
                pass
        config = os.environ.get("LEXICORE_OCR_CONFIG", "--oem 3 --psm 3 -c preserve_interword_spaces=1")
        tess_started = time.monotonic()
        _log_ocr_debug("TESSERACT_START", engine="tesseract", extra={"timeout_seconds": round(timeout, 4), "lang": lang})
        text = pytesseract.image_to_string(_prepare_image(image), lang=lang, config=config, timeout=timeout)
        if text.strip():
            diagnostics.engine = "tesseract_fallback"
            diagnostics.engine_chain = ["embedded_rapidocr", "tesseract_fallback"]
            diagnostics.tesseract_cmd = cmd
            diagnostics.language = lang
            diagnostics.available = True
            diagnostics.portable = False
        cleaned = _clean_text(text)
        _log_ocr_debug("TESSERACT_SUCCESS" if cleaned else "TESSERACT_EMPTY", engine="tesseract", elapsed=time.monotonic() - tess_started, text_len=len(cleaned))
        return cleaned
    except Exception as exc:
        diagnostics.warnings.append(f"Tesseract fallback gagal: {exc}")
        event = "TESSERACT_TIMEOUT" if "timeout" in str(exc).lower() else "TESSERACT_ERROR"
        elapsed = time.monotonic() - tess_started if "tess_started" in locals() else None
        _log_ocr_debug(event, engine="tesseract", elapsed=elapsed, error=exc)
        return ""


def _ocr_pil_image(image, diagnostics: OCRDiagnostics, *, allow_tesseract: bool = True) -> str:
    """Primary embedded OCR with optional Tesseract fallback.

    ``allow_tesseract=False`` is used by the first pass of scanned PDFs so all
    pages receive a fair RapidOCR opportunity before slower fallback work is
    attempted.  Image OCR and existing callers retain the original behavior.
    """
    text = _ocr_embedded(image, diagnostics)
    if text or not allow_tesseract:
        return text
    return _ocr_tesseract_optional(image, diagnostics)


def _notify_progress(callback, done: int, total: int, phase: str) -> None:
    if not callback:
        return
    try:
        callback(int(done), max(1, int(total or 1)), phase)
    except Exception:
        # Progress reporting is observational only and must never alter OCR.
        return


def extract_image_text(file_path: str, progress_callback=None) -> Tuple[str, Dict[str, Any]]:
    diagnostics = OCRDiagnostics(pages_total=1)
    _notify_progress(progress_callback, 0, 1, 'document')
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
    _notify_progress(progress_callback, 1, 1, 'document')
    return text, diagnostics.to_dict()



def _ocr_file_fingerprint(file_path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _coverage_from_diag(diag: Dict[str, Any]) -> float:
    total = max(0, int((diag or {}).get("pages_total") or 0))
    if not total:
        return 1.0
    read = max(0, int((diag or {}).get("pages_native") or 0)) + max(0, int((diag or {}).get("pages_ocr") or 0))
    return max(0.0, min(1.0, read / total))


def _apply_monotonic_coverage_guard(file_path: str, text: str, diag: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Never promote a worse OCR extraction over a better extraction of the same bytes.

    The cache is intentionally process-local and bounded; it protects repeated
    Case Analysis runs without introducing database state or changing uploaded
    files.  If no prior extraction exists and coverage is severely low, the
    diagnostic is explicitly marked non-authoritative so the route can stop
    aggressive downstream analysis.
    """
    fp = _ocr_file_fingerprint(file_path)
    current = _coverage_from_diag(diag)
    diag = copy.deepcopy(diag or {})
    diag["attempt_coverage_ratio"] = round(current, 4)
    severe = max(0.0, min(1.0, float(os.environ.get("LEXICORE_OCR_SEVERE_COVERAGE_FLOOR", "0.20") or 0.10)))
    if not fp:
        diag["coverage_guard_status"] = "OCR_CURRENT_RESULT_NO_FINGERPRINT"
        diag["authoritative_for_analysis"] = bool(current >= severe)
        return text, diag

    with _OCR_BEST_CACHE_LOCK:
        previous = _OCR_BEST_CACHE.get(fp)
        previous_cov = _coverage_from_diag(previous[1]) if previous else -1.0
        if previous and current + 1e-9 < previous_cov:
            best_text, best_diag = previous
            out = copy.deepcopy(best_diag)
            out.setdefault("warnings", [])
            out["warnings"].append(
                f"OCR attempt terbaru regresi ({current:.1%}) dibanding hasil terbaik proses ini ({previous_cov:.1%}); "
                "hasil terbaik dipertahankan sebagai authoritative analysis text."
            )
            out["attempt_coverage_ratio"] = round(current, 4)
            out["previous_best_coverage_ratio"] = round(previous_cov, 4)
            out["coverage_guard_status"] = "OCR_REGRESSED_PREVIOUS_BEST_RESTORED"
            out["authoritative_for_analysis"] = True
            return best_text, out

        diag["previous_best_coverage_ratio"] = round(previous_cov, 4) if previous else None
        diag["coverage_guard_status"] = "OCR_IMPROVED_OR_EQUAL" if previous else "OCR_FIRST_OBSERVATION"
        diag["authoritative_for_analysis"] = bool(current >= severe)
        _OCR_BEST_CACHE[fp] = (text, copy.deepcopy(diag))
        # bounded FIFO-ish eviction; insertion ordering is deterministic in py3.7+
        while len(_OCR_BEST_CACHE) > _OCR_BEST_CACHE_MAX:
            _OCR_BEST_CACHE.pop(next(iter(_OCR_BEST_CACHE)))
    return text, diag

def extract_pdf_text(file_path: str, progress_callback=None) -> Tuple[str, Dict[str, Any]]:
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
        _notify_progress(progress_callback, 0, diagnostics.pages_total, 'document')
        _log_ocr_debug("DOCUMENT_START", page=None, extra={"file": os.path.basename(file_path), "pages_total": diagnostics.pages_total})
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
        _notify_progress(progress_callback, diagnostics.pages_total, diagnostics.pages_total, 'document')
        return "\n\n".join(native).strip(), diagnostics.to_dict()

    try:
        import pymupdf
        from PIL import Image
    except Exception as exc:
        diagnostics.warnings.append(f"OCR renderer tidak tersedia (PyMuPDF/Pillow): {exc}")
        diagnostics.mode = "NATIVE_TEXT_PARTIAL"
        return "\n\n".join(native).strip(), diagnostics.to_dict()

    configured_dpi = max(144, min(300, int(os.environ.get("LEXICORE_OCR_DPI", "220") or 220)))
    # Large scan-heavy documents use a faster render by default.  180 DPI is
    # usually sufficient for pleadings while materially reducing Tesseract
    # latency.  Users may raise LEXICORE_OCR_FAST_DPI when the source has very
    # small print.
    scan_pages=sum(1 for flag in needs_ocr if flag)
    fast_dpi=max(144, min(configured_dpi, int(os.environ.get("LEXICORE_OCR_FAST_DPI", "170") or 180)))
    dpi = fast_dpi if scan_pages >= 12 else configured_dpi
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    total_timeout = _ocr_total_timeout_seconds(scan_pages)
    diagnostics.total_timeout_seconds = total_timeout
    ocr_started = time.monotonic()
    deadline = ocr_started + total_timeout
    _set_ocr_budget(deadline)
    doc = pymupdf.open(file_path)
    timeout_warning_added = False
    # Keep page ordering deterministic and allow second-pass replacement.
    page_texts = list(native)
    pending_fallback: List[int] = []
    try:
        # PASS 1 — fairness first: every scanned page gets a RapidOCR chance.
        for idx in range(diagnostics.pages_total):
            _OCR_BUDGET_LOCAL.current_page = idx + 1
            if not needs_ocr[idx]:
                _log_ocr_debug("PAGE_NATIVE", page=idx + 1, engine="native", text_len=len(native[idx] or ""))
                _notify_progress(progress_callback, idx + 1, diagnostics.pages_total, 'rapid')
                continue

            _log_ocr_debug("PAGE_START", page=idx + 1, extra={"needs_ocr": True, "pass": "rapid"})
            remaining = _remaining_ocr_budget()
            if remaining is not None and remaining <= 0:
                diagnostics.total_timeout_exceeded = True
                pending_fallback.append(idx)
                _log_ocr_debug("GLOBAL_BUDGET_EXHAUSTED", page=idx + 1, extra={"stage": "rapid_pass_before_render"})
                _notify_progress(progress_callback, idx + 1, diagnostics.pages_total, 'rapid')
                continue

            try:
                remaining_pages = sum(1 for j in range(idx, diagnostics.pages_total) if needs_ocr[j])
                _OCR_BUDGET_LOCAL.remaining_pages = remaining_pages
                _set_ocr_page_budget(_page_time_slice(remaining, remaining_pages))
                render_started = time.monotonic()
                pix = doc.load_page(idx).get_pixmap(matrix=matrix, alpha=False)
                _log_ocr_debug("RENDER_DONE", page=idx + 1, engine="render", elapsed=time.monotonic() - render_started, extra={"width": pix.width, "height": pix.height, "dpi": dpi, "pass": "rapid"})
                remaining = _remaining_ocr_budget()
                if remaining is not None and remaining <= 0:
                    diagnostics.total_timeout_exceeded = True
                    pending_fallback.append(idx)
                    _log_ocr_debug("GLOBAL_BUDGET_EXHAUSTED", page=idx + 1, extra={"stage": "rapid_pass_after_render"})
                    _notify_progress(progress_callback, idx + 1, diagnostics.pages_total, 'rapid')
                    continue
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = _ocr_pil_image(image, diagnostics, allow_tesseract=False)
                if ocr_text:
                    diagnostics.pages_ocr += 1
                    diagnostics.characters_ocr += len(ocr_text)
                    page_texts[idx] = ocr_text
                    _log_ocr_debug("PAGE_DONE", page=idx + 1, text_len=len(ocr_text), extra={"status": "ocr_success", "pass": "rapid"})
                else:
                    pending_fallback.append(idx)
                    _log_ocr_debug("PAGE_PENDING_FALLBACK", page=idx + 1, extra={"pass": "rapid"})
            except Exception as exc:
                pending_fallback.append(idx)
                diagnostics.warnings.append(f"Halaman {idx+1} RapidOCR: {exc}")
                _log_ocr_debug("PAGE_ERROR", page=idx + 1, error=exc, extra={"pass": "rapid"})
            finally:
                _notify_progress(progress_callback, idx + 1, diagnostics.pages_total, 'rapid')

        # PASS 2 — Tesseract only for unresolved pages while budget remains.
        unresolved: List[int] = []
        for pos, idx in enumerate(pending_fallback):
            _OCR_BUDGET_LOCAL.current_page = idx + 1
            remaining = _remaining_ocr_budget()
            remaining_pages = max(1, len(pending_fallback) - pos)
            _OCR_BUDGET_LOCAL.remaining_pages = remaining_pages
            if remaining is not None and remaining <= 0:
                diagnostics.total_timeout_exceeded = True
                unresolved.extend(pending_fallback[pos:])
                _log_ocr_debug("GLOBAL_BUDGET_EXHAUSTED", page=idx + 1, extra={"stage": "tesseract_pass_before_render", "remaining_unresolved": remaining_pages})
                break
            try:
                _log_ocr_debug("PAGE_FALLBACK_START", page=idx + 1, extra={"pass": "tesseract"})
                render_started = time.monotonic()
                pix = doc.load_page(idx).get_pixmap(matrix=matrix, alpha=False)
                _log_ocr_debug("RENDER_DONE", page=idx + 1, engine="render", elapsed=time.monotonic() - render_started, extra={"width": pix.width, "height": pix.height, "dpi": dpi, "pass": "tesseract"})
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = _ocr_tesseract_optional(image, diagnostics)
                if ocr_text:
                    diagnostics.pages_ocr += 1
                    diagnostics.characters_ocr += len(ocr_text)
                    page_texts[idx] = ocr_text
                    _log_ocr_debug("PAGE_DONE", page=idx + 1, text_len=len(ocr_text), extra={"status": "ocr_success", "pass": "tesseract"})
                else:
                    unresolved.append(idx)
                    _log_ocr_debug("PAGE_FAILED", page=idx + 1, text_len=0, extra={"status": "no_ocr_text", "pass": "tesseract"})
            except Exception as exc:
                unresolved.append(idx)
                diagnostics.warnings.append(f"Halaman {idx+1} Tesseract: {exc}")
                _log_ocr_debug("PAGE_ERROR", page=idx + 1, error=exc, extra={"pass": "tesseract"})
            finally:
                _notify_progress(progress_callback, pos + 1, len(pending_fallback), 'tesseract')

        diagnostics.pages_failed = len(set(unresolved))
        if diagnostics.total_timeout_exceeded and not timeout_warning_added:
            diagnostics.warnings.append(
                f"Anggaran waktu total OCR dokumen {total_timeout:g} detik telah habis; "
                "halaman scan tersisa dipertahankan sebagai belum terbaca agar request tetap bounded."
            )
            timeout_warning_added = True
    finally:
        diagnostics.elapsed_ocr_seconds = round(time.monotonic() - ocr_started, 3)
        _set_ocr_page_budget(None)
        _set_ocr_budget(None)
        doc.close()
        try:
            delattr(_OCR_BUDGET_LOCAL, "current_page")
        except Exception:
            pass

    _log_ocr_debug("DOCUMENT_DONE", page=None, elapsed=diagnostics.elapsed_ocr_seconds, extra={
        "pages_total": diagnostics.pages_total,
        "pages_native": diagnostics.pages_native,
        "pages_ocr": diagnostics.pages_ocr,
        "pages_failed": diagnostics.pages_failed,
        "characters_ocr": diagnostics.characters_ocr,
        "total_timeout_exceeded": diagnostics.total_timeout_exceeded,
    })

    if diagnostics.pages_ocr and diagnostics.pages_native:
        diagnostics.mode = "HYBRID_NATIVE_OCR"
    elif diagnostics.pages_ocr:
        diagnostics.mode = "OCR_FALLBACK"
    elif diagnostics.pages_native:
        diagnostics.mode = "NATIVE_TEXT_PARTIAL"
    else:
        diagnostics.mode = "OCR_UNAVAILABLE_OR_EMPTY"
    final_text = "\n\n".join(page_texts).strip()
    final_diag = diagnostics.to_dict()
    _notify_progress(progress_callback, diagnostics.pages_total, diagnostics.pages_total, 'complete')
    return _apply_monotonic_coverage_guard(file_path, final_text, final_diag)


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

