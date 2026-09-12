"""Generic civil-pleading semantic quality guard for LexiCore SAL v1.0.

This module is deliberately outside the legal reasoning core.  It provides
positive, bounded hints for civil pleading posture and statement typing, plus a
reader-facing strategy sanitizer.  It never creates evidence, never marks law
applicable, and never mutates the frozen SAL schema.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict

_WS = re.compile(r"\s+")

_CIVIL_POSTURES = (
    ("REPLIK", re.compile(r"\brepl(?:i|ie)k\b", re.I), "Replik Perdata"),
    ("DUPLIK", re.compile(r"\bdupl(?:i|ie)k\b", re.I), "Duplik Perdata"),
    ("JAWABAN", re.compile(r"\bjawaban\s+(?:para\s+)?tergugat\b|\bjawaban\s+atas\s+gugatan\b", re.I), "Jawaban Gugatan Perdata"),
    ("GUGATAN", re.compile(r"\b(?:surat\s+)?gugatan\b", re.I), "Surat Gugatan Perdata"),
)

_PROCEDURAL_FILING = re.compile(
    r"\b(?:bersama\s+ini\s+(?:kami\s+)?mohon|mohon\s+diperkenankan|"
    r"mengajukan\s+(?:repl(?:i|ie)k|dupl(?:i|ie)k|jawaban|gugatan)|"
    r"repl(?:i|ie)k\s+atas\s+jawaban|dupl(?:i|ie)k\s+atas\s+repl(?:i|ie)k)\b",
    re.I,
)

_ARGUMENTATIVE = re.compile(
    r"\b(?:exceptio(?:\s+[a-z]+){0,4}|plurium\s+litis\s+consortium|"
    r"merupakan\s+perbuatan\s+melawan\s+hukum|"
    r"(?:ptsl|bpn|turut\s+tergugat)\s+tidak\s+(?:bisa|dapat)\s+(?:kita\s+)?(?:libatkan|ditarik)|"
    r"gugatan\s+(?:kabur|obscuur\s+libel)|error\s+in\s+persona|"
    r"kurang\s+pihak|tidak\s+beralasan\s+hukum)\b",
    re.I,
)

# Reader-facing only.  Replacements are deliberately phrases, never broad token
# substitutions, so terms such as "dakwaan" quoted from an opponent remain
# visible outside contaminated strategy templates.
_STRATEGY_REPLACEMENTS = (
    (re.compile(r"bagian\s+dakwaan\s+yang\s+diserang", re.I), "bagian posita atau jawaban lawan yang dipersoalkan"),
    (re.compile(r"bagian\s+dakwaan", re.I), "bagian posita atau jawaban lawan"),
    (re.compile(r"cacat\s+surat\s+dakwaan", re.I), "cacat formil gugatan atau jawaban"),
    (re.compile(r"pengadilan\s+tipikor", re.I), "pengadilan yang memeriksa perkara perdata"),
    (re.compile(r"eksepsi\s+formil\s+versus\s+pokok\s+perkara", re.I), "eksepsi kompetensi/formil versus materi pokok perkara"),
    (re.compile(r"dakwaan\s+asli", re.I), "gugatan dan jawaban asli"),
)


def _clean(value: Any) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def identify_civil_posture(raw_text: str) -> Dict[str, str]:
    """Return a positive civil pleading posture, or UNKNOWN when unsupported."""
    source = _clean(raw_text)
    # Prefer the opening material to avoid quoted pleading names deep in annexes.
    opening = source[:4000]
    for subtype, pattern, posture in _CIVIL_POSTURES:
        if pattern.search(opening):
            return {"posture": posture, "domain": "PERDATA", "subtype": subtype}
    # Full-corpus fallback requires a civil docket/context anchor.
    if re.search(r"\b(?:pdt\.?g|penggugat|tergugat|pengadilan\s+negeri)\b", source, re.I):
        for subtype, pattern, posture in _CIVIL_POSTURES:
            if pattern.search(source):
                return {"posture": posture, "domain": "PERDATA", "subtype": subtype}
    return {"posture": "Dokumen Hukum", "domain": "UNKNOWN", "subtype": "UNKNOWN"}


def is_civil_pleading_context(*, posture: str = "", corpus: str = "", source_item: Dict[str, Any] | None = None) -> bool:
    item = source_item or {}
    explicit = _clean(item.get("_semantic_context") or item.get("document_context")).upper()
    if explicit in {"CIVIL_PLEADING", "REPLIK", "DUPLIK", "CIVIL_RESPONSE"}:
        return True
    posture_low = _clean(posture).lower()
    if any(x in posture_low for x in ("replik", "duplik", "gugatan", "jawaban perdata", "jawaban gugatan")):
        return True
    return identify_civil_posture(corpus).get("domain") == "PERDATA"


def semantic_override(text: str, *, posture: str = "", corpus: str = "", source_item: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return a conservative existing-SAL-type override for civil pleadings."""
    s = _clean(text)
    if not s or not is_civil_pleading_context(posture=posture, corpus=corpus, source_item=source_item):
        return {"override_type": None, "reason": "NOT_CIVIL_PLEADING_OR_EMPTY", "confidence": 0.0}
    if _PROCEDURAL_FILING.search(s):
        return {
            "override_type": "METADATA",
            "reason": "CIVIL_PLEADING_PROCEDURAL_FILING_NOT_MATERIAL_FACT",
            "confidence": 0.98,
        }
    if _ARGUMENTATIVE.search(s):
        return {
            "override_type": "PARTY_ARGUMENT",
            "reason": "CIVIL_PLEADING_ARGUMENT_OR_DOCTRINE_NOT_OBJECTIVE_FACT",
            "confidence": 0.95,
        }
    return {"override_type": None, "reason": "NO_STRONG_CIVIL_PLEADING_NOISE_PATTERN", "confidence": 0.0}


def _sanitize_string(value: str) -> str:
    out = str(value or "")
    for pattern, replacement in _STRATEGY_REPLACEMENTS:
        out = pattern.sub(replacement, out)
    return out


def sanitize_strategy(value: Any, *, domain: str) -> Any:
    """Return a deep-copied reader-facing strategy with criminal-template leakage removed.

    No ``eval``/serialization round-trip is used.  Container types and non-string
    values are preserved exactly.
    """
    if str(domain or "").upper() != "PERDATA":
        return copy.deepcopy(value)
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, list):
        return [sanitize_strategy(v, domain=domain) for v in value]
    if isinstance(value, tuple):
        return tuple(sanitize_strategy(v, domain=domain) for v in value)
    if isinstance(value, dict):
        return {k: sanitize_strategy(v, domain=domain) for k, v in value.items()}
    return copy.deepcopy(value)
