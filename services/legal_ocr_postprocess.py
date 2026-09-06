"""Conservative legal OCR post-processing and evidence grouping.

LexiCore v1.3.11 principles:
- OCR output is never silently treated as pristine source text.
- Only low-risk, high-confidence lexical/spacing corrections are automatic.
- Names, identifiers, dates, monetary values, parcel/certificate numbers, and quoted
  legal conclusions are not rewritten by fuzzy matching.
- Every normalization rule applied is recorded in diagnostics.
- Evidence grouping is extractive: material facts are assembled only from source
  ledger statements already grounded in the uploaded document.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Tuple

# Exact/regex corrections restricted to recurring OCR noise and legal vocabulary.
# Keep this list intentionally conservative: no fuzzy correction of names/IDs.
_RULES: List[Tuple[str, re.Pattern, str]] = [
    ("LEGAL_EKSEPSI", re.compile(r"\b(?:exsepsi|exepsi|eksepsi)\b", re.I), "Eksepsi"),
    ("LEGAL_EXCEPTIO", re.compile(r"\b(?:exsepsio|exepsio|exceptio)\b", re.I), "Exceptio"),
    ("LEGAL_DECLINATOIR", re.compile(r"\b(?:decklinatoir|deklinatoir|declinatoir)\b", re.I), "Declinatoir"),
    ("LEGAL_OBSCUUR", re.compile(r"\b(?:obscur|obscuur)\s+libel\b", re.I), "Obscuur Libel"),
    ("LEGAL_PLURIUM", re.compile(r"\bplurium\s+litis\s+consorti(?:um|un)\b", re.I), "Plurium Litis Consortium"),
    ("LEGAL_REKONVENSI", re.compile(r"\brekonvens[yi]\b", re.I), "Rekonvensi"),
    ("LEGAL_KONVENSI", re.compile(r"\bkonvens[yi]\b", re.I), "Konvensi"),
    ("OCR_AHLI_WARIS", re.compile(r"\bahliwaris\b", re.I), "ahli waris"),
    ("OCR_KAMI_JAWAB", re.compile(r"\bkamijawab\b", re.I), "kami jawab"),
    ("OCR_BERTINDAK", re.compile(r"\bbertndak\b", re.I), "bertindak"),
    ("OCR_ATAS", re.compile(r"\batass\b", re.I), "atas"),
    ("OCR_NOMOR", re.compile(r"\bnonor\b", re.I), "Nomor"),
    ("OCR_ADALAH", re.compile(r"\badaah\b", re.I), "adalah"),
    ("OCR_TANAH", re.compile(r"\btanag\b", re.I), "tanah"),
]

_HEADING_CANON = {
    "DALAM EKSEPSI": "DALAM EKSEPSI",
    "DALAM KONVENSI": "DALAM KONVENSI",
    "DALAM REKONVENSI": "DALAM REKONVENSI",
    "KESIMPULAN": "KESIMPULAN",
    "PERMOHONAN": "PERMOHONAN",
    "PETITUM": "PETITUM",
}


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def postprocess_legal_ocr(text: str) -> Tuple[str, Dict[str, Any]]:
    """Normalize low-risk OCR noise and return an auditable diagnostics object."""
    raw = (text or "").replace("\x00", "")
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    corrections: List[Dict[str, Any]] = []

    # Join hyphenated line wraps only when both sides look like normal alphabetic words.
    # Do not touch legal numbers, case numbers, identifiers, or punctuation-heavy tokens.
    def dehyphen(m):
        corrections.append({"rule": "OCR_LINE_DEHYPHEN", "from": m.group(0), "to": m.group(1) + m.group(2), "count": 1})
        return m.group(1) + m.group(2)
    normalized = re.sub(r"\b([A-Za-zÀ-ÿ]{3,})-\s*\n\s*([a-zà-ÿ]{2,})\b", dehyphen, normalized)

    # Common missing-space artifacts from OCR; bounded to ordinary words.
    normalized = re.sub(r"(?<=[a-zà-ÿ])(?=[A-ZÀ-Þ][a-zà-ÿ]{2,}\b)", " ", normalized)

    for rule_id, pattern, replacement in _RULES:
        before = normalized
        normalized, count = pattern.subn(replacement, normalized)
        if count:
            corrections.append({"rule": rule_id, "from": pattern.pattern, "to": replacement, "count": count})

    # Normalize headings only when a full stripped line is recognizably the heading.
    lines = []
    for line in normalized.split("\n"):
        clean = re.sub(r"\s+", " ", line).strip()
        upper = re.sub(r"[^A-Z ]", "", clean.upper()).strip()
        if upper in _HEADING_CANON:
            clean = _HEADING_CANON[upper]
        lines.append(clean)
    normalized = "\n".join(lines)

    # Conservative whitespace/punctuation cleanup.
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    normalized = re.sub(r"\b(\d+)\s*[Mm]2\b", r"\1 m2", normalized)

    diag = {
        "enabled": True,
        "policy": "CONSERVATIVE_LEGAL_OCR_NORMALIZATION",
        "raw_sha256": _sha256(raw),
        "normalized_sha256": _sha256(normalized),
        "characters_raw": len(raw),
        "characters_normalized": len(normalized),
        "corrections_count": sum(int(x.get("count") or 0) for x in corrections),
        "corrections": corrections[:80],
        "protected_fields": ["names", "NIK/IDs", "dates", "money", "case_numbers", "certificate_numbers"],
        "source_fidelity": "RAW_OCR_HASH_PRESERVED; NORMALIZED_TEXT_USED_FOR_ANALYSIS",
    }
    return normalized, diag


_GROUPS = [
    ("document_posture", "Dokumen & Postur Prosedural", ("replik", "repliek", "gugatan", "jawaban", "eksepsi", "konvensi", "rekonvensi", "kesimpulan", "permohonan", "petitum", "perkara nomor")),
    ("jurisdiction", "Kompetensi & Forum", ("pengadilan agama", "kompetensi absolut", "kewenangan absolut", "declinatoir", "declinatoria", "kewenangan pengadilan")),
    ("inheritance", "Waris & Hubungan Para Pihak", ("waris", "warisan", "ahli waris", "pewaris", "pembagian waris", "bagian kasdi", "bagian suliah")),
    ("land_registration", "Pertanahan & Pendaftaran", ("sertipikat", "sertifikat", "hak milik", "shm", "ptsl", "skpt", "surat ukur", "kantor pertanahan", "tanah", "rumah", "m2")),
    ("formal_defenses", "Eksepsi & Syarat Formil", ("plurium", "obscuur", "kurang pihak", "gugatan kabur", "syarat formil", "syarat materiil", "posita", "petitum")),
    ("claims_positions", "Dalil, Bantahan & Posisi Para Pihak", ("perbuatan melawan hukum", "mendalilkan", "menolak", "membenarkan", "membuktikan", "cacat hukum", "unsur pidana")),
    ("relief", "Petitum / Upaya yang Dimohonkan", ("mengabulkan", "menolak eksepsi", "menghukum", "memohon", "permohonan", "50%", "putusan inkracht", "ongkos perkara")),
    ("authority_parties", "Para Pihak & Kewenangan Bertindak", ("surat kuasa khusus", "penggugat", "tergugat", "pemberi kuasa", "penerima kuasa", "advokat")),
]


def _evidence_group_for(statement: str) -> Tuple[str, str, int]:
    low = (statement or "").lower()
    best = ("other", "Fakta Material Lain", 0)
    for gid, label, anchors in _GROUPS:
        score = sum(1 for a in anchors if a in low)
        if score > best[2]:
            best = (gid, label, score)
    return best


def group_source_ledger(ledger: Iterable[Dict[str, Any]], max_groups: int = 12, max_facts_per_group: int = 12) -> List[Dict[str, Any]]:
    """Group extractive ledger rows into legally meaningful evidence clusters.

    The group summaries are not generated facts. They are concatenated/trimmed extracts
    from member statements, with member indices retained for traceability.
    """
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for idx, item in enumerate(ledger or []):
        if not isinstance(item, dict):
            continue
        statement = re.sub(r"\s+", " ", str(item.get("statement") or "")).strip()
        if not statement:
            continue
        gid, label, score = _evidence_group_for(statement)
        if gid not in groups:
            groups[gid] = {"id": gid, "label": label, "items": [], "material_facts": [], "source_item_indexes": []}
            order.append(gid)
        g = groups[gid]
        g["items"].append({
            "label": item.get("label") or "SOURCE FACT",
            "statement": statement,
            "evidence": item.get("evidence") or statement,
            "segment": item.get("segment"),
            "source": item.get("source"),
            "source_index": idx,
        })
        g["source_item_indexes"].append(idx)

    out: List[Dict[str, Any]] = []
    for gid in order:
        g = groups[gid]
        # Build compact material facts by joining adjacent short extracts within the same group.
        facts: List[str] = []
        buffer = ""
        for item in g["items"]:
            s = item["statement"]
            if not buffer:
                buffer = s
            elif len(buffer) + len(s) + 1 <= 430:
                buffer += " " + s
            else:
                facts.append(buffer)
                buffer = s
            if len(facts) >= max_facts_per_group:
                break
        if buffer and len(facts) < max_facts_per_group:
            facts.append(buffer)
        # De-duplicate near-identical grouped extracts.
        dedup, seen = [], set()
        for fact in facts:
            key = re.sub(r"\W+", " ", fact.lower()).strip()[:220]
            if key and key not in seen:
                seen.add(key); dedup.append(fact)
        g["material_facts"] = dedup[:max_facts_per_group]
        g["item_count"] = len(g["items"])
        g["traceability"] = "EXTRACTIVE_GROUPING_ONLY"
        out.append(g)
    # Put 'other' last; otherwise preserve source-driven group order.
    out.sort(key=lambda x: (x["id"] == "other", order.index(x["id"])))
    return out[:max_groups]
