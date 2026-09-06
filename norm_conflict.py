"""LexiCore Norm Conflict Analyzer v1.3.13.6.

Material-first analysis for Menu 7.  A difference in hierarchy or year alone is
not a contradiction.  The engine maps Rule A against Rule B/C/D/... and, where
there is enough deterministic information, applies the conflict principles in
this order:

    1. Lex superior derogat legi inferiori
    2. Lex specialis derogat legi generali
    3. Lex posterior derogat legi priori

The order prevents a lower norm from defeating a higher norm merely because it
is newer or more specific.  Any final result still carries professional/source
verification state; the engine never invents a contradiction or provision.
"""
from __future__ import annotations
from typing import Any, Dict, List, Set, Optional
import re

from regulatory_intelligence import compare_regulations

_STOP = {
    'pasal','tahun','undang','nomor','tentang','yang','dan','atau','dalam','atas',
    'dengan','untuk','pada','dari','serta','ketentuan','peraturan','hukum','wajib',
    'resmi','verifikasi','berlaku','indonesia','republik','ayat','norma','terkait',
    'asas','kerugian','kitab','pidana','putusan','melawan','negara','keuangan'
}

# Statutory hierarchy screen used only for conflict analysis.  PERMA is kept as
# a non-commensurable judicial instrument because it is not mechanically placed
# in Article-7 statutory hierarchy; its authority/scope must be verified.
_MANUAL_RANK = {
    'UUD': 1, 'TAP_MPR': 2, 'UU': 3, 'PERPPU': 3, 'PP': 4, 'PERPRES': 5,
    'PERMEN': 6, 'PERATURAN_MENTERI': 6, 'PERMK': 6, 'PER_LEMBAGA': 6,
    'PERKAP': 6, 'POJK': 6, 'PERDA_PROV': 7, 'PERDA_KAB': 8, 'PERDA': 8,
}


def _tokens(value: str) -> Set[str]:
    return {w for w in re.findall(r'[a-z0-9]+', (value or '').lower())
            if len(w) >= 4 and w not in _STOP and not w.isdigit()}


def _hit_subject_terms(hit: Dict[str, Any]) -> Set[str]:
    terms: Set[str] = set()
    reg = (hit or {}).get('regulation') or {}
    terms |= _tokens(reg.get('tentang') or '')
    for art in ((hit or {}).get('matched_articles') or [])[:5]:
        terms |= _tokens(art.get('topic') or '')
        for kw in art.get('keywords') or []:
            terms |= _tokens(str(kw))
    return terms


def _same_subject(a_hit: Dict[str, Any], b_hit: Dict[str, Any]) -> Dict[str, Any]:
    a_terms, b_terms = _hit_subject_terms(a_hit), _hit_subject_terms(b_hit)
    shared = sorted(a_terms & b_terms); union = a_terms | b_terms
    jaccard = (len(shared) / len(union)) if union else 0.0
    return {'same_subject': len(shared) >= 2 and jaccard >= 0.16,
            'shared_terms': shared[:10], 'jaccard': round(jaccard, 3),
            'a_terms': sorted(a_terms)[:20], 'b_terms': sorted(b_terms)[:20]}


def _structured_pairwise(regulatory_matches: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    hits=[]; seen=set()
    for hit in regulatory_matches or []:
        reg=(hit or {}).get('regulation') or {}; rid=reg.get('id')
        if rid and rid not in seen: seen.add(rid); hits.append(hit)
    screens=[]
    for i in range(min(len(hits),6)):
        for j in range(i+1,min(len(hits),6)):
            p=compare_regulations(hits[i].get('regulation') or {}, hits[j].get('regulation') or {})
            p['material_screen']=_same_subject(hits[i],hits[j]); screens.append(p)
    return screens[:12]


def _norm_kind(text: str) -> str:
    u=(text or '').upper()
    if 'PERMA' in u or 'PERATURAN MAHKAMAH AGUNG' in u: return 'PERMA'
    if 'PERMK' in u or 'PMK' in u or 'PERATURAN MENTERI KEUANGAN' in u: return 'PERMK'
    if 'PERKAP' in u or 'PERATURAN KEPALA KEPOLISIAN' in u or 'PERATURAN KEPOLISIAN' in u: return 'PERKAP'
    if 'PERATURAN MENTERI' in u or re.search(r'\bPERMEN',u): return 'PERMEN'
    if 'PERATURAN LEMBAGA' in u or 'POJK' in u: return 'PER_LEMBAGA' if 'POJK' not in u else 'POJK'
    if 'PERATURAN PRESIDEN' in u or 'PERPRES' in u: return 'PERPRES'
    if re.search(r'\bPP\b',u) or 'PERATURAN PEMERINTAH' in u: return 'PP'
    if 'PERPPU' in u: return 'PERPPU'
    if re.search(r'\bUU\b',u) or 'UNDANG-UNDANG' in u or 'UNDANG UNDANG' in u: return 'UU'
    if 'PERDA PROV' in u or 'PERATURAN DAERAH PROV' in u: return 'PERDA_PROV'
    if re.search(r'\bPERDA\b',u) or 'PERATURAN DAERAH' in u: return 'PERDA'
    if 'UUD' in u: return 'UUD'
    return 'UNKNOWN'


def _manual_norm(text: str, label: str) -> Dict[str, Any]:
    years=[int(x) for x in re.findall(r'\b(19\d{2}|20\d{2})\b',text or '')]
    kind=_norm_kind(text)
    rank=None if kind=='PERMA' else _MANUAL_RANK.get(kind)
    return {'label':label,'citation':text.strip() or label,'type':kind,'rank':rank,
            'year':years[-1] if years else None,'tokens':sorted(_tokens(text))}


def _manual_same_subject(a: Dict[str,Any], b: Dict[str,Any], context: str) -> Dict[str,Any]:
    at,bt=set(a.get('tokens') or []),set(b.get('tokens') or [])
    shared=sorted(at & bt); union=at|bt
    score=len(shared)/len(union) if union else 0.0
    ctx=_tokens(context)
    context_bridge=bool((at & ctx) and (bt & ctx))
    return {'same_subject': bool(len(shared)>=1 or context_bridge), 'shared_terms':shared[:8],
            'context_bridge':context_bridge,'jaccard':round(score,3)}


def _explicit_antinomy(context: str) -> bool:
    t=(context or '').lower()
    keys=['bertentangan','kontradiksi','tidak dapat diterapkan bersama','mengesampingkan',
          'melarang sedangkan','mewajibkan sedangkan','tidak sinkron','antinomi']
    return any(k in t for k in keys)


def _specificity_hint(a: Dict[str,Any], b: Dict[str,Any], context: str) -> Optional[str]:
    """Return A_SPECIAL / B_SPECIAL only when the user explicitly signals scope."""
    t=(context or '').lower()
    ac=(a.get('citation') or '').lower(); bc=(b.get('citation') or '').lower()
    if any(k in t for k in ['aturan a merupakan lex specialis','norma a merupakan lex specialis','aturan a lebih khusus']): return 'A_SPECIAL'
    if any(k in t for k in ['aturan b merupakan lex specialis','norma b merupakan lex specialis','aturan b lebih khusus']): return 'B_SPECIAL'
    # Explicit words embedded in citations can support a screen but not generic title length.
    if 'khusus' in ac and 'khusus' not in bc: return 'A_SPECIAL'
    if 'khusus' in bc and 'khusus' not in ac: return 'B_SPECIAL'
    return None


def _resolve_pair(a: Dict[str,Any], b: Dict[str,Any], context: str, same_subject: Dict[str,Any]) -> Dict[str,Any]:
    antinomy=_explicit_antinomy(context)
    same=bool(same_subject.get('same_subject'))
    ar,br=a.get('rank'),b.get('rank'); ay,by=a.get('year'),b.get('year')
    base={
        'norm_a':{k:a.get(k) for k in ('label','citation','type','year','rank')},
        'norm_b':{k:b.get(k) for k in ('label','citation','type','year','rank')},
        'same_subject_matter':same,
        'shared_subject_terms':same_subject.get('shared_terms') or [],
        'antinomy_identified':antinomy,
        'contradiction_analysis':'Belum ada antinomi material yang dapat dibuktikan dari input.' if not antinomy else 'Konteks secara eksplisit menunjukkan pertentangan/ketidakmungkinan penerapan bersama; resolver menguji hierarki, kekhususan, lalu waktu.',
        'principle_applied':'NONE',
        'applicable_law':'NOT_DETERMINED',
        'resolution_status':'PROFESSIONAL_VERIFICATION_REQUIRED',
        'legal_effect':'Belum boleh menyatakan satu norma mengesampingkan norma lain.',
    }
    if not (same and antinomy):
        base['classification']='RELATIONSHIP_ONLY' if not antinomy else 'POTENTIAL_CONFLICT'
        return base

    # 1. LEX SUPERIOR — only for commensurable statutory ranks.
    if ar is not None and br is not None and ar != br:
        winner=a if ar < br else b; loser=b if winner is a else a
        base.update({
            'classification':'RESOLVED_CONFLICT_CANDIDATE',
            'principle_applied':'LEX_SUPERIOR',
            'applicable_law':winner.get('citation'),
            'displaced_law':loser.get('citation'),
            'resolution_status':'DETERMINISTIC_HIERARCHY_RESULT — OFFICIAL TEXT/DELEGATION VERIFICATION REQUIRED',
            'legal_effect':f"{winner.get('citation')} diprioritaskan terhadap {loser.get('citation')} sepanjang keduanya benar-benar mengatur objek yang sama dan konflik material terkonfirmasi.",
            'contradiction_analysis':base['contradiction_analysis']+' Kedua instrumen berada pada tingkat hierarki berbeda; norma inferior tidak dapat menyimpangi norma superior tanpa dasar delegasi yang sah.'
        })
        return base

    # PERMA vs statutory instruments cannot be mechanically ranked here.
    if (a.get('type')=='PERMA') != (b.get('type')=='PERMA'):
        base.update({'classification':'POTENTIAL_CONFLICT','principle_applied':'LEX_SUPERIOR_SCREEN_INCONCLUSIVE',
                     'resolution_status':'AUTHORITY_AND_SCOPE_VERIFICATION_REQUIRED',
                     'legal_effect':'Kedudukan dan ruang kewenangan PERMA terhadap norma yang dibandingkan harus diuji berdasarkan kewenangan pembentuk, delegasi, dan materi muatan; tidak dipaksakan ke hierarki statuter.'})
        return base

    # 2. LEX SPECIALIS — same rank/commensurable and explicit specificity.
    sp=_specificity_hint(a,b,context)
    if sp:
        winner=a if sp=='A_SPECIAL' else b; loser=b if winner is a else a
        base.update({'classification':'RESOLVED_CONFLICT_CANDIDATE','principle_applied':'LEX_SPECIALIS',
                     'applicable_law':winner.get('citation'),'displaced_law':loser.get('citation'),
                     'resolution_status':'SPECIFICITY_RESULT — SCOPE/ELEMENT VERIFICATION REQUIRED',
                     'legal_effect':f"{winner.get('citation')} diprioritaskan untuk ruang lingkup khusus yang sama; norma umum tetap berlaku di luar ruang khusus tersebut.",
                     'contradiction_analysis':base['contradiction_analysis']+' Input memberi indikator eksplisit bahwa salah satu norma memiliki ruang lingkup lebih khusus.'})
        return base

    # 3. LEX POSTERIOR — same hierarchy, same subject, explicit antinomy, years known.
    if ar is not None and br is not None and ar==br and ay and by and ay!=by:
        winner=a if ay>by else b; loser=b if winner is a else a
        base.update({'classification':'RESOLVED_CONFLICT_CANDIDATE','principle_applied':'LEX_POSTERIOR',
                     'applicable_law':winner.get('citation'),'displaced_law':loser.get('citation'),
                     'resolution_status':'CHRONOLOGY_RESULT — REPEAL/TRANSITION/TEMPUS VERIFICATION REQUIRED',
                     'legal_effect':f"{winner.get('citation')} menjadi kandidat norma yang lebih baru pada tingkat setara, sepanjang tidak ada aturan peralihan, lex specialis, atau ketentuan yang mempertahankan norma lama.",
                     'contradiction_analysis':base['contradiction_analysis']+' Tingkat hierarki setara dan tahun berbeda; lex posterior hanya digunakan setelah lex superior dan lex specialis tidak menentukan hasil.'})
        return base

    base.update({'classification':'POTENTIAL_CONFLICT','principle_applied':'UNRESOLVED',
                 'resolution_status':'MORE_EXACT_TEXT_REQUIRED',
                 'legal_effect':'Perlu teks pasal/ayat, ruang lingkup subjek-objek, tanggal efektif, serta status perubahan/pencabutan untuk menentukan applicable law.'})
    return base


def _manual_matrix(provisions: List[str], context: str) -> List[Dict[str,Any]]:
    """Rule A is compared to every subsequent Rule B/C/D/... as requested."""
    if len(provisions)<2: return []
    anchor=_manual_norm(provisions[0],'Aturan A')
    rows=[]
    for idx,p in enumerate(provisions[1:],start=1):
        label=f"Aturan {chr(65+idx)}" if idx<26 else f"Aturan {idx+1}"
        other=_manual_norm(p,label)
        same=_manual_same_subject(anchor,other,context)
        row=_resolve_pair(anchor,other,context,same)
        row['pair_label']=f"Aturan A vs {label}"
        rows.append(row)
    return rows


def _relationship_from_screen(p: Dict[str, Any]) -> Dict[str, Any]:
    hs=p.get('lex_superior_screen') or {}; ts=p.get('lex_posterior_screen') or {}; material=p.get('material_screen') or {}
    relation=[]
    if hs.get('result') in ('A_HIGHER','B_HIGHER'): relation.append('HIERARCHY')
    if ts.get('result') in ('A_NEWER','B_NEWER'): relation.append('CHRONOLOGY')
    return {'classification':'RELATIONSHIP_ONLY','relations':relation or ['COEXISTENCE'],
            'norm_a':p.get('norm_a'),'norm_b':p.get('norm_b'),
            'same_subject_matter':bool(material.get('same_subject')),
            'shared_subject_terms':material.get('shared_terms') or [],
            'note':'Perbedaan hierarki atau tahun saja bukan konflik norma. Antinomi material harus dibuktikan sebelum asas konflik dipakai.',
            'verification_status':'PROFESSIONAL VERIFICATION: PENDING'}


def analyze_conflicts(provisions: List[str] | None, facts_context: str = '', regulatory_matches: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    provisions=[p.strip() for p in (provisions or []) if str(p).strip()]
    pairwise=_structured_pairwise(regulatory_matches)
    relationships=[_relationship_from_screen(p) for p in pairwise]
    matrix=_manual_matrix(provisions,facts_context)
    # Manual A-vs-B/C/D comparisons that merely coexist must also be exposed
    # through relationships_only. Previously they were counted in summary but
    # omitted from the returned list, causing cross-domain coexistence to look
    # like no relationship was detected at all.
    relationships.extend([dict(r) for r in matrix if r.get('classification')=='RELATIONSHIP_ONLY'])

    # If no manual comparison was supplied, preserve a material-first corpus screen.
    conflicts=[]
    for row in matrix:
        if row.get('classification') in ('POTENTIAL_CONFLICT','RESOLVED_CONFLICT_CANDIDATE'):
            conflicts.append({
                'type':'PAIRWISE_NORM_CONFLICT','classification':row.get('classification'),
                'rule_principle':row.get('principle_applied'),
                'legal_reasoning':row.get('contradiction_analysis'),
                'recommendation_for_counsel':row.get('legal_effect'),
                'applicable_law':row.get('applicable_law'),
                'verification_status':row.get('resolution_status'),
            })

    acts=[]
    for p in provisions:
        if p not in acts: acts.append(p)
    for hit in regulatory_matches or []:
        reg=(hit or {}).get('regulation') or {}; label=reg.get('nomor') or reg.get('tentang')
        if label and label not in acts: acts.append(label)

    resolved=sum(1 for r in matrix if r.get('classification')=='RESOLVED_CONFLICT_CANDIDATE')
    potential=sum(1 for r in matrix if r.get('classification')=='POTENTIAL_CONFLICT')
    relationship=len(relationships)
    return {
        'hierarchy_level':3,
        'hierarchy_label':'Material conflict + strict principle resolver',
        'acts_analyzed':acts or ['Peraturan Perundang-undangan Terkait'],
        'summary':{'resolved_candidates':resolved,'confirmed_conflicts':0,'potential_conflicts':potential,
                   'relationship_only':relationship,'material_conflicts_shown':len(conflicts)},
        'rule_comparison_matrix':matrix,
        'conflicts_detected':conflicts[:12],
        'relationships_only':relationships[:12],
        'principle_order':['LEX_SUPERIOR','LEX_SPECIALIS','LEX_POSTERIOR'],
        'principle_method':{
            'LEX_SUPERIOR':'Dipakai lebih dahulu bila dua norma yang benar-benar bertentangan berada pada hierarki berbeda dan hierarkinya dapat dibandingkan.',
            'LEX_SPECIALIS':'Dipakai setelah hierarki tidak menentukan hasil, hanya bila kekhususan ruang lingkup/subjek/objek dapat dibuktikan.',
            'LEX_POSTERIOR':'Dipakai terakhir untuk norma setingkat yang mengatur materi sama dan benar-benar bertentangan, setelah status perubahan/pencabutan dan aturan peralihan diverifikasi.'
        },
        'structured_pairwise_screens':pairwise,
        'detector_mode':'STRICT_NORM_CONFLICT_RESOLVER_V1_3_13_6',
        'coverage_note':'Applicable law hanya ditentukan sebagai candidate result bila antinomi material, kesamaan objek, dan syarat asas yang dipilih cukup teridentifikasi. Hasil tetap memerlukan verifikasi teks resmi, kewenangan/delegasi, status perubahan/pencabutan, tempus, dan aturan peralihan.',
        'professional_verification':'PENDING',
    }
