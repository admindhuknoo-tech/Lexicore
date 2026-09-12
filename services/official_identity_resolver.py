"""LexiCore exact-identity metadata resolver for official search candidates.

This module is intentionally metadata-only. It never upgrades a candidate to
verified law. Final identity remains fail-closed in legal_sources.resolve_official_fulltext().
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_ID_RE = re.compile(r'^(UU|PP|PERPU|PERPPU|PERMA|SEMA|PERPRES|POJK|SEOJK):([0-9]+[A-Za-z]?):((?:19|20)\d{2})$', re.I)


def _parts(key: str | None):
    m = _ID_RE.fullmatch(str(key or '').strip())
    if not m:
        return None
    return m.group(1).upper(), m.group(2).upper(), m.group(3)


def exact_query_variants(identity_key: str | None) -> list[str]:
    """Return bounded exact-identity query variants, strongest first."""
    p = _parts(identity_key)
    if not p:
        return []
    kind, number, year = p
    labels = {
        'UU': 'Undang-Undang', 'PP': 'Peraturan Pemerintah', 'PERPU':'Peraturan Pemerintah Pengganti Undang-Undang', 'PERPPU':'Peraturan Pemerintah Pengganti Undang-Undang',
        'PERMA': 'Peraturan Mahkamah Agung', 'SEMA': 'Surat Edaran Mahkamah Agung',
        'PERPRES': 'Peraturan Presiden', 'POJK': 'Peraturan Otoritas Jasa Keuangan',
        'SEOJK': 'Surat Edaran Otoritas Jasa Keuangan',
    }
    label = labels[kind]
    return [
        f'{label} Nomor {number} Tahun {year}',
        f'{kind} {number}/{year}',
        f'{kind}:{number}:{year}',
    ]




def _identity_from_url(url: str | None) -> str | None:
    """Extract an instrument identity from a structured official URL."""
    s = str(url or '').strip()
    if not s:
        return None
    patterns = [
        (r'(?:^|[/_-])uu-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])', 'UU'),
        (r'(?:^|[/_-])pp-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])', 'PP'),
        (r'(?:^|[/_-])(?:perpu|perppu)-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])', 'PERPU'),
        (r'(?:^|[/_-])perpres-no-([0-9]+[A-Za-z]?)-tahun-((?:19|20)\d{2})(?:$|[/?#._-])', 'PERPRES'),
    ]
    for pat, kind in patterns:
        m = re.search(pat, s, re.I)
        if m:
            return f'{kind}:{m.group(1).upper()}:{m.group(2)}'
    return None

def _identity_from_text(text: str | None) -> str | None:
    """Extract the earliest explicit primary instrument identity in metadata.

    Embedded ``Undang-Undang`` inside a PERPU title is not promoted to an outer
    UU identity. This prevents reference-only instruments from becoming exact
    candidates in unrelated domains.
    """
    s = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not s:
        return None
    matches=[]
    patterns=[
        (r'\bPeraturan Pemerintah Pengganti Undang[- ]Undang\s*(?:Nomor|No\.?)\s*([0-9]+[A-Za-z]?)\s*Tahun\s*((?:19|20)\d{2})\b','PERPU'),
        (r'\bPERP?U\s*(?:Nomor|No\.?)?\s*([0-9]+[A-Za-z]?)\s*(?:Tahun\s*)?((?:19|20)\d{2})\b','PERPU'),
        (r'\bPeraturan Pemerintah\s*(?:Nomor|No\.?)\s*([0-9]+[A-Za-z]?)\s*Tahun\s*((?:19|20)\d{2})\b','PP'),
        (r'\bPP\s*(?:Nomor|No\.?)?\s*([0-9]+[A-Za-z]?)\s*(?:Tahun\s*)?((?:19|20)\d{2})\b','PP'),
        (r'\bUndang[- ]Undang(?: Republik Indonesia)?\s*(?:Nomor|No\.?)\s*([0-9]+[A-Za-z]?)\s*Tahun\s*((?:19|20)\d{2})\b','UU'),
        (r'\bUU\s*(?:Nomor|No\.?)?\s*([0-9]+[A-Za-z]?)\s*(?:Tahun\s*)?((?:19|20)\d{2})\b','UU'),
    ]
    for pat,kind in patterns:
        for m in re.finditer(pat,s,re.I):
            if kind=='UU':
                prefix=s[max(0,m.start()-55):m.start()].lower()
                if re.search(r'peraturan pemerintah pengganti\s*$',prefix):
                    continue
            matches.append((m.start(),f'{kind}:{m.group(1).upper()}:{m.group(2)}'))
    for m in re.finditer(r'\b(UU|PP|PERPU|PERPPU|PERMA|SEMA|PERPRES|POJK|SEOJK)\s*:\s*([0-9]+[A-Za-z]?)\s*:\s*((?:19|20)\d{2})\b',s,re.I):
        kind=m.group(1).upper().replace('PERPPU','PERPU')
        matches.append((m.start(),f'{kind}:{m.group(2).upper()}:{m.group(3)}'))
    for m in re.finditer(r'\b(UU|PP|PERPU|PERPPU|PERMA|SEMA|PERPRES|POJK|SEOJK)\s*([0-9]+[A-Za-z]?)\s*/\s*((?:19|20)\d{2})\b',s,re.I):
        kind=m.group(1).upper().replace('PERPPU','PERPU')
        matches.append((m.start(),f'{kind}:{m.group(2).upper()}:{m.group(3)}'))
    if not matches:
        return None
    matches.sort(key=lambda x:x[0])
    return matches[0][1]


@dataclass(frozen=True)
class RankedCandidate:
    score: int
    source_id: str | None
    row: dict
    title_identity: str | None
    reason: str


def rank_candidates(expected_identity_key: str | None, rows: Iterable[tuple[str | None, dict]]) -> list[RankedCandidate]:
    """Rank metadata before network fetch.

    An explicit different identity in the title is a hard reject. References in
    snippets/descriptions can only help when the title itself is identity-ambiguous.
    """
    expected = str(expected_identity_key or '').strip().upper()
    out: list[RankedCandidate] = []
    for source_id, row in rows:
        title = str((row or {}).get('title') or '')
        url = str((row or {}).get('url') or '')
        title_text_id = _identity_from_text(title)
        url_id = _identity_from_url(url)

        # R24: when a structured official URL encodes the instrument identity,
        # use it as the primary metadata identity.  This prevents amendment
        # titles such as "Perubahan Atas UU 31/1999" from being misclassified
        # as the amended/base law when the URL identifies the actual instrument
        # as UU 20/2001.
        title_id = url_id or title_text_id
        relevance = float((row or {}).get('relevance_score') or 0.0)
        source_bonus = -100 if source_id == 'local_corpus' else 0
        if expected and title_id:
            if title_id != expected:
                continue
            score = 1000 + source_bonus + min(99, int(relevance * 10))
            out.append(RankedCandidate(score, source_id, row, title_id, 'EXACT_TITLE_IDENTITY'))
            continue
        aux = ' '.join(str((row or {}).get(k) or '') for k in ('description','snippet','summary','query'))
        aux_id = _identity_from_text(aux)
        if expected and aux_id == expected:
            score = 300 + source_bonus + min(99, int(relevance * 10))
            out.append(RankedCandidate(score, source_id, row, title_id, 'AUX_EXPECTED_IDENTITY'))
        else:
            out.append(RankedCandidate(100 + source_bonus + min(99, int(relevance * 10)), source_id, row, title_id, 'AMBIGUOUS_METADATA'))
    out.sort(key=lambda x: x.score, reverse=True)
    return out
