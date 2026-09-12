"""Canonical document-posture resolver for LexiCore Case Analysis.

This module is the single source of truth for generated document/review/strategy
labels.  It combines structural source markers with the additive
``ranah_hukum`` / ``posisi_pengguna`` contract, but it never changes the core
case-domain classification or source/evidence ledgers.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable


def _count(text: str, patterns: Iterable[str]) -> int:
    low = str(text or '').lower()
    return sum(low.count(str(p).lower()) for p in patterns)


def _header_posture(text: str) -> str | None:
    """Resolve explicit document role from the opening/header first.

    Headings and introductory procedural language are more authoritative than
    repeated nouns inside annexes, quoted evidence, statutes, or chronologies.
    This prevents words such as "penetapan" in an SK/chronology from turning a
    response document into a judicial decision.
    """
    head = re.sub(r'\s+', ' ', str(text or '')[:2400]).strip().lower()
    if not head:
        return None
    # BAP/Pemeriksaan Tersangka is a source/procedural examination record, not a judicial order.
    if re.search(r'\b(?:berita\s+acara\s+pemeriksaan(?:\s+tersangka)?|bap\s+tersangka|pemeriksaan\s+tersangka)\b', head, re.I):
        return 'BAP_TERSANGKA'
    if re.search(r'\bdupl(?:i|ie)k\b', head, re.I):
        return 'RESPONSE_TO_COMPLAINT'
    if re.search(r'\bjawaban\s+atas\s+(?:laporan|pengaduan|gugatan|permohonan)\b', head, re.I):
        return 'RESPONSE_TO_COMPLAINT'
    if re.search(r'\b(?:dalam\s+pokok\s+aduan|menolak\s+seluruh\s+dalil|teradu\s+.*?membantah\s+dalil)\b', head, re.I):
        return 'RESPONSE_TO_COMPLAINT'
    if re.search(r'\b(?:eksepsi|nota\s+keberatan|nota\s+pembelaan|pledoi)\b', head, re.I):
        return 'OBJECTION_OR_DEFENSE'
    if re.search(r'\b(?:putusan\s+nomor|penetapan\s+nomor|amar\s+putusan|mengadili\s*[:.]|demi\s+keadilan)\b', head, re.I):
        return 'DECISION_OR_ORDER'
    # A planning/advisory note that says what should/will be done is not a filed
    # pleading merely because it mentions a future gugatan/permohonan.
    future_hits=len(re.findall(r'\b(?:memberikan\s+somasi|menyiapkan\s+bukti|mengajukan\s+gugatan|dilanjutkan\s+mediasi|apabila\s+tidak\s+berhasil|proses\s+dan\s+prosedur)\b', head, re.I))
    filed_claim=bool(re.search(r'\b(?:surat\s+gugatan|gugatan\s+nomor|penggugat\s*[:]|petitum\s*[:]|kepada\s+ketua\s+pengadilan)\b', head, re.I))
    if future_hits >= 2 and not filed_claim:
        return 'PRE_LITIGATION_ADVISORY'
    if re.search(r'\b(?:pengaduan|laporan\s+dugaan|gugatan|permohonan)\b', head, re.I):
        return 'CLAIM_OR_COMPLAINT'
    if re.search(r'\b(?:perjanjian|kontrak)\b', head, re.I) and re.search(r'\b(?:para\s+pihak|pihak\s+pertama|pihak\s+kedua)\b', head, re.I):
        return 'AGREEMENT'
    return None


def _structural_posture(text: str) -> Dict[str, Any]:
    source = re.sub(r'\s+', ' ', str(text or '')).strip()
    header = _header_posture(source)
    profiles = {
        'BAP_TERSANGKA': (
            'berita acara pemeriksaan tersangka', 'berita acara pemeriksaan',
            'pemeriksaan tersangka', 'surat perintah penyidikan', 'penetapan tersangka',
        ),
        'RESPONSE_TO_COMPLAINT': (
            'jawaban atas laporan', 'jawaban atas pengaduan', 'jawaban tergugat',
            'dalam pokok aduan', 'dalam pokok gugatan', 'menolak seluruh dalil',
            'sanggahan', 'membantah dalil',
        ),
        'CLAIM_OR_COMPLAINT': (
            'pengaduan', 'laporan dugaan', 'pokok aduan', 'gugatan',
            'penggugat', 'pemohon', 'permohonan',
        ),
        'OBJECTION_OR_DEFENSE': (
            'eksepsi', 'nota keberatan', 'surat dakwaan', 'dakwaan', 'terdakwa',
            'keberatan formil', 'nota pembelaan', 'pledoi',
        ),
        'DECISION_OR_ORDER': (
            'memutuskan', 'mengadili', 'amar putusan', 'putusan nomor', 'penetapan nomor',
        ),
        'AGREEMENT': (
            'perjanjian', 'para pihak', 'pihak pertama', 'pihak kedua', 'sepakat',
        ),
        'PRE_LITIGATION_ADVISORY': (
            'proses dan prosedur', 'memberikan somasi', 'menyiapkan bukti',
            'mengajukan gugatan', 'apabila tidak berhasil',
        ),
    }
    scores = {name: _count(source, markers) for name, markers in profiles.items()}
    if re.search(r'\bjawaban\s+(?:atas\s+)?(?:laporan|pengaduan|gugatan)\b', source, re.I):
        scores['RESPONSE_TO_COMPLAINT'] += 8
    if re.search(r'\bdalam\s+pokok\s+(?:aduan|gugatan)\b', source, re.I):
        scores['RESPONSE_TO_COMPLAINT'] += 5
    if re.search(r'\b(?:pengadu|pelapor|penggugat)\b.*\b(?:teradu|terlapor|tergugat)\b', source, re.I):
        scores['RESPONSE_TO_COMPLAINT'] += 3

    if header:
        scores[header] = max(scores.get(header, 0), max(scores.values() or [0]) + 20)
        return {'posture': header, 'confidence': 'HIGH', 'scores': scores, 'basis': 'EXPLICIT_DOCUMENT_HEADER'}

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ordered[0] if ordered else ('GENERAL_LEGAL_DOCUMENT', 0)
    second_score = ordered[1][1] if len(ordered) > 1 else 0
    if best_score < 2:
        best = 'GENERAL_LEGAL_DOCUMENT'
    confidence = 'HIGH' if best_score >= 8 and best_score >= second_score + 3 else ('MEDIUM' if best_score >= 3 else 'LOW')
    return {'posture': best, 'confidence': confidence, 'scores': scores}


class DocumentPostureResolver:
    """Resolve one canonical generated posture profile.

    The matrix is procedural-role oriented, not case-name oriented.  Unknown
    legal domains remain supported through the structural fallback.
    """

    ROLE_PROFILE_MAP = {
        ('ETIK_ADMINISTRATIF', 'TERADU'): {
            'document_type': 'Jawaban atas Pengaduan Etik',
            'review_type': 'Pembelaan Etik',
            'strategy_type': 'Pembelaan Etik',
            'issue_label': 'Pokok Aduan',
            'response_label': 'Jawaban / sanggahan',
            'remedy_label': 'Petitum Jawaban',
        },
        ('ETIK_ADMINISTRATIF', 'PENGADU'): {
            'document_type': 'Pengaduan Etik',
            'review_type': 'Pengaduan Etik',
            'strategy_type': 'Pengaduan Etik',
            'issue_label': 'Dugaan Pelanggaran',
            'response_label': 'Dalil Pengaduan',
            'remedy_label': 'Petitum Pengaduan',
        },
        ('PIDANA', 'TERDAKWA'): {
            'document_type': 'Nota Pembelaan / Eksepsi',
            'review_type': 'Pembelaan Pidana',
            'strategy_type': 'Pembelaan Pidana',
            'issue_label': 'Dakwaan',
            'response_label': 'Pembelaan',
            'remedy_label': 'Petitum Pembelaan',
        },
        ('PIDANA', 'KORBAN'): {
            'document_type': 'Laporan / Posisi Korban',
            'review_type': 'Analisis Posisi Korban',
            'strategy_type': 'Perlindungan / Pemulihan Korban',
            'issue_label': 'Perbuatan yang Dilaporkan',
            'response_label': 'Posisi Korban',
            'remedy_label': 'Permohonan / Pemulihan',
        },
        ('PERDATA', 'PENGGUGAT'): {
            'document_type': 'Gugatan Perdata',
            'review_type': 'Gugatan Perdata',
            'strategy_type': 'Gugatan',
            'issue_label': 'Dasar Gugatan',
            'response_label': 'Dalil Gugatan',
            'remedy_label': 'Petitum Gugatan',
        },
        ('PERDATA', 'TERGUGAT'): {
            'document_type': 'Jawaban Gugatan',
            'review_type': 'Jawaban Perdata',
            'strategy_type': 'Pembelaan Perdata',
            'issue_label': 'Pokok Gugatan',
            'response_label': 'Jawaban / bantahan',
            'remedy_label': 'Petitum Jawaban',
        },
        ('TUN', 'PENGGUGAT'): {
            'document_type': 'Gugatan PTUN',
            'review_type': 'Gugatan Tata Usaha Negara',
            'strategy_type': 'Gugatan TUN',
            'issue_label': 'Keputusan TUN yang Dipersoalkan',
            'response_label': 'Dalil Gugatan',
            'remedy_label': 'Petitum Gugatan',
        },
        ('TUN', 'TERGUGAT'): {
            'document_type': 'Jawaban PTUN',
            'review_type': 'Jawaban Tata Usaha Negara',
            'strategy_type': 'Pembelaan TUN',
            'issue_label': 'Keputusan TUN yang Dipersoalkan',
            'response_label': 'Jawaban / bantahan',
            'remedy_label': 'Petitum Jawaban',
        },
    }

    STRUCTURAL_LABELS = {
        'BAP_TERSANGKA': {
            'document_type': 'Berita Acara Pemeriksaan Tersangka',
            'review_type': 'Review BAP Tersangka',
            'strategy_type': 'Analisis Pemeriksaan Tersangka',
            'issue_label': 'Materi Pemeriksaan / Dugaan',
            'response_label': 'Keterangan Tersangka',
            'remedy_label': 'Tindak Lanjut / Verifikasi',
        },
        'RESPONSE_TO_COMPLAINT': {
            'document_type': 'Jawaban atas pengaduan/laporan',
            'review_type': 'Jawaban / Pembelaan',
            'strategy_type': 'Jawaban / Pembelaan',
            'issue_label': 'Pokok aduan / gugatan',
            'response_label': 'Jawaban / sanggahan',
            'remedy_label': 'Permohonan / petitum jawaban',
        },
        'CLAIM_OR_COMPLAINT': {
            'document_type': 'Pengaduan / laporan / permohonan',
            'review_type': 'Pengaduan / Klaim',
            'strategy_type': 'Pengajuan Klaim',
            'issue_label': 'Pokok pengaduan / klaim',
            'response_label': 'Dalil / posisi pengaju',
            'remedy_label': 'Permohonan / petitum',
        },
        'OBJECTION_OR_DEFENSE': {
            'document_type': 'Keberatan / pembelaan',
            'review_type': 'Keberatan / Pembelaan',
            'strategy_type': 'Keberatan / Pembelaan',
            'issue_label': 'Objek keberatan / tuduhan',
            'response_label': 'Keberatan / pembelaan',
            'remedy_label': 'Permohonan / petitum',
        },
        'DECISION_OR_ORDER': {
            'document_type': 'Putusan / penetapan',
            'review_type': 'Review Putusan / Penetapan',
            'strategy_type': 'Analisis Akibat Hukum',
            'issue_label': 'Isu yang diputus',
            'response_label': 'Pertimbangan',
            'remedy_label': 'Amar / penetapan',
        },
        'AGREEMENT': {
            'document_type': 'Perjanjian / kontrak',
            'review_type': 'Review Kontrak',
            'strategy_type': 'Mitigasi Kontraktual',
            'issue_label': 'Hak, kewajiban, dan sengketa',
            'response_label': 'Posisi para pihak',
            'remedy_label': 'Pemulihan / tindakan',
        },
        'PRE_LITIGATION_ADVISORY': {
            'document_type': 'Catatan Konsultasi / Rencana Pra-Litigasi',
            'review_type': 'Review Pra-Litigasi',
            'strategy_type': 'Perencanaan Tindakan Hukum',
            'issue_label': 'Potensi isu hukum',
            'response_label': 'Posisi awal / informasi klien',
            'remedy_label': 'Opsi tindakan',
        },
        'GENERAL_LEGAL_DOCUMENT': {
            'document_type': 'Dokumen hukum',
            'review_type': 'Analisis Hukum',
            'strategy_type': 'Analisis Hukum',
            'issue_label': 'Isu hukum',
            'response_label': 'Posisi / tanggapan',
            'remedy_label': 'Rekomendasi / permohonan',
        },
    }

    @classmethod
    def resolve(cls, domain_result: Dict | None, case_data: Dict | None) -> Dict[str, Any]:
        domain_result = dict(domain_result or {})
        case_data = dict(case_data or {})
        source_text = str(case_data.get('source_text') or case_data.get('text') or '')
        structural = _structural_posture(source_text)
        base = copy.deepcopy(cls.STRUCTURAL_LABELS[structural['posture']])

        ranah = str(domain_result.get('ranah_hukum') or 'UMUM').upper()
        posisi = str(domain_result.get('posisi_pengguna') or 'BELUM_TERIDENTIFIKASI').upper()
        role_profile = cls.ROLE_PROFILE_MAP.get((ranah, posisi))

        # Structural posture is the authority for document role.  Domain/party
        # refinement only supplies labels when it agrees with that role.
        if role_profile:
            response_side = posisi in {'TERADU','TERGUGAT','TERMOHON','TERDAKWA','TERSANGKA'}
            claim_side = posisi in {'PENGADU','PENGGUGAT','PEMOHON','PELAPOR','KORBAN'}
            compatible = (
                structural['posture'] == 'GENERAL_LEGAL_DOCUMENT'
                or (structural['posture'] == 'RESPONSE_TO_COMPLAINT' and response_side)
                or (structural['posture'] == 'CLAIM_OR_COMPLAINT' and claim_side)
                or (structural['posture'] == 'OBJECTION_OR_DEFENSE' and response_side)
                or (structural['posture'] == 'BAP_TERSANGKA' and posisi in {'TERSANGKA','TERDAKWA','BELUM_TERIDENTIFIKASI'})
            )
            if compatible:
                base.update(copy.deepcopy(role_profile))

        # Preserve explicit pleading stage terminology. A Duplik is not merely
        # a generic 'Jawaban Gugatan'; its procedural stage matters for both
        # review strategy and reader-facing export labels.
        opening = re.sub(r'\s+', ' ', source_text[:2400]).lower()
        subtype = 'BAP_TERSANGKA' if structural['posture'] == 'BAP_TERSANGKA' else None
        if re.search(r'\bdupl(?:i|ie)k\b', opening):
            subtype = 'DUPLIK'
            base.update({'document_type':'Duplik', 'review_type':'Duplik Perdata', 'strategy_type':'Duplik / Pembelaan Perdata'})
        elif re.search(r'\brepl(?:i|ie)k\b', opening):
            subtype = 'REPLIK'
            base.update({'document_type':'Replik', 'review_type':'Replik Perdata', 'strategy_type':'Replik / Penegasan Gugatan'})

        return {
            **structural,
            **base,
            'document_subtype': subtype,
            'ranah_hukum': ranah,
            'posisi_pengguna': posisi,
            'forum': domain_result.get('forum'),
            'source': 'DOCUMENT_POSTURE_RESOLVER_V1_FINAL_CORRECTIVE',
        }


def resolve_document_posture(domain_result: Dict | None, case_data: Dict | None) -> Dict[str, Any]:
    return DocumentPostureResolver.resolve(domain_result, case_data)
