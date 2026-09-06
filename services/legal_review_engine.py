"""LexiCore Professional Legal Review Engine.

A deterministic, fail-closed multi-pass review layer inspired by how a lawyer
would review a pleading or case document: read structure, separate facts from
argument, find anomalies, test legal gates, stress-test the thesis, and turn
findings into concrete recommendations.

This engine does NOT replace professional judgment and does not silently repair
source documents. Every correction is a candidate that must be verified.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List

from services.case_consistency_guard import (
    classify_source_item,
    executive_fact_candidates,
    material_source_ledger,
)


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _uniq(values: Iterable[str], limit: int = 30) -> List[str]:
    out=[]; seen=set()
    for value in values:
        value=_clean(value)
        key=value.lower()
        if not value or key in seen:
            continue
        seen.add(key); out.append(value)
        if len(out)>=limit:
            break
    return out


def _has(text: str, *terms: str) -> bool:
    low=_clean(text).lower()
    return any(t.lower() in low for t in terms)


# Conservative legal-writing candidates. These are not auto-corrections.
_TYPO_CANDIDATES = {
    "piodana":"pidana",
    "undng":"undang",
    "flafon":"plafon",
    "agugtus":"agustus",
    "jombangt":"jombang",
    "berweang":"berwenang",
    "adaah":"adalah",
    "peuntut":"penuntut",
    "errtor":"error",
    "managemen":"manajemen",
    "diangtkat":"diangkat",
    "terhadeap":"terhadap",
    "fiducia":"fidusia",
    "fiduci":"fidusia",
}


def _textual_typo_findings(text: str) -> List[Dict[str,Any]]:
    low=str(text or "").lower()
    findings=[]
    for wrong,right in _TYPO_CANDIDATES.items():
        if re.search(rf"\b{re.escape(wrong)}\b", low):
            findings.append({
                "type":"POTENTIAL_TEXT_TYPO",
                "severity":"MEDIUM",
                "source_text":wrong,
                "candidate":right,
                "finding":f"Ditemukan bentuk '{wrong}' yang berpotensi salah ketik/OCR.",
                "recommendation":"Cocokkan dengan dokumen asli sebelum koreksi; jangan mengubah substansi secara otomatis.",
            })
    return findings


def _date_number_inconsistencies(text: str) -> List[Dict[str,Any]]:
    findings=[]
    # Example: SK number ends /2021 but nearby explicit date says 2011.
    pat=re.compile(r"(?i)(?P<label>(?:SK|Surat Keputusan)[^\n.]{0,180}?Nomor\s*[:.]?\s*(?P<number>[A-Z0-9./-]+))[^\n.]{0,120}?tanggal\s+(?P<date>\d{1,2}\s+[A-Za-z]+\s+(?P<year>19\d{2}|20\d{2}))")
    for m in pat.finditer(str(text or "")):
        number=m.group('number'); year=m.group('year')
        ny=re.findall(r"(?:19\d{2}|20\d{2})", number)
        if ny and ny[-1] != year:
            findings.append({
                "type":"NUMBER_DATE_INCONSISTENCY",
                "severity":"HIGH",
                "source_text":_clean(m.group(0))[:500],
                "finding":f"Tahun pada nomor dokumen ({ny[-1]}) berbeda dengan tahun pada tanggal eksplisit ({year}).",
                "recommendation":"Periksa salinan SK/dokumen primer. Jangan gunakan salah satu tahun sebagai tempus tanpa verifikasi.",
            })
    return findings


def _name_variants(text: str) -> List[Dict[str,Any]]:
    # Conservative focus on names near defendant/party markers.
    candidates=[]
    for m in re.finditer(r"(?i)(?:terdakwa|atas\s+nama|drs\.?|sdr\.?|sdri\.?)[\s,:-]+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4})", str(text or "")):
        name=_clean(m.group(1)).strip(' ,.;:')
        if len(name)>=7:
            candidates.append(name)
    candidates=_uniq(candidates,20)
    findings=[]
    for i,a in enumerate(candidates):
        for b in candidates[i+1:]:
            ta=a.lower().split(); tb=b.lower().split()
            if not ta or not tb or ta[0] != tb[0]:
                continue
            ratio=SequenceMatcher(None,a.lower(),b.lower()).ratio()
            if 0.72 <= ratio < 0.98 and a.lower()!=b.lower():
                findings.append({
                    "type":"ENTITY_NAME_VARIANT",
                    "severity":"HIGH",
                    "source_text":f"{a} / {b}",
                    "finding":"Terdapat variasi penulisan nama pihak yang cukup mirip dan dapat menimbulkan ambiguitas identitas.",
                    "recommendation":"Samakan dengan identitas pada surat dakwaan/KTP/akta/kuasa asli dan gunakan satu bentuk konsisten.",
                })
    return findings[:8]


def _document_type(text: str) -> str:
    low=_clean(text).lower()
    if 'eksepsi' in low or 'keberatan' in low:
        return 'EKSEPSI_OR_OBJECTION'
    if 'petitum' in low or ('penggugat' in low and 'tergugat' in low):
        return 'CIVIL_PLEADING'
    if 'surat dakwaan' in low or 'dakwaan' in low:
        return 'CRIMINAL_PLEADING'
    if 'perjanjian' in low or 'para pihak sepakat' in low:
        return 'CONTRACT'
    return 'LEGAL_DOCUMENT'


def _structural_review(text: str, doc_type: str) -> Dict[str,Any]:
    low=_clean(text).lower(); expected=[]
    if doc_type=='EKSEPSI_OR_OBJECTION':
        expected=[
            ('authority_identity',('surat kuasa','penasehat hukum','penasihat hukum')),
            ('case_position',('kasus posisi','dakwaan','kronologi')),
            ('grounds',('eksepsi','keberatan','alasan')),
            ('legal_basis',('tentang hukumnya','dasar hukum','pasal','undang-undang')),
            ('conclusion',('kesimpulan',)),
            ('prayer',('permohonan','petitum','memohon')),
        ]
    elif doc_type=='CIVIL_PLEADING':
        expected=[('identity',('penggugat','tergugat')),('posita',('posita','fundamentum','bahwa')),('petitum',('petitum','memohon'))]
    elif doc_type=='CONTRACT':
        expected=[('parties',('para pihak','pihak pertama','pihak kedua')),('object',('objek','ruang lingkup')),('rights',('hak dan kewajiban','kewajiban')),('default',('wanprestasi','cidera janji')),('dispute',('penyelesaian perselisihan','sengketa'))]
    present=[]; missing=[]
    for key,terms in expected:
        if any(t in low for t in terms): present.append(key)
        else: missing.append(key)
    return {
        'document_type':doc_type,
        'present_components':present,
        'missing_components':missing,
        'completeness': round((len(present)/len(expected))*100) if expected else None,
    }


def _argument_findings(result: Dict[str,Any]) -> List[Dict[str,Any]]:
    out=[]
    guard=result.get('reasoning_guard') or {}
    for b in guard.get('boundary_checks') or []:
        out.append({
            'type':b.get('code') or 'ARGUMENT_BOUNDARY',
            'severity':'HIGH',
            'finding':b.get('finding') or '-',
            'recommendation':b.get('required_check') or 'Pisahkan dalil formil, fakta material, dan pokok perkara.',
        })
    tempus=guard.get('tempus') or {}
    if tempus.get('status') in {'TEMPUS_INSUFFICIENT','TEMPUS_REQUIRES_EVENT_DATE','TEMPUS_TRANSITION_REVIEW_REQUIRED'}:
        out.append({
            'type':'TEMPUS_GAP',
            'severity':'CRITICAL',
            'finding':tempus.get('note') or 'Tempus perbuatan belum dapat dipastikan.',
            'recommendation':'Jangan tetapkan norma materiil sebelum tanggal/periode perbuatan dan ketentuan peralihan diverifikasi dari dokumen primer.',
        })
    for a in guard.get('citation_anomalies') or []:
        out.append({
            'type':'LEGAL_CITATION_ANOMALY',
            'severity':'HIGH',
            'finding':f"Rujukan '{a.get('source_text')}' berpotensi salah identitas/penulisan.",
            'recommendation':a.get('instruction') or 'Cocokkan dengan dokumen asli dan sumber resmi.',
            'candidate':a.get('candidate_normalization'),
        })
    return out


def _evidence_findings(result: Dict[str,Any]) -> List[Dict[str,Any]]:
    hygiene=result.get('evidence_hygiene') or {}
    counts=hygiene.get('classification_counts') or {}
    out=[]
    noisy=sum(int(counts.get(k,0) or 0) for k in ('DOCUMENT_METADATA','PARTY_IDENTITY','PROCEDURAL_METADATA','PETITUM_OR_PRAYER','LEGAL_ARGUMENT','PLEADING_ASSERTION','NON_MATERIAL_FRAGMENT'))
    raw=int(hygiene.get('raw_source_items') or 0)
    material=int(hygiene.get('user_visible_material_items') or 0)
    if raw and noisy/raw >= 0.35:
        out.append({
            'type':'SOURCE_NOISE_HIGH',
            'severity':'MEDIUM',
            'finding':f'Sebagian besar isi sumber merupakan metadata, identitas, prosedur, atau argumentasi; item material {material} dari {raw}.',
            'recommendation':'Fokuskan pembuktian pada dokumen primer dan fakta merits; metadata hanya dipakai bila relevan untuk identitas, kewenangan, atau prosedur.',
        })
    gaps=_uniq(result.get('evidentiary_gaps') or [],8)
    for g in gaps[:5]:
        out.append({
            'type':'EVIDENTIARY_GAP',
            'severity':'HIGH',
            'finding':g,
            'recommendation':'Dapatkan dan uji bukti primer yang secara langsung menutup gap ini sebelum menaikkan kesimpulan hukum.',
        })
    return out


def _official_law_findings(result: Dict[str,Any]) -> List[Dict[str,Any]]:
    snap=result.get('case_regulatory_snapshot') or {}
    funnel=snap.get('retrieval_funnel') or {}
    verified=int(funnel.get('verified_applicable') or funnel.get('applicable') or 0)
    out=[]
    if verified==0:
        out.append({
            'type':'NO_VERIFIED_APPLICABLE_LAW',
            'severity':'HIGH',
            'finding':'Belum ada norma yang lolos seluruh gate identitas instrumen, status hukum, tempus, keterkaitan perkara, dan keberlakuan pada perkara.',
            'recommendation':'Pertahankan kesimpulan hukum pada level provisional sampai sumber resmi dan pasal yang benar-benar berlaku terverifikasi.',
        })
    return out


def _strengths(result: Dict[str,Any], doc_type: str) -> List[str]:
    out=[]
    material=material_source_ledger(result.get('source_ledger') or [],limit=80)
    if material:
        out.append(f'{len(material)} item sumber material dapat dipisahkan dari metadata/dalil untuk ditelaah lebih lanjut.')
    guard=result.get('reasoning_guard') or {}
    flags=guard.get('flags') or {}
    if flags.get('fiduciary_nexus'):
        out.append('Isu agunan/fidusia teridentifikasi sebagai faktor recovery/kausalitas yang relevan, bukan sebagai penentu otomatis hasil perkara.')
    if flags.get('objection_context'):
        out.append('Dokumen memiliki posisi prosedural keberatan/eksepsi yang dapat diuji terpisah antara cacat formil dan pembelaan pokok perkara.')
    facts=executive_fact_candidates(result.get('source_ledger') or [],5)
    if facts:
        out.append('Terdapat fakta perkara material yang dapat dijadikan titik awal matriks isu-versus-bukti.')
    return _uniq(out,8)


def _priority(sev: str) -> str:
    return {'CRITICAL':'P1','HIGH':'P1','MEDIUM':'P2','LOW':'P3'}.get(str(sev).upper(),'P2')


def _strategic_recommendation(result: Dict[str,Any], doc_type: str) -> Dict[str,Any]:
    guard=result.get('reasoning_guard') or {}
    boundaries={str(x.get('code')) for x in (guard.get('boundary_checks') or []) if isinstance(x,dict)}
    tempus=(guard.get('tempus') or {}).get('status')
    anomalies=guard.get('citation_anomalies') or []
    if doc_type=='EKSEPSI_OR_OBJECTION':
        priorities=[
            'Utamakan keberatan yang benar-benar bersifat formil/prosedural dan tunjukkan secara spesifik bagian dakwaan yang dianggap tidak memenuhi syarat, bukan hanya menyimpulkan bahwa substansi perkara seharusnya dikualifikasikan lain.',
            'Pisahkan secara tegas: (a) kompetensi/forum, (b) cacat surat dakwaan, dan (c) pembelaan mengenai terbukti atau tidaknya unsur. Jangan memakai argumen merits sebagai pengganti dasar eksepsi formil.',
            'Untuk setiap keberatan, kutip atau identifikasi bagian dakwaan yang diserang, jelaskan cacatnya, akibat hukumnya, lalu hubungkan dengan petitum yang diminta.',
        ]
        if 'FORUM_VS_MERITS' in boundaries:
            priorities.append('Jangan menjadikan fidusia/penggelapan semata sebagai dasar bahwa Pengadilan Tipikor tidak berwenang; gunakan isu itu sebagai pembelaan alternatif terhadap unsur, kausalitas, atau kerugian jika memang didukung bukti.')
        if 'ERROR_IN_PERSONA_VS_ATTRIBUTION' in boundaries:
            priorities.append('Jika mempertahankan dalil error in persona, bedakan salah identitas terdakwa dari argumen bahwa pihak lain lebih bertanggung jawab. Jika identitas terdakwa jelas, arahkan serangan ke atribusi perbuatan/pertanggungjawaban, bukan label error in persona.')
        if tempus in {'TEMPUS_INSUFFICIENT','TEMPUS_REQUIRES_EVENT_DATE','TEMPUS_TRANSITION_REVIEW_REQUIRED'}:
            priorities.append('Jadikan tempus delicti sebagai audit wajib: pastikan tanggal/periode perbuatan sebelum menentukan norma materiil dan ketentuan peralihan yang dipakai.')
        if anomalies:
            priorities.append('Verifikasi dan rapikan seluruh identitas peraturan dari dakwaan asli. Salah tahun/nomor undang-undang jangan dikoreksi secara diam-diam atau diasumsikan sebagai kesalahan JPU sebelum sumber primer diperiksa.')
        outline=[
            'I. Pendahuluan, identitas, dan kedudukan penasihat hukum',
            'II. Objek eksepsi dan bagian surat dakwaan yang secara spesifik dipersoalkan',
            'III. Keberatan formil/prosedural per isu, masing-masing dengan teks dakwaan, cacat, dasar hukum, dan akibat',
            'IV. Audit tempus dan identitas norma yang dirujuk dalam dakwaan',
            'V. Pemisahan tegas antara keberatan formil dan pembelaan pokok perkara',
            'VI. Kesimpulan',
            'VII. Petitum yang konsisten dengan jenis keberatan yang berhasil dibangun',
        ]
        return {'approach':'REBUILD_OBJECTION_AROUND_FORMAL_DEFECTS','priorities':priorities,'recommended_outline':outline}
    if doc_type=='CIVIL_PLEADING':
        return {'approach':'ISSUE_FACT_EVIDENCE_RULE_PETITUM_ALIGNMENT','priorities':[
            'Pastikan setiap posita material mempunyai fakta sumber dan bukti yang dapat ditelusuri.',
            'Pastikan petitum merupakan konsekuensi logis dari posita dan dasar hukum, bukan tuntutan yang berdiri sendiri.',
            'Audit kompetensi, para pihak, legal standing, tempus, dan hubungan hukum sebelum menyusun kesimpulan merits.',
        ],'recommended_outline':['Identitas & standing','Kronologi/fakta material','Isu hukum','Dasar hukum terverifikasi','Analisis per isu','Petitum primer/subsider']}
    if doc_type=='CONTRACT':
        return {'approach':'CLAUSE_RISK_REWRITE','priorities':[
            'Pisahkan kewajiban, kondisi pemicu, bukti pemenuhan, dan akibat wanprestasi untuk setiap klausul material.',
            'Cari konflik internal, istilah tidak konsisten, tanggal/angka yang tidak sinkron, dan klausul yang tidak memiliki mekanisme eksekusi.',
            'Ubah temuan menjadi redraft copy-ready setelah legal basis dan konteks transaksi diverifikasi.',
        ],'recommended_outline':['Para pihak & definisi','Objek/ruang lingkup','Hak & kewajiban','Pembayaran/kinerja','Default & remedies','Force majeure','Liability/indemnity','Dispute/forum','Boilerplate']}
    return {'approach':'ISSUE_EVIDENCE_LAW_RECOMMENDATION','priorities':[
        'Bangun analisis dari fakta material dan bukti primer, bukan dari label dokumen atau keyword.',
        'Uji identitas norma, status berlaku, tempus, keterkaitan perkara, dan unsur sebelum menarik kesimpulan spesifik.',
        'Ubah setiap gap menjadi tindakan verifikasi yang konkret dan dapat dikerjakan.',
    ],'recommended_outline':['Fakta material','Isu hukum','Bukti pendukung/kontra','Norma terverifikasi','Analisis','Kelemahan/counter-argument','Rekomendasi']}


def build_professional_review(result: Dict[str,Any], source_text: str | None = None) -> Dict[str,Any]:
    text=source_text if source_text is not None else result.get('source_text') or ''
    doc_type=_document_type(text)
    structure=_structural_review(text,doc_type)

    findings=[]
    findings.extend(_textual_typo_findings(text))
    findings.extend(_date_number_inconsistencies(text))
    findings.extend(_name_variants(text))
    findings.extend(_argument_findings(result))
    findings.extend(_evidence_findings(result))
    findings.extend(_official_law_findings(result))

    # Deduplicate by type+finding while keeping the strongest first.
    rank={'CRITICAL':4,'HIGH':3,'MEDIUM':2,'LOW':1}
    uniq=[]; seen=set()
    for f in sorted(findings,key=lambda x:rank.get(str(x.get('severity')).upper(),0),reverse=True):
        key=(str(f.get('type')), _clean(f.get('finding')).lower())
        if key in seen: continue
        seen.add(key); uniq.append(f)
    findings=uniq[:30]

    recommendations=[]
    for i,f in enumerate(findings,1):
        recommendations.append({
            'priority':_priority(f.get('severity')),
            'issue':f.get('type') or 'REVIEW_FINDING',
            'action':f.get('recommendation') or 'Lakukan verifikasi profesional.',
            'basis':f.get('finding') or '-',
        })
    # Structural missing components become recommendations but not allegations.
    for comp in structure.get('missing_components') or []:
        recommendations.append({
            'priority':'P2',
            'issue':'DOCUMENT_STRUCTURE',
            'action':f'Pertimbangkan melengkapi komponen dokumen: {comp}.',
            'basis':'Komponen yang lazim untuk tipe dokumen ini belum terdeteksi secara eksplisit.',
        })

    critical=[f for f in findings if str(f.get('severity')).upper()=='CRITICAL']
    high=[f for f in findings if str(f.get('severity')).upper()=='HIGH']
    readiness='HOLD_FOR_VERIFICATION' if critical else ('REVISE_BEFORE_RELIANCE' if high else 'PROVISIONAL_REVIEW_COMPLETE')

    return {
        'engine':'LEXICORE_PROFESSIONAL_REVIEW_V1',
        'policy':'MULTI_PASS_FAIL_CLOSED',
        'passes':[
            'READ_AND_CLASSIFY_DOCUMENT',
            'SEPARATE_FACT_ARGUMENT_METADATA',
            'CHECK_TEXT_ENTITY_DATE_CITATION_ANOMALIES',
            'TEST_TEMPUS_IDENTITY_NEXUS_AND_EVIDENCE_GATES',
            'ADVERSARIAL_ARGUMENT_REVIEW',
            'SYNTHESIZE_STRENGTHS_WEAKNESSES',
            'BUILD_PRIORITIZED_RECOMMENDATIONS',
        ],
        'document_structure':structure,
        'strengths':_strengths(result,doc_type),
        'findings':findings,
        'recommendations':recommendations[:24],
        'strategic_recommendation':_strategic_recommendation(result,doc_type),
        'review_status':readiness,
        'professional_verification':'PENDING',
        'disclaimer':'Review ini merupakan analisis kerja hukum berbantuan sistem. Setiap koreksi, inferensi, dan rekomendasi wajib diverifikasi lawyer terhadap dokumen primer dan hukum positif yang berlaku.',
    }


def apply_professional_review(result: Dict[str,Any], source_text: str | None = None) -> Dict[str,Any]:
    result=dict(result or {})
    result['professional_review']=build_professional_review(result,source_text)
    return result
