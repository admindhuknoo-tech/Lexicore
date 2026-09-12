"""Fail-closed material tempus candidate extraction for LexiCore RC18.

This module discovers date/year candidates tied to alleged material events. It
never decides legal applicability and never promotes procedural, statute,
object/model, or document-number dates into material tempus.

RC18 Tempus Extraction Closure strengthens OCR-heavy legal documents by:
- treating an explicit full/numeric date as a temporal anchor even when OCR
  omits words such as ``tanggal``;
- evaluating short adjacent OCR lines as one context window so an event cue and
  its date can survive line breaks;
- ranking alleged-conduct events above office/status events, while keeping
  office/status events material when they are the actual disputed event;
- preserving a strict fail-closed result when several competing material dates
  of the same priority remain.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Tuple

_MONTHS = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11,
    'desember': 12,
}

# Tier A: alleged/substantive conduct.  If exactly one defensible Tier-A date
# exists, unrelated office/status chronology must not make tempus ambiguous.
_CONDUCT_EVENT_CUES = (
    'perbuatan', 'melakukan', 'dilakukan', 'terjadi', 'kejadian', 'pelanggaran',
    'melanggar', 'transaksi', 'pencairan', 'perjanjian kredit', 'pemberian kredit', 'persetujuan kredit',
    'kredit diberikan', 'kredit dicairkan', 'menyetujui kredit',
    'menandatangani perjanjian', 'menandatangani kontrak',
    'wanprestasi', 'cidera janji', 'jatuh tempo', 'tidak membayar', 'gagal membayar',
    'pemutusan hubungan kerja', 'phk', 'mulai bekerja', 'hubungan kerja',
    'upah tidak dibayar', 'membayar', 'pembayaran', 'menyerahkan', 'menerima uang',
    'memberikan uang', 'memerintahkan', 'menggunakan', 'mengalihkan', 'menguasai',
    'menetapkan keputusan', 'menerbitkan keputusan',
)

# Tier B: status/office events.  These are material in electoral/ethics and
# administrative disputes where qualification/office status at a point in time
# is itself disputed.
_STATUS_EVENT_CUES = (
    'mengundurkan diri', 'pengunduran diri', 'menerima pengunduran diri',
    'diangkat', 'pengangkatan', 'ditetapkan sebagai', 'penetapan sebagai',
    'terpilih menjadi', 'memberhentikan', 'diberhentikan', 'pemberhentian',
    'mulai menjabat', 'menjabat sebagai', 'berhenti menjabat', 'berakhir masa jabatan',
    'kepengurusan', 'pengurus', 'susunan personalia', 'pelantikan',
)

_EVENT_CUES = _CONDUCT_EVENT_CUES + _STATUS_EVENT_CUES
_TIME_CUES = (
    'tanggal', 'pada tahun', 'pada tanggal', 'bulan', 'periode', 'sejak',
    'antara', 'sampai dengan', 'hingga', 'sekitar tahun', 'terhitung sejak',
)
_OBJECT_CUES = (
    'mobil', 'kendaraan', 'honda', 'jazz', 'nomor polisi', 'tahun produksi',
    'model kendaraan', 'barang jaminan', 'agunan', 'bpkb',
)
_STATUTE_CUES = (
    'undang-undang', ' uu ', 'pasal ', 'pojk', 'seojk', 'peraturan pemerintah',
    'perma', 'sema', ' berlaku ', 'diundangkan', 'lembaran negara',
)
_PROCEDURAL_CUES = (
    'nomor perkara', 'pid.sus', 'persidangan', 'sidang', 'berita acara pemeriksaan',
    'bap', 'pemeriksaan', 'surat dakwaan', 'surat kuasa', 'kepaniteraan',
    'gugatan diajukan', 'permohonan diajukan', 'nomor pengaduan', 'laporan dugaan',
    'pengaduan diajukan', 'pengaduan diterima', 'laporan diajukan',
    'registrasi perkara', 'putusan dibacakan', 'putusan diucapkan',
)
_DOCUMENT_DATE_CUES = (
    'ditandatangani pada', 'dokumen dibuat', 'surat dibuat', 'tanggal surat',
    'meterai', 'materai', 'oct ', 'sep ', 'aug ', 'jul ', 'jun ', 'may ',
    'apr ', 'mar ', 'feb ', 'jan ',
)

_FULL_DATE_RE = re.compile(
    r'(?<!\d)(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(19\d{2}|20\d{2})(?!\d)',
    re.I,
)
_NUMERIC_DATE_RE = re.compile(r'(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](19\d{2}|20\d{2})(?!\d)')
_YEAR_RE = re.compile(r'\b(19\d{2}|20\d{2})\b')


def _sentences(text: str) -> List[str]:
    """Return OCR-tolerant context windows, not merely isolated lines.

    OCR often puts an event cue and its date on adjacent lines.  We retain each
    logical sentence and also a bounded two-segment window.  Deduplication later
    removes repeated date candidates.
    """
    raw_parts = [
        s.strip()
        for s in re.split(r'(?<=[.!?;])\s+|[\r\n]+', str(text or ''))
        if s.strip()
    ]
    out: List[str] = []
    seen = set()
    for idx, part in enumerate(raw_parts):
        candidates = [part]
        if idx + 1 < len(raw_parts):
            nxt = raw_parts[idx + 1]
            # Merge only when at least one side lacks an explicit date.  If
            # both sides already carry dates, merging would let an event cue
            # from one sentence incorrectly promote the other sentence's
            # procedural/regulatory date.
            part_has_date = _explicit_temporal_anchor(part)
            next_has_date = _explicit_temporal_anchor(nxt)

            # Do not let a date that is already owned by an explicitly
            # procedural sentence be re-labelled as material merely because
            # the adjacent sentence contains a generic conduct cue.  This is
            # the common pattern in pleadings such as:
            #   "Surat dakwaan ... persidangan tanggal 31 Agustus 2026."
            #   "Perbuatan didakwakan melanggar UU ..."
            # The hearing date belongs to the procedural event, not to the
            # alleged act.  We still merge the inverse OCR pattern where an
            # event line is followed by a bare date line.
            part_low = f' {part.lower()} '
            next_low = f' {nxt.lower()} '
            part_procedural = any(cue in part_low for cue in _PROCEDURAL_CUES)
            next_procedural = any(cue in next_low for cue in _PROCEDURAL_CUES)
            part_event = _event_tier(part_low)[0] > 0
            next_event = _event_tier(next_low)[0] > 0
            procedural_date_handoff = (
                (part_has_date and part_procedural and next_event and not next_has_date)
                or (next_has_date and next_procedural and part_event and not part_has_date)
            )

            merged = f'{part} {nxt}'.strip()
            if (
                len(merged) <= 700
                and not (part_has_date and next_has_date)
                and not procedural_date_handoff
            ):
                candidates.append(merged)
        for candidate in candidates:
            key = re.sub(r'\s+', ' ', candidate).strip()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out


def _date_iso(day: int, month: int, year: int) -> str | None:
    try:
        return datetime(year, month, day).strftime('%Y-%m-%d')
    except ValueError:
        return None


def _normalize_ocr_day(text: str) -> str:
    months = '|'.join(m.title() for m in _MONTHS)

    def repl(match):
        day = int(match.group(1) + match.group(2))
        return f'{day} {match.group(3)} {match.group(4)}' if 1 <= day <= 31 else match.group(0)

    normalized = re.sub(
        rf'(?<!\d)([0-3])\s+([0-9])\s+({months})\s+(20\d{{2}})(?!\d)',
        repl,
        text or '',
        flags=re.I,
    )
    # OCR may break a normal date across line boundaries.  Collapse whitespace
    # only around date tokens; do not flatten the entire document.
    normalized = re.sub(
        rf'(?<!\d)(\d{{1,2}})\s*[\r\n]+\s*({months})\s*[\r\n]+\s*(19\d{{2}}|20\d{{2}})(?!\d)',
        r'\1 \2 \3',
        normalized,
        flags=re.I,
    )
    return normalized


def _explicit_temporal_anchor(sentence: str) -> bool:
    return bool(_FULL_DATE_RE.search(sentence) or _NUMERIC_DATE_RE.search(sentence))


def _year_is_statute_identity(sentence: str, match: re.Match) -> bool:
    """Return True when a year token belongs to a legal-instrument identity.

    This is candidate-local on purpose.  A sentence can legitimately mention an
    alleged act and a statute in the same breath (for example, "Perbuatan
    didakwakan melanggar Undang-Undang Nomor 31 Tahun 1999").  The sentence may
    therefore contain a material-event cue, but the year 1999 still belongs to
    the statute identity and must never become tempus delicti.
    """
    prefix = sentence[max(0, match.start() - 140):match.start()].lower()
    instrument = r'(?:undang-undang|uu|perpu|perppu|peraturan(?:\s+[a-z-]+){0,3}|pp|perpres|pojk|seojk|perma|sema)'
    return bool(
        re.search(rf'\b{instrument}\b[^.;\n]{{0,100}}\btahun\s*$', prefix, re.I)
        or re.search(rf'\b{instrument}\b[^.;\n]{{0,80}}/\s*$', prefix, re.I)
    )


def _event_tier(low: str) -> Tuple[int, List[str]]:
    conduct = [cue for cue in _CONDUCT_EVENT_CUES if cue in low]
    status = [cue for cue in _STATUS_EVENT_CUES if cue in low]
    if conduct:
        return 2, conduct
    if status:
        return 1, status
    return 0, []


def _classify_sentence(sentence: str) -> tuple[str, int, list[str], int]:
    low = f' {sentence.lower()} '
    reasons: List[str] = []
    score = 0
    tier, event_hits = _event_tier(low)
    time_hits = [cue for cue in _TIME_CUES if cue in low]
    explicit_date = _explicit_temporal_anchor(sentence)

    if event_hits:
        score += 14 if tier == 2 else 12
        # Multiple independent event expressions in the same bounded context
        # strengthen ownership of the date without introducing domain rules.
        # Example: "mengundurkan diri dan diberhentikan ... sejak tanggal X"
        # is stronger than a bare document date that only happens to sit near
        # one status word.  Cap the uplift so repeated OCR text cannot dominate.
        score += min(6, max(0, len(set(event_hits)) - 1) * 2)
        if len(set(event_hits)) > 1:
            reasons.append('corroborating_event_cues')
        reasons.append('material_conduct_cue' if tier == 2 else 'material_status_cue')
    if time_hits:
        score += 8
        reasons.append('temporal_cue')
    lifecycle_anchors = [
        cue for cue in ('resmi mengundurkan diri', 'diberhentikan dengan hormat',
                        'menerima pengunduran diri', 'terhitung sejak', 'sejak tanggal')
        if cue in low
    ]
    if lifecycle_anchors:
        score += min(8, 2 * len(set(lifecycle_anchors)))
        reasons.append('explicit_lifecycle_anchor')
    if explicit_date:
        # A full/numeric date is itself a strong temporal anchor.  This repairs
        # OCR/legal drafting such as "mengundurkan diri 16 Januari 2018" where
        # the word "tanggal" is absent.
        score += 7
        reasons.append('explicit_temporal_anchor')

    object_context = any(cue in low for cue in _OBJECT_CUES)
    statute_hits = sum(1 for cue in _STATUTE_CUES if cue in low)
    procedural_context = any(cue in low for cue in _PROCEDURAL_CUES)
    document_context = any(cue in low for cue in _DOCUMENT_DATE_CUES)

    if object_context:
        score -= 20
        reasons.append('object_or_model_context')
    if statute_hits >= 2:
        score -= 18
        reasons.append('statute_context')
    # Procedural context remains disqualifying unless a genuine material event
    # is explicitly present in the same local context.  This lets a BAP quote
    # contain the alleged act date without promoting the BAP examination date.
    if procedural_context and not event_hits:
        score -= 18
        reasons.append('procedural_context')
    if document_context and not event_hits:
        score -= 10
        reasons.append('document_date_context')

    if re.search(
        r'(mengundurkan diri|pengunduran diri|diangkat|pengangkatan|ditetapkan sebagai|terpilih menjadi|memberhentikan|diberhentikan|pemberhentian|mulai menjabat|menjabat sebagai|melakukan|dilakukan|pelanggaran|transaksi|pencairan)[^.;\n]{0,100}\b(?:tanggal|sejak|pada)\b',
        low,
        re.I,
    ):
        score += 8
        reasons.append('direct_material_date_grammar')

    has_temporal_anchor = bool(time_hits or explicit_date)
    if event_hits and has_temporal_anchor and score >= 15:
        return 'material_event', score, reasons, tier
    if 'procedural_context' in reasons:
        return 'procedural', score, reasons, 0
    if 'statute_context' in reasons:
        return 'regulation', score, reasons, 0
    if 'object_or_model_context' in reasons:
        return 'object_or_record', score, reasons, 0
    if 'document_date_context' in reasons:
        return 'document_or_stamp', score, reasons, 0
    return 'unknown', score, reasons, 0


def _append_candidate(rows: List[Dict], *, value: str, precision: str, year: int,
                      role: str, score: int, reasons: List[str], context: str,
                      event_tier: int) -> None:
    rows.append({
        'value': value,
        'precision': precision,
        'year': year,
        'role': role,
        'score': score,
        'event_tier': event_tier,
        'reasons': list(reasons),
        'context': context[:500],
    })


def extract_material_tempus_candidates(text: str, limit: int = 20) -> List[Dict]:
    """Return ranked candidate dates/years with provenance and role.

    Discovery is intentionally broader than promotion: callers may only promote
    role=material_event candidates that satisfy their own confidence threshold.
    """
    raw = _normalize_ocr_day(str(text or ''))
    rows: List[Dict] = []
    now_year = datetime.now().year

    for sentence in _sentences(raw):
        role, base_score, reasons, event_tier = _classify_sentence(sentence)

        # Full Indonesian dates.
        for match in _FULL_DATE_RE.finditer(sentence):
            month = _MONTHS.get(match.group(2).lower())
            if not month:
                continue
            year = int(match.group(3))
            iso = _date_iso(int(match.group(1)), month, year)
            if not iso or year > now_year:
                continue
            _append_candidate(
                rows,
                value=iso,
                precision='date',
                year=year,
                role=role,
                score=base_score + 5,
                reasons=reasons + ['explicit_full_date'],
                context=sentence,
                event_tier=event_tier,
            )

        # Numeric dates.
        for match in _NUMERIC_DATE_RE.finditer(sentence):
            year = int(match.group(3))
            iso = _date_iso(int(match.group(1)), int(match.group(2)), year)
            if not iso or year > now_year:
                continue
            _append_candidate(
                rows,
                value=iso,
                precision='date',
                year=year,
                role=role,
                score=base_score + 5,
                reasons=reasons + ['explicit_numeric_date'],
                context=sentence,
                event_tier=event_tier,
            )

        # Year-only candidates require explicit temporal language.  A bare year
        # is too weak because legal files contain statute years, model years,
        # document numbers and publication years in abundance.
        if any(cue in sentence.lower() for cue in _TIME_CUES):
            for match in _YEAR_RE.finditer(sentence):
                year = int(match.group(1))
                if year < 1945 or year > now_year:
                    continue
                # A statute year is identity metadata, not a material-event
                # date, even when the surrounding sentence contains words such
                # as "perbuatan" or "melanggar".  Keep this exclusion at
                # candidate level so a genuine event date elsewhere in the same
                # context remains eligible.
                if _year_is_statute_identity(sentence, match):
                    continue
                _append_candidate(
                    rows,
                    value=str(year),
                    precision='year',
                    year=year,
                    role=role,
                    score=base_score,
                    reasons=reasons + ['explicit_year'],
                    context=sentence,
                    event_tier=event_tier,
                )

    # Deduplicate.  A two-line OCR window may repeat the same date found in a
    # one-line context.  Keep the strongest/provenance-rich representation.
    best: Dict[tuple, Dict] = {}
    for row in rows:
        key = (row['value'], row['role'], row['precision'], row.get('event_tier', 0))
        previous = best.get(key)
        if previous is None or (row['score'], len(row['context'])) > (previous['score'], len(previous['context'])):
            best[key] = row

    out = sorted(
        best.values(),
        key=lambda row: (
            row['role'] == 'material_event',
            row.get('event_tier', 0),
            row['score'],
            row['precision'] == 'date',
            row['value'],
        ),
        reverse=True,
    )
    return out[:max(1, int(limit or 20))]


def _top_material_tier(material: List[Dict]) -> List[Dict]:
    """Return only the highest-priority defensible material-event tier.

    A unique alleged-conduct date should not become ambiguous merely because the
    file also records appointment/resignation history.  Conversely, if the case
    contains no alleged-conduct date, office/status events remain eligible and
    competing status dates still fail closed.
    """
    if not material:
        return []
    tier = max(int(row.get('event_tier', 0) or 0) for row in material)
    return [row for row in material if int(row.get('event_tier', 0) or 0) == tier]


def select_material_tempus(text: str) -> Dict:
    """Select one defensible candidate or fail closed as UNKNOWN/AMBIGUOUS.

    Exact date outranks year.  Multiple competing dates within the same highest
    materiality tier remain ambiguous rather than being guessed.  Extraction
    never sets ``tempus_verified`` or ``applicable``.
    """
    candidates = extract_material_tempus_candidates(text)
    all_material = [row for row in candidates if row['role'] == 'material_event' and row['score'] >= 15]

    # Lifecycle/status transitions with direct date ownership are allowed to
    # establish the temporal anchor before materiality-tier pruning.  This is
    # deliberately domain-neutral: resignation, termination, appointment,
    # commencement, and similar state transitions can be the legally decisive
    # date even when the surrounding document repeatedly mentions an alleged
    # violation.  Ordinary competing conduct dates (e.g. credit approval vs
    # disbursement) remain fail-closed.
    lifecycle_by_value = {}
    for row in all_material:
        if row.get('precision') != 'date' or 'explicit_lifecycle_anchor' not in set(row.get('reasons') or []):
            continue
        prev = lifecycle_by_value.get(row['value'])
        if prev is None or row['score'] > prev['score']:
            lifecycle_by_value[row['value']] = row
    lifecycle_ranked = sorted(lifecycle_by_value.values(), key=lambda item: item['score'], reverse=True)
    if len(lifecycle_ranked) == 1:
        row = lifecycle_ranked[0]
        competing_exact_values = {
            item['value'] for item in all_material
            if item.get('precision') == 'date' and item.get('value') != row.get('value')
        }
        return {
            'status': 'MATERIAL_TEMPUS_CANDIDATE',
            'value': row['value'],
            'precision': 'date',
            'confidence': 'HIGH_CANDIDATE',
            'candidate': row,
            'candidates': candidates,
            'material_timeline': sorted(all_material, key=lambda item: item['score'], reverse=True),
            'selection_basis': (
                'STRONGEST_EVENT_DATE_OWNERSHIP'
                if competing_exact_values
                else 'UNIQUE_MATERIAL_EVENT_DATE'
            ),
        }
    if len(lifecycle_ranked) > 1 and lifecycle_ranked[0]['score'] >= lifecycle_ranked[1]['score'] + 8:
        row = lifecycle_ranked[0]
        return {
            'status': 'MATERIAL_TEMPUS_CANDIDATE',
            'value': row['value'],
            'precision': 'date',
            'confidence': 'HIGH_CANDIDATE',
            'candidate': row,
            'candidates': candidates,
            'material_timeline': sorted(all_material, key=lambda item: item['score'], reverse=True),
            'selection_basis': 'STRONGEST_EVENT_DATE_OWNERSHIP',
        }

    material = _top_material_tier(all_material)

    exact = [row for row in material if row['precision'] == 'date']
    if exact:
        # Prefer a uniquely strongest event-owned date.  This is not a domain
        # priority: strength comes from the local event/date relationship.
        # Equal-strength competing material dates still fail closed.
        best_by_value = {}
        for row in exact:
            prev = best_by_value.get(row['value'])
            if prev is None or row['score'] > prev['score']:
                best_by_value[row['value']] = row
        ranked = sorted(best_by_value.values(), key=lambda item: item['score'], reverse=True)
        if len(ranked) == 1:
            row = ranked[0]
            return {
                'status': 'MATERIAL_TEMPUS_CANDIDATE',
                'value': row['value'],
                'precision': 'date',
                'confidence': 'HIGH_CANDIDATE',
                'candidate': row,
                'candidates': candidates,
                'material_timeline': ranked,
                # Preserve the established public/test contract.
                'selection_basis': 'UNIQUE_MATERIAL_EVENT_DATE',
            }

        # Multiple event-owned dates in the same materiality tier are normally
        # ambiguous.  Do not let incidental scoring differences (for example
        # "pencairan kredit" vs "pemberian kredit") silently choose one
        # legal tempus.  A strongest candidate is accepted only when its local
        # text contains an explicit lifecycle anchor and it materially outranks
        # the runner-up.  This remains domain-neutral: the rule is about the
        # strength of date/event ownership, not the forum or case label.
        top, runner_up = ranked[0], ranked[1]
        top_reasons = set(top.get('reasons') or [])
        if (
            'explicit_lifecycle_anchor' in top_reasons
            and top['score'] >= runner_up['score'] + 8
        ):
            return {
                'status': 'MATERIAL_TEMPUS_CANDIDATE',
                'value': top['value'],
                'precision': 'date',
                'confidence': 'HIGH_CANDIDATE',
                'candidate': top,
                'candidates': candidates,
                'material_timeline': ranked,
                'selection_basis': 'STRONGEST_EVENT_DATE_OWNERSHIP',
            }

        return {
            'status': 'MATERIAL_TEMPUS_AMBIGUOUS',
            'value': None,
            'precision': None,
            'confidence': 'NONE',
            'candidates': candidates,
            'material_timeline': ranked,
            # Preserve the established public/test contract.
            'selection_basis': 'MULTIPLE_COMPETING_MATERIAL_EVENT_DATES',
        }

    years = {row['year'] for row in material if row['precision'] == 'year'}
    if len(years) == 1:
        year = next(iter(years))
        row = max(
            (r for r in material if r['precision'] == 'year' and r['year'] == year),
            key=lambda item: item['score'],
        )
        return {
            'status': 'MATERIAL_TEMPUS_CANDIDATE',
            'value': str(year),
            'precision': 'year',
            'confidence': 'MEDIUM_CANDIDATE',
            'candidate': row,
            'candidates': candidates,
            'selection_basis': 'UNIQUE_MATERIAL_EVENT_YEAR',
        }
    if len(years) > 1:
        return {
            'status': 'MATERIAL_TEMPUS_AMBIGUOUS',
            'value': None,
            'precision': None,
            'confidence': 'NONE',
            'candidates': candidates,
            'selection_basis': 'MULTIPLE_COMPETING_MATERIAL_EVENT_DATES',
        }
    return {
        'status': 'MATERIAL_TEMPUS_UNKNOWN',
        'value': None,
        'precision': None,
        'confidence': 'NONE',
        'candidates': candidates,
        'selection_basis': 'NO_DEFENSIBLE_MATERIAL_EVENT_DATE',
    }
