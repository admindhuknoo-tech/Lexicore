"""Living Analysis Orchestrator.

This module is a pure, read-only NARRATION layer over the Case Analysis
`result` dict that routes/case_analysis.py already builds by the time all
frozen engines/services have run (case_domain_classifier, reasoning_guard,
consistency_guard, legal_review_engine, adversarial_view,
regulatory_retrieval, norm_conflict, reasoning_contract, case_working_paper,
etc.). It performs ZERO new AI calls, ZERO re-computation, and does not
modify, import-and-rewrap, or restructure any of those engines. It only
reads fields they already produced and labels them under the explicit
14-step method LexiCore's lawyers use to think through a case, plus the
5-node critic loop that quality-checks the draft before it is presented as
final.

    LIVING ANALYSIS — 14 langkah:
      1  Baca seluruh narasi
      2  Identifikasi pihak & peran
      3  Bangun kronologi
      4  Identifikasi objek / uang / dokumen
      5  Pisahkan fakta vs dugaan
      6  Temukan isu hukum
      7  Deteksi fakta yang hilang
      8  Cari hukum yang relevan
      9  Bentuk beberapa hipotesis hukum
      10 Uji pro & kontra
      11 Uji tempus / yurisdiksi / evidence
      12 Nilai risiko
      13 Bentuk rekomendasi tindakan
      14 Self-review / contradiction check

    CRITIC LOOP:
      Draft Analysis -> Critic -> Counter Analysis -> Evidence Check ->
      Law Verification -> Final Synthesis

Call `attach_living_analysis(result)` once, after the existing pipeline has
finished populating `result` (i.e. after apply_professional_review /
build_adversarial_viewpoint_splitter / attach_reasoning_contract have run,
so every field this module reads already exists). It is safe to call this
function nowhere at all -- nothing else in the pipeline depends on
`result['living_analysis']` -- which is what makes it purely additive.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DONE = 'DONE'
PARTIAL = 'PARTIAL'
NOT_MODELED = 'NOT_SEPARATELY_MODELED'


def _clip_list(values: Any, limit: int = 5, item_limit: int = 220) -> List[str]:
    out: List[str] = []
    for v in (values or []):
        s = str(v).strip()
        if not s:
            continue
        s = s[:item_limit] + ('…' if len(s) > item_limit else '')
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _step(step_id: int, name: str, question: str, status: str, summary: str,
          source: str, evidence: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        'step': step_id,
        'name': name,
        'question': question,
        'status': status,
        'summary': summary,
        'source': source,
        'evidence': evidence or [],
    }


def _step1_reading(result: Dict[str, Any]) -> Dict[str, Any]:
    dr = result.get('document_reading') or {}
    chars = dr.get('characters') or len(result.get('source_text') or '')
    segs_total = dr.get('segments_total') or 0
    segs_read = dr.get('segments_read') or 0
    mode = dr.get('reading_mode') or result.get('analytical_method') or '-'
    summary = f"{chars:,} karakter dibaca".replace(',', '.')
    if segs_total:
        summary += f"; {segs_read}/{segs_total} segmen diproses"
    summary += f". Mode pembacaan: {mode}."
    return _step(1, 'Baca seluruh narasi', 'Apa isi lengkap narasi/dokumen ini?',
                 DONE if chars else PARTIAL, summary, 'document_reading / source_text')


def _step2_parties(result: Dict[str, Any]) -> Dict[str, Any]:
    dc = result.get('domain_classification') or result.get('domain_contract') or {}
    role = dc.get('role') or 'BELUM_TERIDENTIFIKASI'
    area = dc.get('area') or '-'
    confidence = dc.get('confidence') or '-'
    basis = dc.get('basis') or ''
    summary = f"Posisi dokumen teridentifikasi sebagai {role} (area hukum: {area}, confidence: {confidence})."
    status = DONE if role != 'BELUM_TERIDENTIFIKASI' else PARTIAL
    return _step(2, 'Identifikasi pihak & peran', 'Siapa para pihak dan apa peran/posisi masing-masing?',
                 status, summary, 'domain_classification (case_domain_classifier)',
                 _clip_list([basis], 1) if basis else [])


def _step3_chronology(result: Dict[str, Any]) -> Dict[str, Any]:
    dv = result.get('date_values') or []
    mt = result.get('material_tempus') or {}
    mt_status = mt.get('status') or 'UNKNOWN'
    mt_value = mt.get('value')
    summary = f"{len(dv)} tanggal terdeteksi dalam narasi."
    if mt_value:
        summary += f" Tempus material terpilih: {mt_value} ({mt_status})."
    else:
        summary += f" Tempus material: {mt_status} — belum ada satu tanggal yang cukup dominan/eksplisit untuk dipilih secara fail-safe."
    status = DONE if dv else PARTIAL
    return _step(3, 'Bangun kronologi', 'Bagaimana urutan waktu peristiwa, dan tanggal mana yang material secara hukum?',
                 status, summary, 'date_values / material_tempus (material_tempus_extractor)',
                 _clip_list(dv, 6))


def _step4_objects(result: Dict[str, Any]) -> Dict[str, Any]:
    mv = result.get('money_values') or []
    dv = result.get('date_values') or []
    summary = f"{len(mv)} nilai uang dan {len(dv)} tanggal/dokumen bertanggal teridentifikasi dari teks."
    status = DONE if (mv or dv) else PARTIAL
    return _step(4, 'Identifikasi objek / uang / dokumen', 'Objek sengketa, nilai uang, dan dokumen apa saja yang disebut?',
                 status, summary, 'money_values / date_values', _clip_list(mv, 6))


def _step5_fact_vs_assumption(result: Dict[str, Any]) -> Dict[str, Any]:
    facts = result.get('facts') or []
    avs = result.get('adversarial_viewpoint_splitter') or {}
    prosecution = avs.get('prosecution') or avs.get('pihak_a') or []
    defense = avs.get('defense') or avs.get('pihak_b') or []
    summary = f"{len(facts)} kalimat fakta diekstraksi dari narasi."
    if prosecution or defense:
        summary += f" Adversarial viewpoint splitter memisahkan {len(prosecution)} pernyataan sisi pemohon/penuntut dan {len(defense)} sisi termohon/tergugat berdasarkan semantic_type (fakta/dugaan/argumen)."
    status = DONE if facts else PARTIAL
    return _step(5, 'Pisahkan fakta vs dugaan', 'Mana yang fakta yang didukung dokumen, mana yang baru dugaan/klaim satu pihak?',
                 status, summary, 'facts / adversarial_viewpoint_splitter', _clip_list(facts, 5))


def _step6_legal_issues(result: Dict[str, Any]) -> Dict[str, Any]:
    issues = result.get('legal_issues') or []
    summary = f"{len(issues)} isu hukum teridentifikasi."
    status = DONE if issues else PARTIAL
    return _step(6, 'Temukan isu hukum', 'Isu/pertanyaan hukum apa saja yang harus dijawab dalam perkara ini?',
                 status, summary, 'legal_issues', _clip_list(issues, 6))


def _step7_missing_facts(result: Dict[str, Any]) -> Dict[str, Any]:
    gaps = result.get('evidentiary_gaps') or []
    needed = result.get('evidence_needed') or []
    pr = result.get('professional_review') or {}
    pr_gaps = pr.get('evidence_findings') or pr.get('findings') or []
    combined = list(gaps) + [x for x in needed if x not in gaps]
    summary = f"{len(combined)} kebutuhan bukti/fakta yang belum tersedia teridentifikasi."
    if pr_gaps:
        summary += f" Professional review menambahkan {len(pr_gaps)} temuan terkait kelengkapan bukti."
    status = DONE if combined else PARTIAL
    return _step(7, 'Deteksi fakta yang hilang', 'Fakta/bukti apa yang belum ada tapi dibutuhkan untuk menyimpulkan?',
                 status, summary, 'evidentiary_gaps / evidence_needed / professional_review', _clip_list(combined, 6))


def _step8_legal_basis(result: Dict[str, Any]) -> Dict[str, Any]:
    matches = result.get('regulatory_matches') or []
    refs = result.get('provision_refs') or []
    corpus_status = result.get('regulatory_corpus_status') or {}
    official = result.get('official_verification') or {}
    summary = (f"{len(matches)} regulasi/pasal relevan ditemukan (mode: {corpus_status.get('mode', '-')}); "
               f"{len(refs)} rujukan pasal eksplisit dari teks sumber.")
    verified = official.get('status') if isinstance(official, dict) else None
    if verified:
        summary += f" Status akses sumber resmi: {verified}."
    status = DONE if matches else PARTIAL
    return _step(8, 'Cari hukum yang relevan', 'Peraturan/pasal mana yang relevan dengan isu-isu di atas?',
                 status, summary, 'regulatory_matches / provision_refs (regulatory_retrieval, legal_sources)',
                 _clip_list([m.get('pasal') or m.get('source') or str(m) for m in matches] if matches and isinstance(matches[0], dict) else matches, 6))


def _step9_hypotheses(result: Dict[str, Any]) -> Dict[str, Any]:
    elements = result.get('element_matrix') or []
    chain = result.get('legal_reasoning_chain') or {}
    summary = f"{len(elements)} unsur hukum dipetakan dengan posisi pendukung vs pembela masing-masing."
    if chain:
        summary += " Legal reasoning chain (11 tahap) menautkan unsur-unsur ini menjadi satu rangkaian hipotesis yang koheren."
    status = DONE if elements else PARTIAL
    ev = [e.get('element', str(e)) for e in elements] if elements and isinstance(elements[0], dict) else []
    return _step(9, 'Bentuk beberapa hipotesis hukum', 'Skenario/konstruksi hukum apa saja yang mungkin menjelaskan fakta ini?',
                 status, summary, 'element_matrix / legal_reasoning_chain', _clip_list(ev, 6))


def _step10_pro_contra(result: Dict[str, Any]) -> Dict[str, Any]:
    pros = result.get('arguments_for') or []
    cons = result.get('arguments_against') or []
    conflicts = result.get('norm_conflicts') or {}
    conflict_n = len(conflicts.get('conflicts') or conflicts.get('matrix') or []) if isinstance(conflicts, dict) else 0
    summary = f"{len(pros)} argumen mendukung dan {len(cons)} argumen menentang teridentifikasi."
    if conflict_n:
        summary += f" {conflict_n} potensi antinomi/konflik norma turut diuji (lex superior/specialis/posterior)."
    status = DONE if (pros or cons) else PARTIAL
    return _step(10, 'Uji pro & kontra', 'Apa argumen terkuat untuk tiap posisi, dan bagaimana masing-masing dapat dibantah?',
                 status, summary, 'arguments_for / arguments_against / norm_conflicts',
                 _clip_list(pros, 3) + _clip_list(cons, 3))


def _step11_tempus_jurisdiction_evidence(result: Dict[str, Any]) -> Dict[str, Any]:
    guard = result.get('reasoning_guard') or {}
    tempus = guard.get('tempus') or {}
    boundary = guard.get('boundary_checks') or []
    posture = result.get('case_posture') or '-'
    flagged = [b for b in boundary if isinstance(b, dict) and b.get('flag')]
    summary = f"Postur perkara: {posture}. {len(flagged)}/{len(boundary)} boundary check (yurisdiksi/forum/atribusi) menyalakan flag."
    if tempus:
        summary += f" Tempus assessment: {tempus.get('status', tempus.get('note', '-'))}."
    status = DONE if guard else PARTIAL
    return _step(11, 'Uji tempus / yurisdiksi / evidence', 'Apakah waktu berlakunya norma, forum/yurisdiksi, dan kekuatan bukti sudah teruji?',
                 status, summary, 'reasoning_guard (case_reasoning_guard)',
                 _clip_list([b.get('label', str(b)) for b in flagged] if flagged and isinstance(flagged[0], dict) else flagged, 5))


def _step12_risk(result: Dict[str, Any]) -> Dict[str, Any]:
    risks = result.get('risks') or []
    strategic = (result.get('professional_review') or {}).get('strategic_recommendation') or {}
    summary = f"{len(risks)} risiko dicatat."
    if strategic:
        summary += f" Strategic recommendation menilai prioritas: {strategic.get('priority', strategic.get('headline', '-'))}."
    status = DONE if risks else PARTIAL
    return _step(12, 'Nilai risiko', 'Apa risiko hukum/strategis utama bila posisi ini diambil?',
                 status, summary, 'risks / professional_review.strategic_recommendation', _clip_list(risks, 5))


def _step13_recommendation(result: Dict[str, Any]) -> Dict[str, Any]:
    recs = result.get('recommendations') or []
    plan = (result.get('case_working_paper') or {}).get('action_plan') or (result.get('case_working_paper') or {}).get('tactical_action_plan') or []
    summary = f"{len(recs)} rekomendasi umum tercatat."
    if plan:
        summary += f" Case Working Paper menyusun {len(plan)} langkah tindakan taktis bergerbang hukum (legal-gated)."
    status = DONE if (recs or plan) else PARTIAL
    return _step(13, 'Bentuk rekomendasi tindakan', 'Langkah apa yang sebaiknya diambil selanjutnya?',
                 status, summary, 'recommendations / case_working_paper', _clip_list(recs, 5))


def _step14_self_review(result: Dict[str, Any]) -> Dict[str, Any]:
    pr = result.get('professional_review') or {}
    consistency = result.get('consistency_guard') or {}
    contract = result.get('reasoning_contract') or {}
    valid = contract.get('valid') if isinstance(contract, dict) else None
    summary = "Professional review dan consistency guard telah dijalankan."
    if valid is not None:
        summary += f" Reasoning contract validation: {'LULUS' if valid else 'GAGAL — lihat reasoning_contract.errors'}."
    status = DONE if (pr or consistency) else PARTIAL
    return _step(14, 'Self-review / contradiction check', 'Apakah analisis ini konsisten dengan dirinya sendiri dan dengan fakta sumber?',
                 status, summary, 'professional_review / consistency_guard / reasoning_contract')


def _critic_loop(result: Dict[str, Any]) -> Dict[str, Any]:
    draft = result.get('unguarded_legal_analysis') or result.get('legal_analysis') or ''
    pr = result.get('professional_review') or {}
    critic_findings = (pr.get('evidence_findings') or []) + (pr.get('argument_findings') or [])
    avs = result.get('adversarial_viewpoint_splitter') or {}
    consistency = result.get('consistency_guard') or {}
    official = result.get('official_verification') or {}
    guard = result.get('reasoning_guard') or {}
    chain = result.get('legal_reasoning_chain') or {}
    contract = result.get('reasoning_contract') or {}

    return {
        'draft_analysis': {
            'question': None,
            'summary': (draft[:600] + '…') if isinstance(draft, str) and len(draft) > 600 else draft,
            'source': 'unguarded_legal_analysis (pre-guard) / legal_analysis',
        },
        'critic': {
            'question': 'Apakah ada fakta yang belum dipertimbangkan?',
            'summary': f"{len(critic_findings)} temuan dari professional review (structural/argument/evidence findings).",
            'source': 'professional_review (legal_review_engine)',
            'evidence': _clip_list([f.get('finding') or f.get('note') or str(f) for f in critic_findings] if critic_findings and isinstance(critic_findings[0], dict) else critic_findings, 5),
        },
        'counter_analysis': {
            'question': 'Apa argumen lawan?',
            'summary': f"Adversarial viewpoint splitter memisahkan pernyataan {len(avs.get('prosecution') or avs.get('pihak_a') or [])} vs {len(avs.get('defense') or avs.get('pihak_b') or [])} berikut basis argumen pembanding pada element_matrix.",
            'source': 'adversarial_viewpoint_splitter (adversarial_view) / element_matrix',
        },
        'evidence_check': {
            'question': 'Mana yang fakta, mana yang dugaan?',
            'summary': consistency.get('note') or 'Consistency guard memisahkan fakta bersumber dokumen dari inferensi/argumen sebelum masuk executive summary.',
            'source': 'consistency_guard (case_consistency_guard)',
        },
        'law_verification': {
            'question': 'Dasar hukum masih berlaku?',
            'summary': (
                f"Status verifikasi sumber resmi: {official.get('status', 'NOT_RUN') if isinstance(official, dict) else 'NOT_RUN'}. "
                f"Reasoning guard mendeteksi {len(guard.get('citation_anomalies') or [])} anomali sitasi."
            ),
            'source': 'official_verification (legal_sources) / reasoning_guard.citation_anomalies',
        },
        'final_synthesis': {
            'question': None,
            'summary': (
                f"Legal reasoning chain (11 tahap) tersusun; validasi kontrak: "
                f"{'LULUS' if contract.get('valid') else ('GAGAL' if contract else 'BELUM DIVALIDASI')}."
            ),
            'source': 'legal_reasoning_chain / reasoning_contract (reasoning_contract.py) / case_working_paper',
        },
    }


def build_living_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    """Pure function: read `result`, return the living-analysis narration.

    Never mutates `result`. Safe to call multiple times; safe to call on a
    partially-populated `result` (every step degrades to PARTIAL rather than
    raising, since a case run may legitimately skip a stage e.g. when AI is
    unavailable and the deterministic fallback path is used).
    """
    steps = [
        _step1_reading(result), _step2_parties(result), _step3_chronology(result),
        _step4_objects(result), _step5_fact_vs_assumption(result), _step6_legal_issues(result),
        _step7_missing_facts(result), _step8_legal_basis(result), _step9_hypotheses(result),
        _step10_pro_contra(result), _step11_tempus_jurisdiction_evidence(result),
        _step12_risk(result), _step13_recommendation(result), _step14_self_review(result),
    ]
    return {
        'method': 'LIVING_ANALYSIS_14_STEP_V1',
        'note': ('Narasi metodologis atas hasil Case Analysis yang sudah dihitung oleh mesin inti LexiCore. '
                 'Layer ini tidak melakukan panggilan AI baru dan tidak mengubah kesimpulan; ia hanya '
                 'memberi label eksplisit atas tahapan yang sudah dijalankan.'),
        'steps': steps,
        'critic_loop': _critic_loop(result),
    }


def attach_living_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach `result['living_analysis']`. Call after the existing pipeline
    (reasoning guard, consistency guard, professional review, adversarial
    view, reasoning contract) has already populated `result`."""
    result['living_analysis'] = build_living_analysis(result)
    return result
