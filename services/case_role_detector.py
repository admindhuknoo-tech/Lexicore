"""Deterministic ranah_hukum / posisi_pengguna detector for LexiCore.

This module does not replace `case_domain_classifier.classify_case`; it reads
its output plus explicit textual signals to answer two narrower, more
actionable questions that the domain/posture contract does not itself encode:

1. ranah_hukum   — which procedural-law family governs (Pidana Umum, Pidana
                    Khusus, Perdata, TUN, Niaga, Agama, Hubungan Industrial,
                    Arbitrase, Etik Penyelenggara Pemilu, or GENERAL when the
                    signal is too weak to commit).
2. posisi_pengguna — whose side the document/case record is written from
                    (Terdakwa, Penggugat, Tergugat, Pemohon, Termohon,
                    Korban/Pelapor, Teradu, or TIDAK_TERIDENTIFIKASI).

Both are used only to select which tactical/procedural playbook entries are
relevant (see services/case_action_planner.py). Neither value is used to
decide guilt, liability, or the merits of the case, and both are exposed with
an explicit confidence/evidence trail so a wrong guess is visible rather than
silently steering the action plan.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

NEGATION_PATTERNS = [r'tidak\s+ada', r'tanpa', r'bukan', r'tidak\s+terdapat', r'belum\s+ada']


def _present(text: str, term: str) -> bool:
    low = text.lower()
    term = term.lower()
    for m in re.finditer(re.escape(term), low):
        prefix = low[max(0, m.start() - 45):m.start()]
        if any(re.search(p + r'\s+(?:\w+\s+){0,3}$', prefix) for p in NEGATION_PATTERNS):
            continue
        return True
    return False


def _count(text: str, terms) -> int:
    return sum(1 for t in terms if _present(text, t))


# ---------------------------------------------------------------------------
# ranah_hukum
# ---------------------------------------------------------------------------

_RANAH_FROM_POSTURE = {
    'PIDANA_KHUSUS_PENYIDIKAN': 'PIDANA_KHUSUS',
    'ELECTORAL_ETHICS_PROCEEDING': 'ETIK_PENYELENGGARA_PEMILU',
    'TATA_USAHA_NEGARA': 'TUN',
    'SENGKETA_INFORMASI_PUBLIK': 'TUN',
    'REGULATORY_INVESTMENT': 'TUN',
    'PERDATA_LITIGASI': 'PERDATA',
    'HUBUNGAN_INDUSTRIAL': 'HUBUNGAN_INDUSTRIAL',
    'NIAGA_KEPAILITAN': 'NIAGA',
    'ARBITRASE_ADR': 'ARBITRASE',
    'REGULATORY_FINANCIAL_SERVICES': 'PERDATA',
    'DATA_PRIVACY_DIGITAL': 'PERDATA',
    'PERLINDUNGAN_KONSUMEN': 'PERDATA',
    'KORPORASI': 'PERDATA',
    'PERDATA_SENGKETA_KONTRAK': 'PERDATA',
    'GENERAL_LEGAL': 'GENERAL',
}


def detect_ranah_hukum(text: str, domain_classification: Dict[str, Any] | None) -> Dict[str, Any]:
    dc = domain_classification or {}
    posture = str(dc.get('posture') or '')
    primary_domain = str(dc.get('primary_domain') or '')
    religious = _count((text or '').lower(), ['pengadilan agama', 'peradilan agama', 'pasal 49', 'waris islam', 'ekonomi syariah'])
    direct_criminal = _count((text or '').lower(), ['tersangka', 'penyidikan', 'penuntut umum', 'jaksa penyidik',
                                                      'surat penetapan tersangka', 'dakwaan', 'penahanan', 'penangkapan',
                                                      'terdakwa'])
    ranah = _RANAH_FROM_POSTURE.get(posture)
    basis = f"posture={posture}" if ranah else "posture tidak dikenali"

    # `classify_case` does not emit a dedicated posture for a plain (non-
    # corruption) criminal case: it leaves posture=GENERAL_LEGAL but still
    # sets primary_domain='criminal'. Without this check every ordinary
    # pidana-umum case (the most common posisi_pengguna=TERDAKWA scenario)
    # would silently fall to ranah_hukum=GENERAL and never reach the
    # Praperadilan/Nota Keberatan/Saksi A De Charge playbook below.
    if ranah in (None, 'GENERAL') and primary_domain == 'criminal':
        ranah = 'PIDANA_UMUM'
        basis = "primary_domain=criminal pada domain_classification"
    elif ranah is None and direct_criminal >= 2:
        ranah = 'PIDANA_UMUM'
        basis = "sinyal acara pidana pada teks tanpa posture/primary_domain eksplisit"

    if religious:
        ranah = 'AGAMA'
        basis = "sinyal Peradilan Agama pada teks"
    if ranah is None:
        ranah = 'GENERAL'
    return {'ranah_hukum': ranah, 'basis': basis, 'posture_source': posture}


# ---------------------------------------------------------------------------
# posisi_pengguna
# ---------------------------------------------------------------------------

_ROLE_SIGNALS = {
    'TERDAKWA': ['penasihat hukum terdakwa', 'penasehat hukum terdakwa', 'kuasa hukum terdakwa',
                 'untuk dan atas nama terdakwa', 'nota keberatan', 'pembelaan terdakwa', 'terdakwa'],
    'PENGGUGAT': ['kuasa hukum penggugat', 'untuk dan atas nama penggugat', 'selaku penggugat',
                  'penggugat dalam perkara ini'],
    'TERGUGAT': ['kuasa hukum tergugat', 'untuk dan atas nama tergugat', 'selaku tergugat',
                 'jawaban gugatan', 'jawaban atas gugatan'],
    'PEMOHON': ['kuasa hukum pemohon', 'untuk dan atas nama pemohon', 'selaku pemohon', 'permohonan a quo'],
    'TERMOHON': ['kuasa hukum termohon', 'untuk dan atas nama termohon', 'selaku termohon'],
    'KORBAN_PELAPOR': ['laporan polisi', 'selaku korban', 'selaku pelapor', 'sebagai korban', 'sebagai pelapor'],
    'TERADU': ['teradu', 'kuasa hukum teradu', 'jawaban atas laporan dugaan pelanggaran kode etik'],
    'PENGADU': ['pengadu', 'kuasa hukum pengadu'],
}

# When both sides of a pair appear (e.g. a pleading mentions both Penggugat
# and Tergugat), the *authorship* signals (kuasa hukum X, untuk dan atas nama
# X, jawaban gugatan) are weighted far higher than the bare party label,
# which is expected to appear regardless of which side commissioned the
# document.
_AUTHORSHIP_WEIGHT = 5
_BARE_LABEL_WEIGHT = 1


def _role_score(low: str, role: str) -> int:
    score = 0
    for signal in _ROLE_SIGNALS[role]:
        if not _present(low, signal):
            continue
        weight = _BARE_LABEL_WEIGHT if signal in (role.lower(), role.lower().replace('_', ' ')) else _AUTHORSHIP_WEIGHT
        score += weight
    return score


def detect_posisi_pengguna(text: str, doc_type: str | None = None) -> Dict[str, Any]:
    low = (text or '').lower()
    scores = {role: _role_score(low, role) for role in _ROLE_SIGNALS}
    best_role = max(scores, key=scores.get)
    best_score = scores[best_role]
    runner_up = max((s for r, s in scores.items() if r != best_role), default=0)
    if best_score == 0 or best_score <= runner_up:
        return {
            'posisi_pengguna': 'TIDAK_TERIDENTIFIKASI',
            'confidence': 'LOW',
            'basis': 'Tidak ditemukan penanda otorship (kuasa hukum/untuk dan atas nama) yang jelas untuk satu pihak.',
            'scores': scores,
        }
    confidence = 'HIGH' if best_score >= _AUTHORSHIP_WEIGHT else 'MEDIUM'
    return {
        'posisi_pengguna': best_role,
        'confidence': confidence,
        'basis': f'Penanda otorship terkuat mengarah ke {best_role} (skor={best_score} vs runner-up={runner_up}).',
        'scores': scores,
    }


def detect_case_role(text: str, result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Single entry point used by case_action_planner: returns both axes."""
    result = result or {}
    domain_classification = result.get('domain_classification') or result.get('domain_contract') or {}
    doc_type = ((result.get('professional_review') or {}).get('document_structure') or {}).get('document_type')
    ranah = detect_ranah_hukum(text, domain_classification)
    posisi = detect_posisi_pengguna(text, doc_type)
    return {**ranah, **posisi}
