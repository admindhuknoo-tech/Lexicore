"""Offline/online/hybrid legal authority search for LexiCore."""
from __future__ import annotations
from typing import Dict, List
import re

from database import RegulatoryCorpusManager
from legal_sources import federated_search
from services.positive_law_verification import classify_legal_document_candidate, regulation_identity

VALID_MODES={'offline','online','hybrid'}


REGULATORY_HIERARCHY = [
    ("UU", "Undang-Undang (UU)"),
    ("PP", "Peraturan Pemerintah (PP)"),
    ("PERPRES", "Peraturan Presiden (Perpres)"),
    ("PER_MENTERI_LEMBAGA", "Peraturan Menteri / Lembaga"),
    ("PERMA", "Peraturan Mahkamah Agung (PERMA)"),
    ("PERMK", "Peraturan Mahkamah Konstitusi (PERMK)"),
    ("PERKAP", "Peraturan Kepolisian / PERKAP"),
    ("PERDA", "Peraturan Daerah (PERDA)"),
    ("LAINNYA", "Instrumen Lain / Dasar Konstitusional"),
]


def _hierarchy_key(jenis: str = '', title: str = '', nomor: str = '') -> str:
    raw=' '.join(str(x or '') for x in (jenis,title,nomor)).lower()
    j=(jenis or '').upper().strip()
    if j == 'PERMA' or 'peraturan mahkamah agung' in raw or re.search(r'\bperma\b', raw): return 'PERMA'
    if j in {'PERMK','PMK'} or 'peraturan mahkamah konstitusi' in raw or re.search(r'\bpermk\b', raw): return 'PERMK'
    if j in {'PERKAP','PERPOL'} or 'peraturan kepolisian' in raw or 'peraturan kapolri' in raw or re.search(r'\bperkap\b', raw): return 'PERKAP'
    if j.startswith('PERDA') or 'peraturan daerah' in raw or re.search(r'\bperda\b', raw): return 'PERDA'
    if j == 'PERPRES' or 'peraturan presiden' in raw or re.search(r'\bperpres\b', raw): return 'PERPRES'
    if j == 'PP' or 'peraturan pemerintah' in raw or re.search(r'\bpp\s+(?:no|nomor)', raw): return 'PP'
    if j == 'UU' or 'undang-undang' in raw or re.search(r'\buu\s+(?:no|nomor)', raw): return 'UU'
    if re.search(r'\binpres\b', raw) or 'instruksi presiden' in raw:
        return 'LAINNYA'
    if j in {'POJK','SEOJK','PER_LEMBAGA','PER_MENTERI','PERMEN','PBI','PADG'} or any(x in raw for x in ('peraturan menteri','peraturan badan','peraturan lembaga','peraturan ojk','pojk','seojk','peraturan bank indonesia')):
        return 'PER_MENTERI_LEMBAGA'
    return 'LAINNYA'


def _number_year(row: Dict) -> tuple[str, str]:
    raw=str(row.get('nomor') or row.get('title') or '').strip()
    ident=regulation_identity(raw)
    tahun=str(row.get('tahun') or ident.get('year') or '').strip()
    if ident.get('key'):
        labels={'UU':'UU','PP':'PP','PERMA':'PERMA','SEMA':'SEMA','PERPRES':'PERPRES'}
        nomor=f"{labels.get(ident.get('type'),ident.get('type'))} No. {ident.get('number')} Tahun {ident.get('year')}"
    else:
        nomor=raw
    if not tahun:
        m=re.search(r'\b((?:19|20)\d{2})\b', raw)
        tahun=m.group(1) if m else ''
    if not nomor:
        nomor='BELUM TERVERIFIKASI'
    return nomor, tahun or 'BELUM TERVERIFIKASI'


def _query_terms(query: str) -> list[str]:
    return [x for x in re.findall(r'[a-z0-9]{3,}', (query or '').lower()) if x not in {'pasal','ayat','tahun','nomor','tentang','peraturan'}]


def _specific_provisions(reg: Dict, query: str) -> list[Dict]:
    arts=[a for a in (reg.get('articles') or []) if isinstance(a,dict)]
    terms=_query_terms(query)
    scored=[]
    for a in arts:
        hay=' '.join([str(a.get('pasal','')),str(a.get('topic','')),str(a.get('content','')),' '.join(a.get('keywords') or [])]).lower()
        score=sum(2 for t in terms if t in hay)
        if re.search(r'\bpasal\s+\d+', str(a.get('pasal') or ''), re.I): score += 3
        if score: scored.append((score,a))
    scored.sort(key=lambda x:x[0], reverse=True)
    out=[]
    for _,a in scored[:4]:
        label=str(a.get('pasal') or '').strip()
        exact=bool(re.search(r'\bPasal\s+\d+', label, re.I))
        ayat=''
        m=re.search(r'ayat\s*\(([^)]+)\)', label, re.I)
        if m: ayat=f"ayat ({m.group(1)})"
        out.append({
            'pasal': label if exact else 'BELUM TERVERIFIKASI',
            'ayat': ayat,
            'topic': a.get('topic') or '',
            'content': a.get('content') or '',
            'verification_status': 'LOCAL_CORPUS — VERIFY OFFICIAL SOURCE' if exact else 'PASAL_SPESIFIK_BELUM_TERVERIFIKASI',
        })
    return out


def _requested_provisions(query: str) -> list[Dict]:
    out=[]
    for m in re.finditer(r'\bPasal\s+(\d+[A-Za-z]?)(?:\s+ayat\s*\(([^)]+)\))?', query or '', re.I):
        out.append({'pasal':f"Pasal {m.group(1)}",'ayat':f"ayat ({m.group(2)})" if m.group(2) else '', 'topic':'','content':'', 'verification_status':'REQUESTED — VERIFY IN OFFICIAL FULL TEXT'})
    return out


def _practical_implication(query: str, provisions: list[Dict], verification_status: str, is_online: bool=False) -> str:
    issue=(query or 'isu perkara').strip()
    exact=[p for p in provisions if p.get('pasal') and p.get('pasal')!='BELUM TERVERIFIKASI']
    if exact:
        topics=', '.join([p.get('topic') for p in exact if p.get('topic')][:2]) or issue
        return f"Ketentuan ini menjadi parameter untuk menguji {topics} terhadap fakta/bukti perkara. Posisi hukum user menguat hanya jika unsur pada pasal tersebut terpenuhi dan status berlaku/tempus telah diverifikasi pada sumber resmi."
    if is_online:
        return f"Sumber resmi telah ditemukan untuk isu '{issue}', tetapi implikasi terhadap posisi hukum user belum boleh ditarik sebagai kesimpulan final sebelum pasal/ayat spesifik dan status berlakunya diverifikasi."
    return f"Regulasi ini relevan secara topikal terhadap '{issue}', tetapi pasal/ayat spesifik belum cukup terpetakan. Gunakan sebagai arah riset, bukan dasar final, sampai provision dan tempus diverifikasi."


def _enrich_local_row(row: Dict, query: str) -> Dict:
    nomor,tahun=_number_year(row)
    provisions=_specific_provisions(row,query)
    key=_hierarchy_key(row.get('jenis'),row.get('tentang'),nomor)
    return {**row,'hierarchy_key':key,'hierarchy_label':dict(REGULATORY_HIERARCHY).get(key,key),
            'nomor':nomor,'tahun':tahun,'specific_provisions':provisions,
            'practical_implication':_practical_implication(query,provisions,row.get('verification_status',''))}


def _enrich_online_row(row: Dict, query: str) -> Dict:
    nomor,tahun=_number_year(row)
    provisions=_requested_provisions(query)
    key=_hierarchy_key('',row.get('title'),nomor)
    return {**row,'hierarchy_key':key,'hierarchy_label':dict(REGULATORY_HIERARCHY).get(key,key),
            'nomor':nomor,'tahun':tahun,'specific_provisions':provisions,
            'practical_implication':_practical_implication(query,provisions,row.get('verification_status',''),True)}


def _hierarchical_groups(rows: List[Dict]) -> List[Dict]:
    groups=[]
    for order,(key,label) in enumerate(REGULATORY_HIERARCHY,1):
        items=[r for r in rows if r.get('hierarchy_key')==key]
        if items:
            groups.append({'key':key,'label':label,'order':order,'items':items})
    return groups


def _local_rows(query:str, limit:int)->List[Dict]:
    rows=[]
    semantic_terms=[t for t in _query_terms(query) if not t.isdigit()]
    for reg in RegulatoryCorpusManager.search(query,limit=max(limit*3,limit)):
        hay=' '.join([str(reg.get('nomor','')),str(reg.get('tentang','')),' '.join(reg.get('domain_tags') or []),
                      ' '.join(' '.join([str(a.get('pasal','')),str(a.get('topic','')),str(a.get('content','')),' '.join(a.get('keywords') or [])]) for a in (reg.get('articles') or []) if isinstance(a,dict))]).lower()
        if semantic_terms:
            matched=sum(1 for t in semantic_terms if t in hay)
            required=len(semantic_terms) if len(semantic_terms)<=2 else 2
            if matched < required:
                continue
        rows.append({
            'source':'LOCAL_DATABASE','authoritative':False,'regulation_id':reg.get('id'),
            'title':f"{reg.get('nomor','')} — {reg.get('tentang','')}",
            'nomor':reg.get('nomor'),'tahun':reg.get('tahun'),'tentang':reg.get('tentang'),
            'jenis':reg.get('jenis'),'hierarchy_rank':reg.get('hierarchy_rank'),
            'status':reg.get('status'),'effective_date':reg.get('effective_date'),
            'official_url':reg.get('official_url'),'domain_tags':reg.get('domain_tags',[]),
            'articles':reg.get('articles',[]),'verification_status':'LOCAL_DATABASE — VERIFY OFFICIAL SOURCE',
        })
        if len(rows)>=limit: break
    return rows


def _online_rows(query:str, limit:int, direct_ids=None)->tuple[List[Dict], int]:
    """Return only legal-instrument candidates from official search.

    The Corpus UI shares the same deterministic gate as Case Analysis so an
    official news/event page is not rendered as Regulatory Intelligence.
    """
    rows=[]; rejected=0
    query_identity=regulation_identity(query)
    for bundle in federated_search(query,direct_ids=tuple(direct_ids or ()),per_source_limit=max(2,min(limit,6))):
        for item in bundle.get('results',[]):
            row={
                'source':'OFFICIAL_ONLINE','source_id':bundle.get('source_id'),'source_name':bundle.get('source_name'),
                'authoritative':bool(bundle.get('authoritative')),'title':item.get('title'),
                'url':item.get('url'),'score':item.get('score',0),'query':query,
                'verification_status':'OFFICIAL SOURCE LOCATED — CONTENT/APPLICABILITY VERIFY',
            }
            gate=classify_legal_document_candidate(row)
            row['document_classification']=gate
            if not gate.get('legal_instrument_candidate'):
                rejected += 1
                continue
            # For an exact instrument query, reject a result whose explicit title
            # identity points to a different regulation.  This prevents legal but
            # irrelevant search hits from masquerading as the requested norm.
            title_identity=regulation_identity(row.get('title'))
            if query_identity.get('key') and title_identity.get('key') and title_identity.get('key') != query_identity.get('key'):
                rejected += 1
                continue
            rows.append(row)
    rows.sort(key=lambda x:(bool(x.get('authoritative')),x.get('score',0)),reverse=True)
    seen=set(); out=[]
    for row in rows:
        key=(row.get('url') or row.get('title') or '').strip().lower()
        if not key or key in seen: continue
        seen.add(key); out.append(row)
        if len(out)>=limit: break
    return out, rejected


def search_legal_authorities(query:str, mode:str='hybrid', limit:int=12, direct_ids=None)->Dict:
    mode=(mode or 'hybrid').lower().strip()
    if mode not in VALID_MODES: mode='hybrid'
    local=_local_rows(query,limit) if mode in ('offline','hybrid') else []
    online=[]; rejected_non_legal=0; error=None
    if mode in ('online','hybrid'):
        try: online,rejected_non_legal=_online_rows(query,limit,direct_ids=direct_ids)
        except Exception as exc: error=str(exc)[:300]
    local=[_enrich_local_row(r,query) for r in local]
    online=[_enrich_online_row(r,query) for r in online]
    combined=local+online
    return {
        'mode':mode,'query':query,'local_results':local,'online_results':online,
        'hierarchical_results':_hierarchical_groups(combined),
        'hierarchy_order':[{'key':k,'label':v,'order':i+1} for i,(k,v) in enumerate(REGULATORY_HIERARCHY)],
        'counts':{'local':len(local),'online':len(online),'rejected_non_legal_content':rejected_non_legal,'total':len(combined)},
        'error':error,'professional_verification':'PENDING',
        'note':'Pemetaan disajikan menurut hierarchy workspace LexiCore. Local database adalah retrieval aid; pasal/ayat dan implikasi final wajib diverifikasi pada sumber resmi serta diuji terhadap fakta/tempus perkara.'
    }
