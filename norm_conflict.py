"""LexiCore Material Norm Conflict Filtering.

A hierarchy difference is a relationship, not a conflict. This detector only
surfaces a conflict candidate when the norms plausibly regulate the same
subject matter and there is a concrete antinomy/temporal/specialis issue to
verify. Ordinary hierarchy/chronology relationships are kept separate.

The module never makes a final determination of applicable law.
"""
from __future__ import annotations
from typing import Any, Dict, List, Set
import re

from regulatory_intelligence import compare_regulations

_STOP = {
    'pasal','tahun','undang','nomor','tentang','yang','dan','atau','dalam','atas',
    'dengan','untuk','pada','dari','serta','ketentuan','peraturan','hukum','wajib',
    'resmi','verifikasi','berlaku','indonesia','republik','ayat','norma','terkait',
    'asas','kerugian','kitab','pidana','putusan','melawan','negara','keuangan','hukum'
}


def _tokens(value: str) -> Set[str]:
    return {
        w for w in re.findall(r'[a-z0-9]+', (value or '').lower())
        if len(w) >= 4 and w not in _STOP and not w.isdigit()
    }


def _hit_subject_terms(hit: Dict[str, Any]) -> Set[str]:
    terms: Set[str] = set()
    reg = (hit or {}).get('regulation') or {}
    terms |= _tokens(reg.get('tentang') or '')
    # Use matched articles first; they best represent why the regulation was retrieved.
    arts = (hit or {}).get('matched_articles') or []
    for art in arts[:5]:
        terms |= _tokens(art.get('topic') or '')
        for kw in art.get('keywords') or []:
            terms |= _tokens(str(kw))
    return terms


def _same_subject(a_hit: Dict[str, Any], b_hit: Dict[str, Any]) -> Dict[str, Any]:
    a_terms = _hit_subject_terms(a_hit)
    b_terms = _hit_subject_terms(b_hit)
    shared = sorted(a_terms & b_terms)
    union = a_terms | b_terms
    jaccard = (len(shared) / len(union)) if union else 0.0
    # Material overlap must be meaningful, not just shared legal vocabulary.
    # A modest Jaccard threshold plus two specific terms filters out pairs such
    # as UUD-vs-KUHP or KUHP-vs-KUHAP that merely share generic legal words.
    same = len(shared) >= 2 and jaccard >= 0.16
    return {
        'same_subject': same,
        'shared_terms': shared[:10],
        'jaccard': round(jaccard, 3),
        'a_terms': sorted(a_terms)[:20],
        'b_terms': sorted(b_terms)[:20],
    }


def _structured_pairwise(regulatory_matches: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    hits=[]
    seen=set()
    for hit in regulatory_matches or []:
        reg=(hit or {}).get('regulation') or {}
        rid=reg.get('id')
        if rid and rid not in seen:
            seen.add(rid); hits.append(hit)
    screens=[]
    for i in range(min(len(hits),6)):
        for j in range(i+1,min(len(hits),6)):
            a_hit,b_hit=hits[i],hits[j]
            p=compare_regulations(a_hit.get('regulation') or {}, b_hit.get('regulation') or {})
            p['material_screen']=_same_subject(a_hit,b_hit)
            screens.append(p)
    return screens[:12]


def _relationship_from_screen(p: Dict[str, Any]) -> Dict[str, Any]:
    hs=p.get('lex_superior_screen') or {}
    ts=p.get('lex_posterior_screen') or {}
    material=p.get('material_screen') or {}
    relation=[]
    if hs.get('result') in ('A_HIGHER','B_HIGHER'):
        relation.append('HIERARCHY')
    if ts.get('result') in ('A_NEWER','B_NEWER'):
        relation.append('CHRONOLOGY')
    return {
        'classification':'RELATIONSHIP_ONLY',
        'relations':relation or ['COEXISTENCE'],
        'norm_a':p.get('norm_a'),
        'norm_b':p.get('norm_b'),
        'same_subject_matter':bool(material.get('same_subject')),
        'shared_subject_terms':material.get('shared_terms') or [],
        'note':'Perbedaan tingkat hierarki atau tahun bukan konflik norma. Hubungan ini baru menjadi conflict candidate jika materi yang sama mengandung kewajiban, larangan, hak, kewenangan, atau akibat hukum yang tidak dapat diterapkan bersamaan.',
        'verification_status':'PROFESSIONAL VERIFICATION: PENDING',
    }


def analyze_conflicts(provisions: List[str] | None, facts_context: str = '', regulatory_matches: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    provisions=provisions or []
    text=(' '.join(provisions)+' '+(facts_context or '')).lower()
    conflicts=[]
    relationships=[]
    temporal=[]
    lex_specialis=[]

    # 1) Criminal/private-law coexistence is a relationship, not an antinomy.
    criminal = any(k in text for k in ['korupsi','tipikor','pasal 603','pasal 604','pidana'])
    private = any(k in text for k in ['kuhperdata','pasal 1365','pasal 1320','pasal 1243','wanprestasi','perjanjian','kredit'])
    explicit_antinomy = any(k in text for k in ['bertentangan','tidak dapat diterapkan bersama','mengesampingkan','lex specialis'])
    if criminal and private:
        relation={
            'classification':'RELATIONSHIP_ONLY',
            'relations':['CROSS_DOMAIN_INTERACTION'],
            'norm_a':{'citation':'Norma pidana/pidana khusus yang relevan'},
            'norm_b':{'citation':'Norma perdata/tata kelola yang relevan'},
            'same_subject_matter':None,
            'shared_subject_terms':[],
            'note':'Keberadaan ranah pidana dan perdata/tata kelola dalam perkara yang sama tidak dengan sendirinya merupakan konflik norma. Uji antinomi material diperlukan sebelum asas lex specialis dipertimbangkan.',
            'verification_status':'PROFESSIONAL VERIFICATION: PENDING',
        }
        relationships.append(relation)
        if explicit_antinomy:
            conflicts.append({
                'type':'LEX_SPECIALIS_CANDIDATE','severity':'POTENTIAL_CONFLICT','classification':'POTENTIAL_CONFLICT',
                'rule_principle':'Lex Specialis Derogat Legi Generali',
                'special_norm':'Norma khusus yang relevan — identitas final wajib diverifikasi',
                'general_norm':'Norma umum yang relevan — identitas final wajib diverifikasi',
                'legal_reasoning':'Teks perkara secara eksplisit mengindikasikan potensi pertentangan/pengesampingan. Kandidat ini tetap harus lolos uji kesamaan subjek, objek, perilaku, akibat hukum, dan ketidakmungkinan penerapan bersama.',
                'recommendation_for_counsel':'Bandingkan teks resmi kedua norma dan nyatakan lex specialis hanya bila antinomi material benar-benar terbukti.',
                'verification_status':'PROFESSIONAL VERIFICATION: PENDING',
            })

    # 2) Temporal issue only when the context actually carries an earlier event
    # year and later criminal-law years, rather than merely seeing a newer act.
    event_years={int(y) for y in re.findall(r'\b(19\d{2}|20\d{2})\b', facts_context or '')}
    cited_years={int(y) for y in re.findall(r'\b(19\d{2}|20\d{2})\b', ' '.join(provisions))}
    later_years={y for y in cited_years if event_years and y > min(event_years)}
    explicit_temporal=any(k in text for k in ['tempus','non-retroaktif','asas legalitas','aturan peralihan'])
    if (event_years and later_years) or explicit_temporal:
        conflicts.append({
            'type':'TEMPORAL_APPLICABILITY','severity':'POTENTIAL_CONFLICT',
            'classification':'POTENTIAL_CONFLICT',
            'rule_principle':'Asas legalitas + tempus + aturan peralihan / lex mitior bila relevan',
            'newer_norm':'Norma yang mulai berlaku setelah sebagian fakta/peristiwa',
            'older_norm':'Norma pada tempus perbuatan',
            'legal_reasoning':'Ada indikator perbedaan waktu antara peristiwa dan norma yang dirujuk. Tahun yang lebih baru tidak otomatis berlaku atau menggantikan norma lama; tanggal efektif, aturan transisi, perubahan/pencabutan, dan ketentuan yang lebih menguntungkan harus diuji.',
            'recommendation_for_counsel':'Buat tabel tanggal peristiwa, pengundangan, mulai berlaku, perubahan, unsur dan sanksi. Verifikasi aturan peralihan pada sumber primer.',
            'verification_status':'PROFESSIONAL VERIFICATION: PENDING',
        })
        temporal.append({'old_law':'Norma pada tempus perbuatan','new_law':'Norma setelah peristiwa','transition_rule':'WAJIB DIVERIFIKASI','advice':'Jangan menyimpulkan applicability dari tahun saja.'})

    # 3) Internal/subordinate instruments are a hierarchy relationship unless
    # a material contradiction is actually identified.
    if any(k in text for k in ['perda','permen','perdir','surat edaran direksi','sop','pkpb','pedoman internal','peraturan internal','pojk']):
        relationships.append({
            'classification':'RELATIONSHIP_ONLY',
            'relations':['HIERARCHY','DELEGATION_CHECK'],
            'norm_a':{'citation':'Norma lebih tinggi/berwenang yang relevan'},
            'norm_b':{'citation':'Instrumen subordinat/internal yang disebut dalam perkara'},
            'same_subject_matter':None,
            'shared_subject_terms':[],
            'note':'Pelanggaran SOP, surat edaran, pedoman internal atau regulasi lembaga dapat relevan terhadap tata kelola. Hubungan hierarki/delegasi harus diperiksa, tetapi itu bukan konflik norma dan tidak otomatis menjadi unsur pidana.',
            'verification_status':'PROFESSIONAL VERIFICATION: PENDING',
        })

    pairwise=_structured_pairwise(regulatory_matches)
    for p in pairwise:
        material=p.get('material_screen') or {}
        hs=p.get('lex_superior_screen') or {}
        ts=p.get('lex_posterior_screen') or {}
        # Hierarchy-only / chronology-only screens are relationships, not conflicts.
        relationships.append(_relationship_from_screen(p))
        # Same subject + different years is an actionable temporal candidate,
        # but still not a confirmed contradiction.
        same_rank=(p.get('norm_a') or {}).get('rank') == (p.get('norm_b') or {}).get('rank')
        if material.get('same_subject') and same_rank and ts.get('result') in ('A_NEWER','B_NEWER') and any(k in text for k in ['bertentangan','tidak dapat diterapkan bersama','mengesampingkan','dicabut','mengubah']):
            a=(p.get('norm_a') or {}).get('citation','Norm A')
            b=(p.get('norm_b') or {}).get('citation','Norm B')
            key=frozenset([a,b,'TEMPORAL'])
            if not any(c.get('_dedupe_key')==key for c in conflicts):
                conflicts.append({
                    '_dedupe_key':key,
                    'type':'LEX_POSTERIOR_CANDIDATE','severity':'POTENTIAL_CONFLICT',
                    'classification':'POTENTIAL_CONFLICT',
                    'rule_principle':'Lex Posterior / transitional-law screen',
                    'older_norm': b if ts.get('result')=='A_NEWER' else a,
                    'newer_norm': a if ts.get('result')=='A_NEWER' else b,
                    'legal_reasoning':f"Korpus menemukan irisan materi ({', '.join((material.get('shared_terms') or [])[:5]) or 'subject matter terkait'}) dan perbedaan tahun. Ini hanya conflict candidate; perlu dibandingkan bunyi norma, status perubahan/pencabutan, tanggal efektif dan aturan transisi.",
                    'recommendation_for_counsel':'Bandingkan teks resmi kedua norma pada isu yang sama dan tentukan apakah keduanya benar-benar tidak dapat diterapkan bersama.',
                    'verification_status':'PROFESSIONAL VERIFICATION: PENDING',
                })

    # Remove internal dedupe metadata and collapse repeated logical conflicts.
    cleaned=[]; seen=set()
    for c in conflicts:
        c.pop('_dedupe_key',None)
        sig=(c.get('type'),c.get('older_norm'),c.get('newer_norm'),c.get('special_norm'),c.get('general_norm'))
        if sig in seen: continue
        seen.add(sig); cleaned.append(c)
    conflicts=cleaned[:4]

    # Relationship dedupe and cap. These belong conceptually in Regulatory Corpus.
    rel_clean=[]; rel_seen=set()
    for r in relationships:
        a=((r.get('norm_a') or {}).get('citation') or '')
        b=((r.get('norm_b') or {}).get('citation') or '')
        sig=(tuple(r.get('relations') or []),a,b)
        if sig in rel_seen: continue
        rel_seen.add(sig); rel_clean.append(r)
    relationships=rel_clean[:12]

    acts=[]
    for p in provisions:
        if p and p not in acts: acts.append(p)
    for hit in regulatory_matches or []:
        reg=(hit or {}).get('regulation') or {}
        label=reg.get('nomor') or reg.get('tentang')
        if label and label not in acts: acts.append(label)

    confirmed=sum(1 for c in conflicts if c.get('classification')=='CONFIRMED_CONFLICT')
    potential=sum(1 for c in conflicts if c.get('classification')=='POTENTIAL_CONFLICT')
    return {
        'hierarchy_level':3,
        'hierarchy_label':'Material-first conflict screening; hierarchy/chronology alone are relationships, not conflicts',
        'acts_analyzed':acts or ['Peraturan Perundang-undangan Terkait'],
        'summary':{
            'confirmed_conflicts':confirmed,
            'potential_conflicts':potential,
            'relationship_only':len(relationships),
            'material_conflicts_shown':len(conflicts),
        },
        'conflicts_detected':conflicts,
        'relationships_only':relationships,
        'lex_specialis_matrix':lex_specialis,
        'temporal_transitions':temporal,
        'structured_pairwise_screens':pairwise,
        'detector_mode':'MATERIAL_NORM_CONFLICT_FILTER_V1_3_3_3',
        'coverage_note':'Perbedaan hierarki dan kronologi tidak diperlakukan sebagai konflik. Kandidat konflik hanya ditampilkan bila terdapat indikasi antinomi material dan tetap memerlukan verifikasi teks resmi, kewenangan/delegasi, tanggal efektif, aturan peralihan, serta status perubahan/pencabutan.',
        'professional_verification':'PENDING',
    }
