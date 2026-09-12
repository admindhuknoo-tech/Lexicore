from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

STOPWORDS={
    'yang','dan','atau','dengan','untuk','dari','pada','dalam','oleh','sebagai','adalah','bahwa','ini','itu','telah','akan','agar','atas','kepada','terhadap','menjadi','dapat','harus','apakah','terdapat','perlu','belum','sudah','secara','serta','antara','setiap','suatu','karena','namun','tidak','bukan','juga','lebih','masih','maka','bila','jika','tersebut','perkara','hukum','fakta','bukti','unsur','pihak','dokumen','analisis'
}

CONCEPTS={
    'TEMPUS': {'tempus','tanggal','tahun','waktu','kejadian','berlaku','peralihan','efektif'},
    'CREDIT': {'kredit','perkreditan','bpr','bank','perbankan','plafon','debitur','appraisal','agunan','jaminan','fidusia','outstanding','kolektibilitas','ckpn','pencairan','sop','komite'},
    'CORRUPTION': {'korupsi','koruptif','tipikor','kerugian','negara','penyalahgunaan','kewenangan','melawan','menguntungkan','gratifikasi','kickback','fee'},
    'INTENT': {'sengaja','kesengajaan','niat','tujuan','menguntungkan','keuntungan','afiliasi','gratifikasi','kickback','fee','aliran','dana'},
    'LOSS': {'kerugian','actual','loss','outstanding','pembayaran','agunan','jaminan','recovery','pemulihan','saldo','audit'},
    'CAUSATION': {'kausal','causal','hubungan','sebab','akibat','keputusan','kerugian','kontribusi','intervening','peran'},
    'RESPONSIBILITY': {'tanggung','jawab','direktur','komite','pejabat','kewenangan','peran','pengawas','kepatuhan','spi','debitur','atribusi'},
    'FORUM': {'pengadilan','tipikor','kewenangan','kompetensi','forum','mengadili','eksepsi','penggelapan','fidusia'},
    'IDENTITY': {'identitas','error','persona','salah','orang','terdakwa','nama','nik'},
    'FIDUCIARY': {'fidusia','fiduciary','jaminan','agunan','bpkb','objek','lelang','eksekusi'},
    'GOVERNANCE': {'prosedur','penyimpangan','tata','kelola','sop','plafon','appraisal','komite','persetujuan'},
    'CIVIL_PROCEDURE': {'gugatan','penggugat','tergugat','eksepsi','posita','petitum','obscuur','plurium','kompetensi','forum','surat kuasa'},
    'LAND': {'sertipikat','sertifikat','shm','tanah','surat ukur','buku tanah','warkah','skpt','ptsl','bpn','pendaftaran','mulyoagung'},
    'INHERITANCE': {'waris','pewaris','ahli waris','harta waris','harta peninggalan','wasiat','kajat'},
    'TORT': {'perbuatan melawan hukum','pmh','melawan hukum','ganti rugi'},
    'CONTRACT': {'wanprestasi','cidera janji','ingkar janji','somasi','perjanjian','kontrak','prestasi'},
}

META_RE=re.compile(r'(?i)(?:\bnik\b|\bnia\b|\bemail\b|\b(?:hp|tlp|telp|telepon|phone)\b|\b(?:jl\.?|jalan)\b|rt\.?\s*\d+|rw\.?\s*\d+|lahir\s+di|agama\b|menikah\b|master\s+ilmu\s+hukum|magister|\b(?:kertarejasa|candirenggo|singosari)\b)')
PROCEDURAL_META_RE=re.compile(r'(?i)(?:surat\s+kuasa\s+khusus|terdaftar\s+di\s+kepaniteraan|nomor\s+perkara|reg\s+perkara|dibacakan\s+dalam\s+persidangan|persidangan\s+tanggal|bertindak\s+untuk\s+dan\s+atas\s+nama)')
PETITUM_RE=re.compile(r'(?i)(?:\bpermohonan\b|\bpetitum\b|\bmohon\b.*\bmajelis\b|memerintahkan\s+terdakwa|dapat\s+diterima|diputuskan\s+dengan\s+seadil)')
LEGAL_ARGUMENT_RE=re.compile(r'(?i)(?:\beksepsi\b|error\s+in\s+persona|kewenangan\s+mengadili|missing\s+link|uraian\s+dakwaan\s+yang\s+terputus|\bmestinya\b|\bseharusnya\b|\bmenurut\b|\bkalau\b.+\bmaka\b|\bapabila\b.+\bmaka\b|permasalahan\s+selesai|bukan\s+perbuatan\s+tindak\s+pidana)')
FRAGMENT_RE=re.compile(r'(?i)^(?:rp\.?\s*)?[0-9][0-9\s.,/-]*(?:\([^)]*rupiah\))?[ .,:;-]*$')
LEGAL_REF_RE=re.compile(r'(?i)\b(?:pasal\s+\d+|undang-?undang|\buu\s+(?:no\.?|nomor)|pojk|seojk|perma|sema|kuhp|kuhap)\b')
PLEADING_RE=re.compile(r'(?i)\b(?:eksepsi|permohonan|petitum|kesimpulan|mohon|menyatakan|dakwaan|dalil|menurut|mestinya|seharusnya|berpendapat)\b')
HEADING_RE=re.compile(r'(?i)^(?:dalam\s+)?(?:eksepsi|konvensi|rekonvensi|permohonan|petitum|kesimpulan|kewenangan\s+mengadili|kasus\s+posisi(?:\s+sesuai\s+dakwaan\s+jpu)?|tentang\s+hukumnya|pokok\s+perkara)\s*[:.-]?$')
EVIDENCE_DOC_RE=re.compile(r'(?i)\b(?:surat\s+kuasa\s+khusus|sertifikat\s+fidusia|sertipikat\s+fidusia|bpkb|rekening\s+koran|laporan\s+audit|hasil\s+audit|notulen|berita\s+acara|sk\s+walikota|surat\s+keputusan|perjanjian(?:\s+[a-zA-ZÀ-ÿ]+){0,3}|appraisal|slik|bukti\s+pencairan|kwitansi|akta)\b')
CASE_FACT_RE=re.compile(r'(?i)\b(?:pemberian\s+kredit|kredit\s+macet|digantikan|menjabat|direktur\s+utama|nilai\s+jaminan|melebihi\s+plafon|tersimpan\s+di\s+bank|tidak\s+ditemukan|dialihkan|dijual|pencairan|pembayaran|outstanding|kerugian|sertipikat|sertifikat|surat\s+ukur|skpt|ptsl|bpn|kantor\s+pertanahan|ahli\s+waris|harta\s+waris|pembagian\s+waris|surat\s+keterangan\s+waris|perbuatan\s+melawan\s+hukum|posita|petitum|obscuur\s+libel|plurium\s+litis\s+consortium)\b')


def _clean(v: Any) -> str:
    return re.sub(r'\s+',' ',str(v or '')).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r'[a-zA-ZÀ-ÿ0-9]+', str(text or '').lower()) if len(t)>=3 and t not in STOPWORDS and not t.isdigit()}


def _concept_hits(text: str) -> set[str]:
    toks=_tokens(text)
    low=' '+str(text or '').lower()+' '
    out=set()
    for name,terms in CONCEPTS.items():
        if toks & terms or any((' '+term+' ') in low for term in terms if ' ' in term):
            out.add(name)
    return out


def classify_source_item(item: Dict[str,Any]) -> Dict[str,Any]:
    statement=_clean(item.get('statement') or item.get('evidence'))
    label=str(item.get('label') or 'SOURCE FACT').upper()
    low=statement.lower()
    # Evidence Taxonomy V2: distinguish pleaded facts/roles from evidence,
    # and keep headings/argument/metadata out of merits evidence.
    if not statement or FRAGMENT_RE.fullmatch(statement):
        cls='NON_MATERIAL_FRAGMENT'; quality=0.0
    elif len(statement) <= 110 and HEADING_RE.fullmatch(statement.strip(' .:-')):
        cls='HEADING_OR_SECTION'; quality=0.0
    elif META_RE.search(statement) and not CASE_FACT_RE.search(statement):
        cls='DOCUMENT_METADATA' if any(x in low for x in ('email','telp','tlp','phone','hp.','alamat','jl.','jalan','kertarejasa','candirenggo','singosari')) else 'PARTY_IDENTITY'
        quality=0.02
    elif PROCEDURAL_META_RE.search(statement) and not any(x in low for x in ('keputusan kredit','pemberian kredit','kerugian','agunan','fidusia')):
        cls='PROCEDURAL_METADATA'; quality=0.05
    elif PETITUM_RE.search(statement):
        cls='PETITUM_OR_PRAYER'; quality=0.05
    elif label in {'LEGAL_REFERENCE'} or (LEGAL_REF_RE.search(statement) and not CASE_FACT_RE.search(statement)):
        cls='LEGAL_REFERENCE'; quality=0.10
    elif LEGAL_ARGUMENT_RE.search(statement):
        cls='LEGAL_ARGUMENT'; quality=0.18
    elif re.search(r'(?i)\b(?:dakwaan|jaksa\s+penuntut\s+umum)\b',statement) and re.search(r'(?i)\b(?:direktur\s+utama|jabatan|menjabat|diangkat|sebagai\s+(?:direktur|pejabat|terdakwa))\b',statement):
        cls='ALLEGED_ROLE'; quality=0.32
    elif EVIDENCE_DOC_RE.search(statement):
        if label=='DOCUMENT':
            cls='ACTUAL_EVIDENTIARY_ITEM'; quality=0.80
        else:
            cls='EVIDENCE_ASSERTION'; quality=0.45
    elif label=='DOCUMENT' and len(statement)<80:
        cls='DOCUMENT_STRUCTURE'; quality=0.05
    elif CASE_FACT_RE.search(statement) and (label in {'ALLEGATION','ADMISSION','DENIAL / LIMITATION'} or PLEADING_RE.search(statement)):
        cls='PLEADED_FACT'; quality=0.42
    elif CASE_FACT_RE.search(statement):
        cls='CASE_FACT'; quality=0.60
    elif label in {'ALLEGATION','ADMISSION','DENIAL / LIMITATION'} or PLEADING_RE.search(statement):
        cls='PLEADING_ASSERTION'; quality=0.22
    else:
        cls='SOURCE_FACT'; quality=0.20
    return {'classification':cls,'quality':quality,'statement':statement,'concepts':sorted(_concept_hits(statement))}


def probative_weight_for_issue(issue: str, item: Dict[str,Any], nexus: Dict[str,Any] | None=None) -> Dict[str,Any]:
    """Separate semantic relevance from evidentiary sufficiency/probative value.

    A text can be topically related to an issue yet still be too weak to support
    the legal proposition.  This guard intentionally fails closed.
    """
    meta=classify_source_item(item)
    cls=meta['classification']; low=meta['statement'].lower(); issue_low=str(issue or '').lower()
    concepts_i=_concept_hits(issue); concepts_s=set(meta['concepts'])
    score=0.0; reason='Belum ada bobot pembuktian yang cukup.'

    if cls=='ACTUAL_EVIDENTIARY_ITEM':
        score=0.72; reason='Dokumen/bukti primer teridentifikasi, tetapi autentikasi dan isi tetap harus diuji.'
    elif cls in {'CASE_FACT','PLEADED_FACT'}:
        score=0.38 if cls=='PLEADED_FACT' else 0.50
        reason='Pernyataan faktual relevan, tetapi belum membuktikan unsur tanpa bukti primer.'
    elif cls=='EVIDENCE_ASSERTION':
        score=0.34; reason='Keberadaan bukti hanya diklaim; dokumen primernya belum tersedia.'
    elif cls=='ALLEGED_ROLE':
        score=0.28; reason='Jabatan/peran baru didalilkan; atribusi tindakan individual belum terbukti.'
    else:
        return {'score':0.0,'level':'NONE','sufficient':False,'reason':'Kelas sumber ini tidak layak menjadi dasar pembuktian merits.'}

    # Issue-specific sufficiency gates.
    if 'LOSS' in concepts_i or 'kerugian' in issue_low or 'actual loss' in issue_low:
        strong=any(x in low for x in ('laporan audit','hasil audit','perhitungan kerugian','kerugian nyata','outstanding','saldo pokok','pembayaran kredit','pemulihan','recovery','nilai likuidasi'))
        if not strong:
            score=min(score,0.24)
            reason='Relevan terhadap konteks kredit/agunan, tetapi belum cukup membuktikan kerugian nyata atau besar kerugian.'
    if any(x in issue_low for x in ('kausal','causal','hubungan langsung','intervening','sebab akibat','kontribusi pihak')):
        decision=any(x in low for x in ('keputusan','menyetujui','memutus','pencairan','perintah','tindakan'))
        outcome=any(x in low for x in ('kerugian','outstanding','gagal bayar','dialihkan','dijual','hilang','recovery','pemulihan'))
        intervening=any(x in low for x in ('pihak lain','debitur','dititipi','dialihkan','intervening'))
        if not ((decision and outcome) or intervening):
            score=min(score,0.22)
            reason='Ada keterkaitan topik, tetapi rantai keputusan-akibat/intervening act belum terbukti.'
    if 'INTENT' in concepts_i or 'kesengajaan' in issue_low or 'menguntungkan' in issue_low:
        intent_cue=any(x in low for x in ('aliran dana','keuntungan pribadi','fee','kickback','gratifikasi','afiliasi','menerima','memerintahkan untuk menguntungkan'))
        if not intent_cue:
            score=min(score,0.18)
            reason='Tidak ada bukti sumber yang cukup mengenai niat, benefit, atau keadaan batin.'
    if 'RESPONSIBILITY' in concepts_i:
        responsibility_cue=any(x in low for x in ('direktur','komite','pejabat','kewenangan','menyetujui','memutus','peran','tanggung jawab','pengawas','kepatuhan','spi','debitur'))
        if cls=='ALLEGED_ROLE':
            score=min(score,0.26)
            reason='Jabatan teridentifikasi sebagai dalil, tetapi tindakan, kewenangan konkret, dan atribusi personal belum terbukti.'
        elif not responsibility_cue:
            score=min(score,0.20)
            reason='Fakta ini tidak cukup menunjukkan siapa melakukan apa, dengan kewenangan apa, dan dalam kapasitas apa.'
    if any(x in issue_low for x in ('prosedur','tata kelola','perkreditan','keputusan bisnis/perbankan')):
        if any(x in low for x in ('melebihi plafon','plafon','appraisal','sop','komite','persetujuan kredit','analisa kredit')):
            score=max(score,0.46 if cls!='ACTUAL_EVIDENTIARY_ITEM' else 0.72)
            reason='Cukup relevan untuk menguji tata kelola/proses, tetapi belum membuktikan unsur pidana.'

    level='HIGH' if score>=0.70 else ('MEDIUM' if score>=0.45 else ('LOW' if score>0 else 'NONE'))
    sufficient=score>=0.45
    return {'score':round(score,3),'level':level,'sufficient':sufficient,'reason':reason}

def issue_source_nexus(issue: str, item: Dict[str,Any]) -> Dict[str,Any]:
    meta=classify_source_item(item)
    cls=meta['classification']
    itoks=_tokens(issue); stoks=_tokens(meta['statement'])
    concepts_i=_concept_hits(issue); concepts_s=set(meta['concepts'])

    # Hard exclusions: metadata, generic structure and legal references cannot be used as proof of merits.
    if cls in {'DOCUMENT_METADATA','PARTY_IDENTITY','PROCEDURAL_METADATA','PETITUM_OR_PRAYER','DOCUMENT_STRUCTURE','LEGAL_REFERENCE','NON_MATERIAL_FRAGMENT','LEGAL_ARGUMENT','PLEADING_ASSERTION','HEADING_OR_SECTION','SOURCE_FACT'}:
        return {'eligible':False,'score':0.0,'reason':f'{cls} bukan bukti fakta material untuk isu ini','classification':cls}
    if cls=='PARTY_IDENTITY' and 'IDENTITY' not in concepts_i and 'RESPONSIBILITY' not in concepts_i:
        return {'eligible':False,'score':0.0,'reason':'identitas pihak tidak memiliki nexus langsung dengan isu substantif','classification':cls}

    low=meta['statement'].lower()
    # Issue-specific mandatory gates.  These deliberately prefer "no support"
    # over a plausible-looking but legally false pairing.
    if 'TEMPUS' in concepts_i:
        procedural_or_reference=any(x in low for x in ('surat kuasa','kepaniteraan','persidangan tanggal','nomor perkara','sk walikota','diangkat berdasarkan','diperpanjang dengan','digantikan oleh'))
        event_cue=any(x in low for x in ('perbuatan pada','perbuatan tanggal','terjadi pada','pemberian kredit pada','kredit diberikan pada','pencairan pada','pencairan tanggal','kejadian pada','tempus'))
        if procedural_or_reference or not event_cue:
            return {'eligible':False,'score':0.0,'reason':'tanggal/tahun pada sumber bukan tempus perbuatan yang teridentifikasi','classification':cls}
    if 'INTENT' in concepts_i and 'INTENT' not in concepts_s:
        return {'eligible':False,'score':0.0,'reason':'isu mens rea/keuntungan memerlukan fakta sumber tentang niat, keuntungan, aliran dana, afiliasi, fee atau benefit','classification':cls}
    if any(x in str(issue or '').lower() for x in ('prosedur','tata kelola','perkreditan')):
        procedure_cue=any(x in low for x in ('pemberian kredit','plafon','appraisal','sop','komite','persetujuan kredit','analisa kredit','melebihi 65','pencairan'))
        if not procedure_cue:
            return {'eligible':False,'score':0.0,'reason':'isu tata kelola/perkreditan memerlukan fakta sumber tentang proses atau keputusan kredit','classification':cls}
    if 'CAUSATION' in concepts_i and not (concepts_s & {'CAUSATION','LOSS','CREDIT','FIDUCIARY'}):
        return {'eligible':False,'score':0.0,'reason':'isu kausalitas memerlukan fakta sumber tentang keputusan, akibat, kerugian, kredit atau intervening act','classification':cls}

    overlap=len(itoks & stoks)
    lexical=overlap/max(3,len(itoks))
    concept_overlap=len(concepts_i & concepts_s)
    concept_score=min(0.72, concept_overlap*0.24)
    quality=float(meta['quality'])
    score=min(1.0, lexical*0.55 + concept_score + quality*0.25)

    # For broad legal questions, semantic concept overlap is mandatory unless lexical overlap is unusually strong.
    eligible=(concept_overlap>0 or overlap>=2) and score>=0.24
    reason=(f'nexus semantik {", ".join(sorted(concepts_i & concepts_s))}' if concept_overlap else f'overlap istilah material={overlap}')
    return {'eligible':eligible,'score':round(score,3),'reason':reason,'classification':cls}


def ranked_support_for_issue(issue: str, ledger: Iterable[Dict[str,Any]], limit: int=3) -> List[Dict[str,Any]]:
    ranked=[]
    for idx,item in enumerate(ledger or []):
        if not isinstance(item,dict):
            continue
        nexus=issue_source_nexus(issue,item)
        if not nexus['eligible']:
            continue
        meta=classify_source_item(item)
        probative=probative_weight_for_issue(issue,item,nexus)
        ranked.append({
            'index':idx,
            'statement':meta['statement'],
            'classification':meta['classification'],
            'score':nexus['score'],
            'reason':nexus['reason'],
            'probative_score':probative['score'],
            'probative_level':probative['level'],
            'probative_sufficient':probative['sufficient'],
            'probative_reason':probative['reason'],
            'source_label':item.get('label') or 'SOURCE FACT',
            'segment':item.get('segment'),
        })
    ranked.sort(key=lambda x:(-int(bool(x.get('probative_sufficient'))),-x.get('probative_score',0),-x['score'],x['index']))
    return ranked[:limit]


def evidence_rows(ledger: Iterable[Dict[str,Any]], system: str='CRIMINAL', limit: int=24) -> List[Dict[str,Any]]:
    rows=[]; seen=set()
    from services.semantic_admission import route_allowed
    for idx,item in enumerate(ledger or []):
        if not isinstance(item,dict): continue
        if not route_allowed(item, 'Evidence Map'):
            continue
        meta=classify_source_item(item)
        cls=meta['classification']; fact=meta['statement']
        # Evidence Map is not a transcript of the pleading.  Only a primary
        # evidentiary item, a substantive assertion about evidence, or a
        # material case fact may become a row.  Arguments/metadata remain in
        # the internal trace but are never presented as facts proved.
        if not fact or cls not in {'ACTUAL_EVIDENTIARY_ITEM','EVIDENCE_ASSERTION','CASE_FACT','PLEADED_FACT','ALLEGED_ROLE'}:
            continue
        material_concepts=_concept_hits(fact) & {'CREDIT','CORRUPTION','INTENT','LOSS','CAUSATION','RESPONSIBILITY','FORUM','FIDUCIARY','GOVERNANCE','TEMPUS'}
        if cls!='ACTUAL_EVIDENTIARY_ITEM' and not material_concepts:
            continue
        key=re.sub(r'\W+',' ',fact.lower()).strip()[:180]
        if not key or key in seen: continue
        seen.add(key)
        if cls=='ACTUAL_EVIDENTIARY_ITEM':
            tool='Dokumen/benda bukti yang disebut dalam sumber'; strength='SEDANG — keberadaan disebut dalam sumber, tetapi keaslian, isi lengkap, penguasaan, dan admissibility tetap harus diverifikasi.'
        elif cls=='EVIDENCE_ASSERTION':
            tool='Klaim tentang bukti/dokumen'; strength='RENDAH–SEDANG — sumber menyebut atau mempertanyakan adanya bukti; dokumen primer belum tersedia pada analisis ini.'
        elif cls=='CASE_FACT':
            tool='Fakta perkara dari sumber non-pleading'; strength='SEDANG — pernyataan faktual teridentifikasi; tetap perlu autentikasi dan bukti primer.'
        elif cls=='PLEADED_FACT':
            tool='Fakta yang didalilkan dalam dokumen'; strength='RENDAH–SEDANG — merupakan dalil faktual, bukan fakta terbukti dengan sendirinya.'
        elif cls=='ALLEGED_ROLE':
            tool='Peran/jabatan yang didalilkan'; strength='RENDAH–SEDANG — jabatan/peran disebut dalam dakwaan/pleading; atribusi tindakan individual tetap harus dibuktikan.'
        else:
            tool='Dalil/pleading'; strength='RENDAH — merupakan posisi atau pernyataan dalam dokumen, bukan alat bukti formal dengan sendirinya.'
        rows.append({
            'evidence_tool':tool,'fact_proved':fact[:650],'formal_strength':strength,
            'source_label':item.get('label') or 'SOURCE FACT','source_segment':item.get('segment'),
            'source_classification':cls,'source_index':idx,
            'opponent_evidence_weakness':'Uji nexus, autentikasi, sumber pengetahuan, konsistensi, tempus, serta bukti primer/kontra sebelum menaikkan pernyataan ini menjadi fakta terbukti.'
        })
        if len(rows)>=limit: break
    return rows


def material_source_ledger(ledger: Iterable[Dict[str,Any]], limit: int=80) -> List[Dict[str,Any]]:
    """Return a user-facing trace containing only case-material source items.

    The raw source_ledger remains untouched for auditability.  This projection
    intentionally excludes identity/contact blocks, representation metadata,
    procedural filing metadata, bare legal references, prayers, headings and
    non-material fragments.
    """
    out=[]; seen=set()
    allowed={'ACTUAL_EVIDENTIARY_ITEM','EVIDENCE_ASSERTION','CASE_FACT','PLEADED_FACT','ALLEGED_ROLE'}
    from services.semantic_admission import route_allowed
    for idx,item in enumerate(ledger or []):
        if not isinstance(item,dict):
            continue
        # Material source projection may retain factual/argument leads for audit,
        # but statements explicitly rejected by SAL from both Case Readiness and
        # Evidence Map must not masquerade as case-material evidence.
        sal_state=item.get('sal_admissibility_state')
        sal_type=item.get('sal_semantic_type')
        if sal_state == 'REJECTED' or sal_type in {'QUESTION','FUTURE_ACTION'}:
            continue
        meta=classify_source_item(item); cls=meta['classification']; text=meta['statement']
        if cls not in allowed or not text:
            continue
        concepts=_concept_hits(text)
        if cls!='ACTUAL_EVIDENTIARY_ITEM' and not concepts:
            continue
        key=re.sub(r'\W+',' ',text.lower()).strip()[:180]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({
            'label':item.get('label') or 'SOURCE FACT',
            'display_classification':cls,
            'statement':text,
            'evidence':item.get('evidence') or '',
            'segment':item.get('segment'),
            'source_classification':cls,
            'source_index':idx,
            # Preserve the authoritative SAL classification into the user-facing
            # trace projection. Exporters must not reconstruct semantic meaning
            # from legacy source_classification labels.
            'sal_semantic_type': sal_type or (item.get('sal_contract') or {}).get('semantic_envelope',{}).get('semantic_type'),
            'sal_admissibility_state': sal_state or (item.get('sal_contract') or {}).get('admission_contract',{}).get('admissibility_state'),
            'sal_statement_id': item.get('statement_id') or (item.get('sal_contract') or {}).get('statement_id'),
            'sal_speaker_role': item.get('sal_speaker_role') or 'UNKNOWN',
            'sal_position': item.get('sal_position') or 'NEUTRAL',
            'sal_stance': item.get('sal_stance') or 'UNSPECIFIED',
            'sal_epistemic_status': item.get('sal_epistemic_status') or 'UNSPECIFIED',
        })
        if len(out)>=limit:
            break
    return out

def executive_fact_candidates(ledger: Iterable[Dict[str,Any]], limit: int=5) -> List[str]:
    scored=[]
    for idx,item in enumerate(ledger or []):
        if not isinstance(item,dict): continue
        sal_type=item.get('sal_semantic_type') or (item.get('sal_contract') or {}).get('semantic_envelope',{}).get('semantic_type')
        sal_state=item.get('sal_admissibility_state') or (item.get('sal_contract') or {}).get('admission_contract',{}).get('admissibility_state')
        if sal_type and sal_type not in {'FACT_ASSERTION','PRIMARY_EVIDENCE'}:
            continue
        if sal_state in {'REJECTED','LEAD_ONLY'}:
            continue
        epistemic=str(item.get('sal_epistemic_status') or '').upper()
        if epistemic in {'UNVERIFIED_PROSECUTION_ALLEGATION','UNVERIFIED_DEFENSE_REBUTTAL'}:
            continue
        meta=classify_source_item(item)
        if meta['classification'] not in {'CASE_FACT','ACTUAL_EVIDENTIARY_ITEM','EVIDENCE_ASSERTION','PLEADED_FACT','ALLEGED_ROLE'}:
            continue
        # Prefer case facts, but keep material allegations where the document is itself a pleading.
        score={'CASE_FACT':4,'ACTUAL_EVIDENTIARY_ITEM':4,'EVIDENCE_ASSERTION':3,'PLEADED_FACT':3,'ALLEGED_ROLE':2}[meta['classification']]
        score+=len(_concept_hits(meta['statement']))
        if len(meta['statement'])<45: score-=2
        scored.append((score,idx,meta['statement']))
    scored.sort(key=lambda x:(-x[0],x[1]))
    out=[]; seen=set()
    for _,_,s in scored:
        key=re.sub(r'\W+',' ',s.lower()).strip()[:160]
        if key in seen: continue
        seen.add(key); out.append(s)
        if len(out)>=limit: break
    return out


def regulation_reportable(row: Dict[str,Any]) -> bool:
    """Compatibility-level candidate reportability.

    A legal-instrument candidate may remain *visible as an unverified candidate*
    when it is POTENTIALLY_APPLICABLE and its case nexus is still uncertain,
    provided there is no explicit identity failure.  This preserves discovery
    trace without promoting the candidate to applicable law.

    Lawyer-facing merits sections should use ``regulation_merits_reportable``.
    """
    v=(row or {}).get('positive_law_verification') or {}
    if not (row or {}).get('document_classification',{}).get('legal_instrument_candidate'):
        return False
    if v.get('final_status') in {'REJECTED_NON_LEGAL_CONTENT','VERIFIED_NOT_RELEVANT','UNVERIFIED_IDENTITY_MISMATCH','STATUS_UNCERTAIN'}:
        return False
    if v.get('identity_confirmed') is False:
        return False
    if v.get('case_nexus_status')=='NO_CASE_NEXUS':
        return False
    if v.get('case_nexus_status')=='CASE_NEXUS_VERIFIED':
        return True
    return v.get('final_status')=='POTENTIALLY_APPLICABLE' and v.get('case_nexus_status')=='CASE_NEXUS_UNCERTAIN'


def regulation_merits_reportable(row: Dict[str,Any]) -> bool:
    """Strict lawyer-facing regulatory gate.

    Only an identity-confirmed instrument with verified case nexus may enter the
    main Regulasi & Tempus merits section.  Candidate-only discovery remains in
    diagnostics and never contributes to scoring or legal conclusions.
    """
    v=(row or {}).get('positive_law_verification') or {}
    if not (row or {}).get('document_classification',{}).get('legal_instrument_candidate'):
        return False
    if v.get('identity_confirmed') is not True:
        return False
    if v.get('case_nexus_status')!='CASE_NEXUS_VERIFIED':
        return False
    if v.get('final_status') in {'REJECTED_NON_LEGAL_CONTENT','VERIFIED_NOT_RELEVANT','UNVERIFIED_IDENTITY_MISMATCH','STATUS_UNCERTAIN'}:
        return False
    return True


def _sentence_clip(text: str, limit: int = 900) -> str:
    t=_clean(text)
    if len(t)<=limit: return t
    cut=t[:limit]
    # Prefer ending at a sentence/semicolon boundary rather than leaking a half sentence.
    pos=max(cut.rfind('. '),cut.rfind('; '),cut.rfind(': '))
    if pos>=max(180,int(limit*.55)):
        return cut[:pos+1].strip()
    return cut.rsplit(' ',1)[0].rstrip(' ,;:-')+'…'

def build_consistent_executive_summary(result: Dict[str,Any]) -> List[str]:
    """Build a global-consistency executive summary after the reasoning guard.

    This deliberately runs after tempus/domain guards.  It never infers an event
    year from document numbers, statute citations, case numbers, appointment
    instruments or object model years.
    """
    guard=result.get('reasoning_guard') or {}
    flags=guard.get('flags') or {}
    tempus=guard.get('tempus') or {}
    source=_clean(result.get('source_text'))
    facts=executive_fact_candidates(result.get('source_ledger') or [],5)
    capsule=[]
    if flags.get('corruption_nexus'):
        capsule.append('dokumen memuat konteks/dakwaan tindak pidana korupsi; pemenuhan unsur belum ditetapkan')
    if flags.get('banking_nexus'):
        capsule.append('dokumen memuat konteks perbankan/kredit dan perlu pemetaan proses keputusan, pembayaran, agunan, serta recovery')
    if flags.get('fiduciary_nexus'):
        capsule.append('dokumen memuat isu agunan/fidusia yang relevan terhadap recovery dan kausalitas, bukan penentu otomatis ada/tidaknya tindak pidana')
    if flags.get('criminal_nexus'):
        years=tempus.get('event_year_candidates') or []
        if len(years)==1 and tempus.get('status') not in {'TEMPUS_INSUFFICIENT','TEMPUS_REQUIRES_EVENT_DATE'}:
            capsule.append(f'kandidat tahun perbuatan {years[0]} masih memerlukan verifikasi terhadap dakwaan/bukti primer')
        else:
            capsule.append('tahun/tanggal perbuatan material belum dapat ditetapkan secara aman dari dokumen ini')
    if not capsule and facts:
        capsule.append(facts[0])

    out=[]
    if capsule:
        out.append('Fakta kunci: '+'; '.join(capsule[:4])+'.')
    elif source:
        out.append('Fakta kunci: dokumen sumber telah terbaca, tetapi fakta material belum cukup bersih untuk diringkas tanpa verifikasi terhadap sumber primer.')
    issues=[]
    for x in result.get('legal_issues') or []:
        t=_clean(x)
        if t and t not in issues: issues.append(t)
        if len(issues)>=3: break
    if issues:
        out.append('Isu utama: '+'; '.join(issues))
    analysis=_clean(result.get('legal_analysis'))
    if analysis:
        out.append('Posisi analitis awal: '+_sentence_clip(analysis,900))
    gaps=[]
    for x in (result.get('evidentiary_gaps') or result.get('evidence_needed') or []):
        t=_clean(x)
        if t and t not in gaps: gaps.append(t)
        if len(gaps)>=4: break
    if gaps:
        out.append('Gap pembuktian kritis: '+'; '.join(gaps))
    return out[:4]


def apply_global_case_consistency(result: Dict[str,Any]) -> Dict[str,Any]:
    result=dict(result or {})
    result['executive_summary']=build_consistent_executive_summary(result)
    result['consistency_guard']={
        'policy':'GLOBAL_FAIL_CLOSED_CONSISTENCY',
        'evidence_issue_nexus':'SEMANTIC_REQUIRED',
        'tempus_scope':'GLOBAL',
        'provision_gate':'INSTRUMENT_IDENTITY_THEN_CASE_NEXUS_THEN_ARTICLE',
        'readiness_scoring_rule':'ONLY_VERIFIED_APPLICABLE_PROVISIONS_COUNT',
        'professional_verification':'PENDING',
    }
    return result
