"""Opt-in diagnostic trace for LexiCore official verification.

This module is telemetry-only. It must not alter candidate ordering, verification
results, fail-closed gates, or runtime budgets. Enable with:

    LEXICORE_OFFICIAL_TRACE=1

Optional environment variables:
    LEXICORE_TRACE_EXPECTED=UU:31:1999
    LEXICORE_TRACE_FILE=trace_official_verification.json
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OfficialVerifierTrace:
    _lock = threading.Lock()
    _entries: list[dict[str, Any]] = []

    @classmethod
    def enabled(cls) -> bool:
        return str(os.getenv("LEXICORE_OFFICIAL_TRACE", "")).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def expected_filter(cls) -> str:
        return str(os.getenv("LEXICORE_TRACE_EXPECTED", "")).strip().upper()

    @classmethod
    def path(cls) -> Path:
        raw = str(os.getenv("LEXICORE_TRACE_FILE", "trace_official_verification.json")).strip()
        return Path(raw or "trace_official_verification.json")

    @classmethod
    def clear(cls) -> None:
        if not cls.enabled():
            return
        with cls._lock:
            cls._entries = []
            try:
                cls.path().write_text("[]\n", encoding="utf-8")
            except Exception as exc:  # telemetry must never break analysis
                logger.warning("official trace clear failed: %s", exc)

    @classmethod
    def log(cls, step: str, data: dict[str, Any] | None = None, *, expected: str | None = None) -> None:
        if not cls.enabled():
            return
        expected_key = str(expected or (data or {}).get("expected") or "").strip().upper()
        wanted = cls.expected_filter()
        if wanted and expected_key and expected_key != wanted:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": str(step),
            "expected": expected_key or None,
            "data": data or {},
        }
        with cls._lock:
            cls._entries.append(entry)
            try:
                cls.path().write_text(json.dumps(cls._entries, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
            except Exception as exc:
                logger.warning("official trace write failed: %s", exc)
        logger.info("TRACE [%s] %s", step, json.dumps(entry["data"], ensure_ascii=False, default=str)[:900])

    @classmethod
    def get_trace(cls) -> list[dict[str, Any]]:
        with cls._lock:
            return list(cls._entries)
