"""BAP semantic-noise cleaner for SAL v1.0.

This module is deliberately narrow.  It does not rewrite source text and it does
not create evidence.  It only returns a strong semantic-type override when a
fragment from a verified BAP/interrogation corpus has a form that the generic
statement classifier commonly misreads as a factual assertion.

The frozen SAL taxonomy remains authoritative; every returned type is an
existing SAL v1.0 type.
"""
from __future__ import annotations

import re
from typing import Any, Dict

_WS = re.compile(r"\s+")
_QUESTION = re.compile(
    r"^\s*(?:apakah|apa|siapa|kapan|dimana|di\s+mana|mengapa|kenapa|bagaimana|benarkah|"
    r"diperlihatkan\s+kepada\s+saudara|dipertanyakan\s+kepada\s+saudara)\b|\?\s*$",
    re.I,
)

# Deontic/normative language. In a BAP this is often a quoted statutory right,
# a contractual obligation, or a generic rule read to the examinee.  It is not a
# historical event merely because OCR split it away from its Pasal/klausul lead.
_DEONTIC = re.compile(
    r"\b(?:wajib|berhak|dilarang|berwenang|harus|dapat\s+(?:mengajukan|memohon|menolak|didampingi)|"
    r"mengusahakan\s+dan\s+mengajukan\s+saksi)\b",
    re.I,
)
_GENERIC_LEGAL_SUBJECT = re.compile(
    r"\b(?:tersangka|terdakwa|debitur|kreditur|pemohon|termohon|penyidik|penuntut\s+umum|"
    r"penasihat\s+hukum|saksi|ahli|direksi|bank)\b",
    re.I,
)
_CONCRETE_EVENT = re.compile(
    r"\b(?:pada\s+tanggal|tanggal\s+\d|telah\s+(?:membayar|menyerahkan|menandatangani|mencairkan|"
    r"menyetujui|memerintahkan|menerima|menjual|mengalihkan)|kemarin|hari\s+ini\s+telah)\b",
    re.I,
)

# Bare legal-act enumerations produced by OCR line splitting. They describe a
# generic scope of rights/prohibitions rather than an actor's concrete conduct.
_GENERIC_ACT_LIST = re.compile(
    r"^\s*(?:membeli|menjual|mengalihkan|menyerahkan|menerima|mendapatkan|melepaskan)\s*,?\s*"
    r"(?:menjual|membeli|mengalihkan|menyerahkan|menerima|mendapatkan|melepaskan|atau\s+dengan\s+cara\s+lain)",
    re.I,
)


def _clean(value: Any) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def is_bap_context(*, posture: str = "", corpus: str = "", source_item: Dict[str, Any] | None = None) -> bool:
    """Return True only for a positively identified examination/BAP context."""
    item = source_item or {}
    explicit = _clean(item.get("_semantic_context") or item.get("document_context")).upper()
    if explicit in {"BAP", "BAP_INTERROGATION", "INTERROGATION_RECORD"}:
        return True
    hay = f"{_clean(posture)} {_clean(corpus)[:12000]}".lower()
    anchors = (
        "berita acara pemeriksaan tersangka",
        "berita acara pemeriksaan saksi",
        "berita acara pemeriksaan",
    )
    procedural = any(a in hay for a in anchors)
    examiner = any(a in hay for a in ("jaksa penyidik", "penyidik", "telah memeriksa seorang", "pertanyaan penyidik"))
    return procedural and examiner


def classify_bap_noise(text: str, *, bap_context: bool) -> Dict[str, Any]:
    """Return a conservative SAL semantic override for BAP-only noise.

    ``override_type`` is ``None`` when positive proof is insufficient, so the
    generic SAL classifier remains in control.  No raw text is modified.
    """
    s = _clean(text)
    if not bap_context or not s:
        return {"override_type": None, "reason": "NOT_BAP_OR_EMPTY", "confidence": 0.0}

    if _QUESTION.search(s):
        return {
            "override_type": "QUESTION",
            "reason": "BAP_INTERROGATIVE_FORM_POSITIVELY_IDENTIFIED",
            "confidence": 1.0,
        }

    # A concrete dated/completed act wins over deontic wording. This prevents a
    # sentence such as "pada tanggal X debitur telah membayar..." from being
    # flattened into a normative clause merely because it also says "wajib".
    if _CONCRETE_EVENT.search(s):
        return {"override_type": None, "reason": "CONCRETE_EVENT_PRESERVED_FOR_GENERIC_TYPING", "confidence": 0.0}

    if _DEONTIC.search(s) and (_GENERIC_LEGAL_SUBJECT.search(s) or len(s.split()) <= 24):
        return {
            "override_type": "LAW_CITATION",
            "reason": "BAP_DEONTIC_OR_CONTRACTUAL_NORM_FRAGMENT_NOT_HISTORICAL_FACT",
            "confidence": 0.92,
        }

    if _GENERIC_ACT_LIST.search(s):
        return {
            "override_type": "LAW_CITATION",
            "reason": "BAP_GENERIC_LEGAL_ACT_ENUMERATION_NOT_CONCRETE_CONDUCT",
            "confidence": 0.88,
        }

    return {"override_type": None, "reason": "NO_STRONG_BAP_NOISE_PATTERN", "confidence": 0.0}


def semantic_override(text: str, *, posture: str = "", corpus: str = "", source_item: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Convenience entry point used by SAL.

    This is intentionally read-only and bounded: it returns classification hints
    only; SAL remains the authority for routing and admissibility.
    """
    context = is_bap_context(posture=posture, corpus=corpus, source_item=source_item)
    return classify_bap_noise(text, bap_context=context)
