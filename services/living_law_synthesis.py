"""Living Law & Judicial Realism Synthesis.

The frozen pipeline (case_domain_classifier, case_reasoning_guard,
case_consistency_guard, legal_review_engine, adversarial_view,
reasoning_contract) already does Formal/Black-Letter analysis, fact vs
argument separation, counter-arguments, and strategic recommendations very
well. It does NOT model two dimensions elite legal practice cares about:

  Layer 2 -- Living Law / Operational Reality: how the law is actually
             applied, bypassed, or adapted by trade usage, bureaucratic
             practice, or customary norms.
  Layer 3 -- Judicial Realism: how courts, as an institution, tend to
             handle this CATEGORY of dispute (textualist vs substantive
             tendencies, documented enforcement-consistency issues) --
             never a prediction about a specific judge, court or official,
             and never an accusation tied to this specific case.

This module makes exactly ONE additional AI call per case (through
ai_engine.run_grounded_json_prompt -- a purely additive public wrapper
added to ai_engine.py; no existing function there was modified) to
generate that missing socio-legal layer, grounded strictly in the
domain/issues/regulatory matches the frozen pipeline already extracted.

Fail-closed: if AI is unavailable, errors, or returns something that does
not validate against the expected schema, this returns a clearly labeled
placeholder -- never fabricated content standing in as if it were real
analysis. This module never mutates the frozen `result` fields (facts,
legal_analysis, reasoning_contract, etc.) -- it only adds a new, clearly
separate key.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import ai_engine

STATUS_OK = 'GENERATED'
STATUS_UNAVAILABLE = 'AI_UNAVAILABLE'
STATUS_REJECTED = 'VALIDATION_REJECTED'

_REQUIRED_TOP = ('operational_gap', 'customary_commercial_norms', 'judicial_disposition',
                  'risk_matrix', 'strategic_mitigation')
_RISK_ROWS = ('regulatory_enforcement', 'contractual_enforceability', 'socio_reputational_impact')

DISCLAIMER = ('Analisis Living Law dan Judicial Realism adalah hipotesis analitis berbasis pola umum '
              'praktik hukum Indonesia untuk kategori perkara ini -- bukan fakta yang terverifikasi dan '
              'bukan tuduhan terhadap pihak, hakim, atau pengadilan tertentu. Wajib diuji dan diverifikasi '
              'oleh advokat berdasarkan pengalaman forum/yurisdiksi yang relevan sebelum digunakan. '
              'Professional Verification: PENDING.')


def _validate(payload: Any) -> Tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, 'respons bukan objek JSON'
    for k in _REQUIRED_TOP:
        if k not in payload:
            return False, f'field wajib hilang: {k}'
    rm = payload.get('risk_matrix')
    if not isinstance(rm, dict):
        return False, 'risk_matrix harus berupa objek'
    for row in _RISK_ROWS:
        r = rm.get(row)
        if not isinstance(r, dict) or 'risk_level' not in r:
            return False, f'risk_matrix.{row} tidak lengkap'
        try:
            lvl = int(r['risk_level'])
        except Exception:
            return False, f'risk_matrix.{row}.risk_level bukan angka'
        if not (1 <= lvl <= 10):
            return False, f'risk_matrix.{row}.risk_level di luar rentang 1-10'
    sm = payload.get('strategic_mitigation')
    if not isinstance(sm, dict):
        return False, 'strategic_mitigation harus berupa objek'
    return True, ''


def _prompt(result: Dict[str, Any], source_text: str) -> str:
    domain = result.get('domain_classification') or result.get('domain_contract') or {}
    issues = list(result.get('legal_issues') or [])[:8]
    matches = result.get('regulatory_matches') or []
    if matches and isinstance(matches[0], dict):
        provisions = [m.get('pasal') or m.get('source') or str(m) for m in matches[:8]]
    else:
        provisions = list(matches[:8])
    posture = result.get('case_posture') or domain.get('posture') or '-'
    area = domain.get('area') or '-'
    primary_domain = domain.get('primary_domain') or '-'
    excerpt = (source_text or '')[:6000]

    return f'''Anda adalah analis socio-legal senior untuk praktik hukum Indonesia. Tugas Anda HANYA mengisi dua lapis analisis yang belum dihitung oleh sistem lain: (1) Living Law/realitas operasional, (2) Judicial Realism.

ATURAN KETAT -- WAJIB DIPATUHI:
- Gunakan HANYA pola umum yang terdokumentasi/dikenal luas dalam praktik hukum Indonesia untuk domain dan isu di bawah (misalnya kebiasaan dagang, praktik birokrasi, pola konsistensi peradilan yang umum diketahui kalangan praktisi). JANGAN mengarang fakta baru tentang perkara spesifik ini di luar yang diberikan.
- JANGAN menyebut nama hakim, pengadilan, instansi, atau pejabat tertentu, dan JANGAN membuat tuduhan korupsi atau pelanggaran terhadap pihak spesifik dalam perkara ini. Bicarakan pola umum ("pada umumnya", "dalam praktik"), tingkat prediktabilitas penegakan, dan variasi antar-forum secara generik.
- Bila Anda tidak memiliki dasar yang cukup kuat untuk suatu sub-bagian, tulis dengan jujur bahwa polanya belum cukup terdokumentasi untuk domain ini daripada mengarang.
- Jawab HANYA dengan JSON valid sesuai skema di bawah. Tidak ada teks lain di luar JSON.

KONTEKS PERKARA (dari hasil ekstraksi sistem, bukan untuk diragukan ulang):
- Area hukum: {area} | Domain utama: {primary_domain} | Postur: {posture}
- Isu hukum yang sudah teridentifikasi sistem: {issues}
- Pasal/regulasi yang sudah teridentifikasi sistem: {provisions}
- Cuplikan narasi sumber (maksimum 6000 karakter, mungkin terpotong): "{excerpt}"

SKEMA JSON WAJIB:
{{
  "operational_gap": {{"summary": "ringkasan kesenjangan law-in-books vs law-in-action untuk domain ini", "examples": ["contoh konkret 1", "contoh konkret 2"]}},
  "customary_commercial_norms": {{"summary": "norma dagang/adat/birokrasi yang lazim berlaku", "examples": ["contoh 1", "contoh 2"]}},
  "judicial_disposition": {{"summary": "kecenderungan umum pengadilan pada kategori perkara ini (tekstual vs substantif)", "predictability_note": "seberapa dapat diprediksi hasil litigasi secara umum", "caution": "batasan/variasi yang harus diwaspadai, TANPA menyebut pengadilan/hakim spesifik"}},
  "risk_matrix": {{
    "regulatory_enforcement": {{"formal_exposure": "...", "living_law_reality": "...", "risk_level": 1, "rationale": "..."}},
    "contractual_enforceability": {{"formal_exposure": "...", "living_law_reality": "...", "risk_level": 1, "rationale": "..."}},
    "socio_reputational_impact": {{"formal_exposure": "...", "living_law_reality": "...", "risk_level": 1, "rationale": "..."}}
  }},
  "strategic_mitigation": {{"contractual_safeguards": ["..."], "operational_workarounds": ["..."], "litigation_readiness": ["..."]}}
}}'''


def build_living_law_synthesis(result: Dict[str, Any], source_text: str) -> Dict[str, Any]:
    """Pure-ish: one AI call if available, else fail-closed. Never raises.

    Always returns a dict carrying a 'status' key so the UI can render an
    honest state ("not generated") instead of guessing or showing nothing.
    """
    if not ai_engine.is_available():
        return {
            'status': STATUS_UNAVAILABLE,
            'note': ('AI provider tidak dikonfigurasi/tidak tersedia pada saat run ini. Layer Living Law '
                      'dan Judicial Realism tidak dihasilkan agar tidak ada konten yang dikarang.'),
            'disclaimer': DISCLAIMER,
        }
    payload = ai_engine.run_grounded_json_prompt(_prompt(result, source_text))
    if payload is None:
        return {
            'status': STATUS_UNAVAILABLE,
            'note': 'Panggilan AI untuk Living Law/Judicial Realism gagal atau timeout pada run ini.',
            'disclaimer': DISCLAIMER,
        }
    ok, reason = _validate(payload)
    if not ok:
        return {
            'status': STATUS_REJECTED,
            'note': f'Respons AI tidak sesuai skema dan ditolak secara fail-closed: {reason}',
            'disclaimer': DISCLAIMER,
        }
    payload['status'] = STATUS_OK
    payload['disclaimer'] = DISCLAIMER
    return payload


def enrich_living_analysis(result: Dict[str, Any], source_text: str) -> Dict[str, Any]:
    """Attach result['living_analysis']['living_law_synthesis'].

    No-op (defensive) if `living_analysis` was not attached yet, so this
    module stays independent of the exact call order elsewhere.
    """
    la = result.get('living_analysis')
    if not isinstance(la, dict):
        return result
    la['living_law_synthesis'] = build_living_law_synthesis(result, source_text)
    return result
