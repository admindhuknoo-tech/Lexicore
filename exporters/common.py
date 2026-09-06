import re

from services.case_consistency_guard import regulation_merits_reportable
"""Shared professional Case Analysis export model/formatting helpers."""

def _export_scalar(value):
    """Human-readable scalar for case export; never exposes Python repr noise."""
    if value is None:
        return '-'
    if isinstance(value, bool):
        return 'Ya' if value else 'Tidak'
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip() or '-'


_EXPORT_LABELS_ID = {
    "already established": "Sudah Teridentifikasi",
    "must be verified": "Wajib Diverifikasi",
    "not yet established": "Belum Terbukti / Belum Terverifikasi",
    "classification": "Klasifikasi", "general norm": "Norma Umum", "special norm": "Norma Khusus",
    "newer norm": "Norma Lebih Baru", "older norm": "Norma Lebih Lama", "legal reasoning": "Analisis Hukum",
    "recommendation for counsel": "Rekomendasi Counsel", "verification status": "Status Verifikasi",
    "current status": "Status Saat Ini", "why it matters": "Relevansi", "coverage note": "Catatan Cakupan"
}

def _export_label_id(key):
    raw=str(key or '').replace('_',' ').strip()
    return _EXPORT_LABELS_ID.get(raw.lower(), raw.title())

def _translate_status_id(value):
    m={
        'LOCAL CORPUS ARTICLE - OFFICIAL SOURCE VERIFICATION REQUIRED':'KORPUS LOKAL — WAJIB VERIFIKASI KE SUMBER RESMI',
        'LOCAL CORPUS RECORD - OFFICIAL SOURCE VERIFICATION REQUIRED':'KORPUS LOKAL — WAJIB VERIFIKASI KE SUMBER RESMI',
        'LOCAL_METADATA - OFFICIAL SOURCE VERIFICATION REQUIRED':'METADATA LOKAL — WAJIB VERIFIKASI KE SUMBER RESMI',
        'LOCAL_METADATA - OFFICIAL COURT SOURCE VERIFICATION REQUIRED':'METADATA LOKAL — WAJIB VERIFIKASI KE SUMBER PUTUSAN RESMI',
        'PROFESSIONAL VERIFICATION: PENDING':'VERIFIKASI PROFESIONAL: PENDING',
        'POTENTIAL_CONFLICT':'POTENSI KONFLIK','CONFIRMED_CONFLICT':'KONFLIK TERKONFIRMASI',
        'RELATIONSHIP_ONLY':'HANYA RELASI NORMA','PROMULGATED':'DIUNDANGKAN','EFFECTIVE':'MULAI BERLAKU'
    }
    return m.get(str(value), str(value))


_REVIEW_TYPE_ID={
    'TEMPUS_GAP':'Celah tempus / waktu perbuatan',
    'NUMBER_DATE_INCONSISTENCY':'Ketidaksesuaian nomor dan tanggal',
    'ENTITY_NAME_VARIANT':'Variasi identitas pihak',
    'FORUM_VS_MERITS':'Kompetensi/forum vs pokok perkara',
    'ERROR_IN_PERSONA_VS_ATTRIBUTION':'Error in persona vs atribusi perbuatan',
    'FIDUCIARY_NON_DISPOSITIVE':'Fidusia/agunan tidak menentukan hasil secara otomatis',
    'LEGAL_CITATION_ANOMALY':'Anomali rujukan hukum',
    'POTENTIAL_TEXT_TYPO':'Potensi salah ketik/OCR',
    'SOURCE_NOISE_HIGH':'Kandungan sumber nonmaterial tinggi',
    'EVIDENTIARY_GAP':'Celah pembuktian',
    'NO_VERIFIED_APPLICABLE_LAW':'Belum ada hukum berlaku yang terverifikasi',
    'DOCUMENT_STRUCTURE':'Struktur dokumen',
}
_EVIDENCE_CLASS_ID={
    'ACTUAL_EVIDENTIARY_ITEM':'Dokumen/bukti primer yang teridentifikasi',
    'EVIDENCE_ASSERTION':'Klaim mengenai keberadaan bukti/dokumen',
    'CASE_FACT':'Fakta perkara dari sumber non-pleading',
    'PLEADED_FACT':'Fakta yang didalilkan dalam dokumen',
    'ALLEGED_ROLE':'Peran/jabatan yang didalilkan',
    'LEGAL_ARGUMENT':'Argumentasi hukum',
    'HEADING_OR_SECTION':'Judul/bagian dokumen',
    'PLEADING_ASSERTION':'Dalil/pleading',
    'SOURCE_FACT':'Pernyataan sumber',
}

def _human_review_type(v):
    return _REVIEW_TYPE_ID.get(str(v or '').upper(), str(v or 'Temuan').replace('_',' ').title())

def _human_evidence_class(v):
    return _EVIDENCE_CLASS_ID.get(str(v or '').upper(), str(v or '-').replace('_',' ').title())

def _regulatory_export_lines(ri):
    if not isinstance(ri,dict): return []
    lines=[]
    articles=ri.get('articles') or []
    if articles:
        lines.append('Pasal Relevan:')
        for a in articles:
            if not isinstance(a,dict): continue
            citation=a.get('qualified_citation') or a.get('citation') or ((a.get('regulation') or '')+' - '+(a.get('article') or '')).strip(' -')
            if citation: lines.append('- '+str(citation))
            if a.get('text'): lines.append('  Uraian norma: '+str(a.get('text')))
            if a.get('topic'): lines.append('  Topik: '+str(a.get('topic')))
            if a.get('verification_status'): lines.append('  Status verifikasi: '+_translate_status_id(a.get('verification_status')))
    regulations=ri.get('regulations') or []
    if regulations:
        lines.append('Regulasi:')
        for r in regulations:
            if not isinstance(r,dict): continue
            title=r.get('title') or r.get('tentang') or r.get('number') or r.get('qualified_citation') or '-'
            number=r.get('number') or r.get('nomor')
            head=str(title)
            if number and str(number) not in head: head=f'{number} — {head}'
            lines.append('- '+head)
            details=[]
            if r.get('status'): details.append('Status: '+str(r.get('status')))
            if r.get('effective_date'): details.append('Berlaku: '+str(r.get('effective_date')))
            if r.get('authority_source'): details.append('Sumber otoritatif: '+str(r.get('authority_source')))
            if r.get('hierarchy_rank') not in (None,''): details.append('Tingkat hierarki: '+str(r.get('hierarchy_rank')))
            if details: lines.append('  '+' | '.join(details))
            if r.get('official_url'): lines.append('  Sumber resmi: '+str(r.get('official_url')))
            if r.get('verification_status'): lines.append('  Status verifikasi: '+_translate_status_id(r.get('verification_status')))
    relationships=ri.get('relationships') or []
    if relationships:
        lines.append('Relasi Hukum:')
        for rel in relationships:
            if not isinstance(rel,dict): continue
            src=rel.get('source_citation') or rel.get('source') or '-'
            typ=_translate_status_id(rel.get('relation_type') or rel.get('type') or 'TERKAIT_DENGAN')
            tgt=rel.get('target_citation') or rel.get('target') or '-'
            lines.append(f'- {src} → {typ} → {tgt}')
            if rel.get('basis'): lines.append('  Dasar relasi: '+str(rel.get('basis')))
            if rel.get('verification_status'): lines.append('  Status verifikasi: '+_translate_status_id(rel.get('verification_status')))
    timeline=ri.get('timeline') or []
    if timeline:
        lines.append('Linimasa Hukum:')
        for ev in timeline:
            if not isinstance(ev,dict): continue
            date=ev.get('date') or '-'; event=_translate_status_id(ev.get('event') or '-')
            citation=ev.get('qualified_citation') or ev.get('regulation') or ev.get('number') or '-'
            status=ev.get('status')
            line=f'- {date} — {event} — {citation}'
            if status: line += f' [{status}]'
            lines.append(line)
    return lines

def _norm_conflict_export_lines(nc):
    if not isinstance(nc,dict): return _export_item_lines(nc)
    lines=[]
    for i,c in enumerate(nc.get('conflicts_detected') or [],1):
        if not isinstance(c,dict): lines.append('- '+_export_scalar(c)); continue
        principle=c.get('rule_principle') or c.get('type') or 'Analisis Konflik Norma'
        lines.append(f'Potensi Konflik {i} — {principle}:')
        for key in ('classification','general_norm','special_norm','newer_norm','older_norm','legal_reasoning','recommendation_for_counsel','verification_status'):
            if c.get(key) not in (None,'',[],{}):
                val=_translate_status_id(c.get(key)) if key in ('classification','verification_status') else _export_scalar(c.get(key))
                lines.append(f'  {_export_label_id(key)}: {val}')
    if nc.get('coverage_note'):
        lines.append('Catatan Cakupan:')
        lines.append('  '+str(nc.get('coverage_note')))
    return lines

def _export_item_lines(value, prefix=''):
    """Flatten structured analysis into readable lines while preserving labels."""
    lines=[]
    if value is None:
        return lines
    if isinstance(value, str):
        if value.strip(): lines.append(prefix + value.strip())
        return lines
    if isinstance(value, (int, float, bool)):
        lines.append(prefix + _export_scalar(value)); return lines
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                # Prefer common legal-analysis keys before generic flattening.
                lead=(item.get('statement') or item.get('element') or item.get('issue') or item.get('title') or
                      item.get('action') or item.get('recommendation') or item.get('qualified_citation') or item.get('citation'))
                label=item.get('label') or item.get('status') or item.get('priority') or item.get('type')
                if lead:
                    head=(f'[{label}] ' if label else '') + _export_scalar(lead)
                    details=[]
                    for k,v in item.items():
                        if k in ('statement','element','issue','title','action','recommendation','qualified_citation','citation','label','status','priority','type') or v in (None,'',[],{}):
                            continue
                        if isinstance(v,(str,int,float,bool)):
                            details.append(f'{k.replace("_"," ").title()}: {_export_scalar(v)}')
                    lines.append(prefix + head + ((' | ' + ' | '.join(details)) if details else ''))
                else:
                    parts=[]
                    for k,v in item.items():
                        if v in (None,'',[],{}): continue
                        if isinstance(v,(str,int,float,bool)):
                            parts.append(f'{k.replace("_"," ").title()}: {_export_scalar(v)}')
                    if parts: lines.append(prefix + ' | '.join(parts))
            else:
                lines.extend(_export_item_lines(item,prefix))
        return lines
    if isinstance(value, dict):
        for k,v in value.items():
            if v in (None,'',[],{}): continue
            key=k.replace('_',' ').title()
            if isinstance(v,(str,int,float,bool)):
                lines.append(prefix + f'{key}: {_export_scalar(v)}')
            else:
                nested=_export_item_lines(v, prefix='')
                if nested:
                    lines.append(prefix + key + ':')
                    lines.extend(prefix + '  ' + n for n in nested)
        return lines
    return [prefix + str(value)]


def _regulation_allowed_for_case_domains(row, snapshot):
    domains={str(d.get('id')) for d in (snapshot.get('domains') or []) if isinstance(d,dict)}
    if not domains:
        return True
    reg=(row or {}).get('regulation') or {}
    hay=' '.join(str(reg.get(k) or '') for k in ('nomor','tentang','qualified_citation')).lower()
    hay += ' ' + ' '.join(str(a.get('pasal') or a.get('topic') or '') for a in ((row or {}).get('matched_articles') or []) if isinstance(a,dict)).lower()
    vocab={
        'financial_services':('bank','bpr','pojk','seojk','kredit','ojk'),
        'corruption':('tipikor','korupsi','pasal 603','penyalahgunaan kewenangan'),
        'criminal':('kuhp','kuhap','pidana','praperadilan','tersangka'),
        'civil_contract':('kuhperdata','burgerlijk','hukum perdata','perikatan','wanprestasi'),
        'corporate':('perseroan','uu no. 40 tahun 2007','direksi','komisaris'),
        'land_property':('uupa','agraria','pertanahan','sertipikat','sertifikat','bpn'),
        'religious_court':('peradilan agama','pengadilan agama','pasal 49'),
        'civil_procedure':('hir','rbg','rv','acara perdata','obscuur','plurium'),
        'regional_government':('bumd','perumda','pemerintah daerah'),
        'constitutional':('uud 1945','konstitusi'),
        'employment':('ketenagakerjaan','phk','pkwt','pesangon'),
    }
    allowed=tuple(v for d in domains for v in vocab.get(d,()))
    return not allowed or any(v in hay for v in allowed)



def _tempus_anchor_for_regulation(reg, snapshot):
    """Choose the legally relevant time anchor by regulation function.

    Substantive/sectoral norms are screened against the material event date;
    procedural norms are screened against the documented procedural/filing date.
    This avoids excluding a criminal-procedure statute merely because the
    underlying transaction happened years earlier.
    """
    reg=reg or {}; snapshot=snapshot or {}
    hay=(' '.join([str(reg.get('nomor') or ''),str(reg.get('tentang') or ''),' '.join(reg.get('domain_tags') or [])])).lower()
    procedural=any(k in hay for k in ('kuhap','acara pidana','hukum acara','peradilan umum','peradilan agama','ptun','kekuasaan kehakiman'))
    if procedural and snapshot.get('procedural_date_candidate'):
        return str(snapshot.get('procedural_date_candidate')), 'PROCEDURAL_DATE'
    if snapshot.get('event_date_candidate'):
        return str(snapshot.get('event_date_candidate')), 'MATERIAL_EVENT_DATE'
    if snapshot.get('event_year_candidate'):
        return str(snapshot.get('event_year_candidate')), 'YEAR_SCREENING_CANDIDATE'
    return None,'UNKNOWN'


def _tempus_status(reg, snapshot):
    anchor,anchor_type=_tempus_anchor_for_regulation(reg,snapshot)
    eff=str((reg or {}).get('effective_date') or (reg or {}).get('berlaku') or '')
    if not anchor or not eff: return 'UNVERIFIED',anchor_type
    criminal_substantive=any(k in (' '.join([str((reg or {}).get('nomor') or ''),str((reg or {}).get('tentang') or ''),' '.join((reg or {}).get('domain_tags') or [])])).lower() for k in ('kuhp','pidana materiil','pemberantasan tindak pidana korupsi','tipikor'))
    if len(anchor)>=10:
        if eff > anchor:
            return ('POST_TEMPUS_REQUIRES_TRANSITIONAL_ANALYSIS' if criminal_substantive else 'POST_TEMPUS_EXCLUDED'),anchor_type
        return 'POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE',anchor_type
    if anchor[:4].isdigit() and eff[:4].isdigit():
        ey,ay=int(eff[:4]),int(anchor[:4])
        if ey>ay: return ('POST_TEMPUS_REQUIRES_TRANSITIONAL_ANALYSIS' if criminal_substantive else 'POST_TEMPUS_EXCLUDED'),anchor_type
        if ey==ay: return 'TEMPUS_REQUIRES_EXACT_DATE',anchor_type
        return 'POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE',anchor_type
    return 'UNVERIFIED',anchor_type



def _human_release_status(value):
    mapping={
        'PENDING':'Menunggu verifikasi profesional',
        'HOLD_FOR_VERIFICATION':'Tahan kesimpulan — verifikasi diperlukan',
        'REVISE_BEFORE_RELIANCE':'Perlu revisi sebelum dijadikan dasar tindakan',
        'PROVISIONAL_REVIEW_COMPLETE':'Review sementara selesai',
        'TEMPUS_REQUIRES_EXACT_DATE':'Tanggal perbuatan harus dipastikan',
        'POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE':'Berpotensi relevan — verifikasi sumber resmi',
        'POST_TEMPUS_REQUIRES_TRANSITIONAL_ANALYSIS':'Terbit setelah peristiwa — perlu analisis ketentuan peralihan',
        'POST_TEMPUS_EXCLUDED':'Terbit setelah peristiwa — tidak dipakai sebagai dasar materiil',
        'UNVERIFIED':'Belum diverifikasi',
        'PROCEDURAL_DATE':'Tanggal proses/prosedural',
        'MATERIAL_EVENT_DATE':'Tanggal peristiwa material',
        'YEAR_SCREENING_CANDIDATE':'Tahun indikatif — bukan tempus final',
        'UNKNOWN':'Belum ditentukan',
        'CASE_NEXUS_VERIFIED':'Relevansi terhadap perkara terverifikasi',
        'CASE_NEXUS_UNCERTAIN':'Relevansi terhadap perkara belum pasti',
        'NO_CASE_NEXUS':'Tidak relevan terhadap perkara',
        'VERIFIED_APPLICABLE':'Terverifikasi relevan dan berlaku',
        'VERIFIED_NOT_RELEVANT':'Terverifikasi tidak relevan',
        'IN_FORCE':'Berlaku',
        'AMENDED_IN_FORCE':'Berlaku dengan perubahan',
        'REVOKED':'Dicabut/tidak berlaku',
        'STATUS_UNCERTAIN':'Status hukum belum pasti',
        'TEMPUS_VERIFIED':'Waktu berlaku terverifikasi',
        'TEMPUS_UNVERIFIED':'Waktu berlaku belum terverifikasi',
        'PROVISION_VERIFIED':'Pasal terverifikasi pada teks resmi',
        'PROVISION_PARTIALLY_VERIFIED':'Sebagian pasal terverifikasi',
        'PROVISION_UNVERIFIED':'Pasal belum terverifikasi',
        'REQUIRES_VERIFICATION':'Perlu verifikasi',
        'PROVISIONALLY_SUPPORTED':'Dukungan sementara — tetap perlu verifikasi',
        'EVIDENCE_NEXUS_FOUND_LAW_UNVERIFIED':'Bukti terkait ditemukan — dasar hukum belum terverifikasi',
        'SEMANTIC_NEXUS_ONLY':'Keterkaitan topik ditemukan — daya bukti belum cukup',
        'PARTIAL_OFFICIAL_SOURCE_ACCESS':'Akses ke sumber resmi tersedia sebagian',
        'FULL_OFFICIAL_SOURCE_ACCESS':'Akses ke sumber resmi tersedia',
        'COMPLETE':'Pembacaan selesai',
        'DOCX_TEXT':'Teks dokumen DOCX',
        'PDF_TEXT':'Teks dokumen PDF',
        'HIGH':'Tinggi','MEDIUM':'Sedang','LOW':'Rendah','NONE':'Belum memadai',
        'REBUILD_OBJECTION_AROUND_FORMAL_DEFECTS':'Bangun ulang eksepsi berfokus pada cacat formil/prosedural',
        'ISSUE_EVIDENCE_LAW_RECOMMENDATION':'Isu → bukti → hukum → rekomendasi',
        'EKSEPSI_OR_OBJECTION':'Eksepsi / nota keberatan',
        'CIVIL_PLEADING':'Dokumen gugatan/perdata',
        'CRIMINAL_PLEADING':'Dokumen perkara pidana',
        'CONTRACT':'Kontrak/perjanjian',
        'LEGAL_DOCUMENT':'Dokumen hukum',
    }
    return mapping.get(str(value),str(value or '-'))


def _privacy_compact_source_context(x, max_chars=1050):
    """Return lawyer-facing context without contact/identity boilerplate.

    The raw source remains in the internal source ledger.  This projection is
    intentionally conservative: it removes obvious personal identifiers and
    prefers material/procedural context over letterhead/representation metadata.
    """
    source=re.sub(r'\s+',' ',str((x or {}).get('source_text') or '')).strip()
    if not source:
        return ''
    # Remove email, phone, NIK/KTP-like identifiers, and common advocate/contact boilerplate.
    source=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[email disembunyikan]',source)
    source=re.sub(r'(?i)\b(?:hp|telp|tlp|telepon)\.?\s*[:.]?\s*[+()\d][\d\s().-]{6,}\b','[kontak disembunyikan]',source)
    source=re.sub(r'(?i)\b(?:NIK|KTP\s*No\.?|No\.?\s*KTP)\s*[:.]?\s*\d{8,18}\b','[identitas disembunyikan]',source)
    source=re.sub(r'\b\d{16}\b','[identitas disembunyikan]',source)
    # Prefer substantive entry points if present.
    lows=source.lower()
    starts=[]
    for phrase in ('kasus posisi','dakwaan jaksa','terdakwa diajukan','dalam dakwaan','eksepsi kewenangan'):
        i=lows.find(phrase)
        if i>=0: starts.append(i)
    if starts:
        source=source[min(starts):]
    # Remove obvious representation-address clauses when they survive extraction.
    source=re.sub(r'(?i)para advokat[^.]{0,420}beralamat[^.]{0,420}\.?','',source)
    source=re.sub(r'(?i)kesemuanya beralamat kantor[^.]{0,420}\.?','',source)
    source=re.sub(r'\s+',' ',source).strip()
    return source[:max_chars].rstrip(' ,;:-')


def _executive_legal_review_lines(x):
    """Build lawyer-facing top-level review from Professional Review findings."""
    review=(x or {}).get('professional_review') or {}
    findings=review.get('findings') or []
    sr=review.get('strategic_recommendation') or {}
    lines=[]
    if review:
        lines.append('Status: '+_human_release_status(review.get('review_status') or '-'))
        lines.append('Dokumen: '+_human_release_status((review.get('document_structure') or {}).get('document_type') or '-'))
    if findings:
        lines.append('Matriks temuan utama: [Aspek] | [Posisi/teks dokumen] | [Temuan] | [Rekomendasi]')
        for f in findings[:8]:
            aspect=_human_review_type(f.get('type') or 'Temuan')
            src=re.sub(r'\s+',' ',str(f.get('source_text') or '')).strip()[:240] or '-'
            finding=re.sub(r'\s+',' ',str(f.get('finding') or '')).strip()
            rec=re.sub(r'\s+',' ',str(f.get('recommendation') or '')).strip()
            sev=_human_release_status(f.get('severity') or '-')
            lines.append(f"{aspect} [{sev}] | {src} | {finding} | {rec}")
    priorities=(sr.get('priorities') or [])[:5]
    if priorities:
        lines.append('Arah strategi yang direkomendasikan:')
        lines += ['- '+str(v) for v in priorities]
    return lines

def _case_export_sections(x):
    """Single canonical export model for PDF and DOCX case-analysis results."""
    dr=x.get('document_reading') or {}
    provenance=x.get('analysis_provenance') or {}
    method=provenance.get('mode') or x.get('analytical_method') or 'CASE_ANALYSIS'
    provider=provenance.get('provider') or dr.get('provider') or '-'
    model=provenance.get('model') or dr.get('model') or '-'
    meta=[
        ('Judul', x.get('title') or 'Case Analysis'),
        ('Metode analisis', 'Analisis lokal deterministik' if str(method).upper() in {'LOCAL_DETERMINISTIC','DETERMINISTIC_FALLBACK'} else _human_release_status(method)),
        ('Input', 'Dokumen' if str(x.get('input_type') or '').lower()=='document' else (x.get('input_type') or '-')),
        ('Dokumen', x.get('filename') or '-'),
        ('Pembacaan', f"{_human_release_status(dr.get('status','UNKNOWN'))} - {dr.get('segments_read',0)}/{dr.get('segments_total',0)} bagian analitis - {dr.get('characters',0)} karakter"),
    ]
    ingestion=x.get('document_ingestion') or {}
    if ingestion.get('mode'):
        meta.append(('Pembacaan dokumen', f"{_human_release_status(ingestion.get('mode'))} - teks asli {ingestion.get('pages_native',0)} hlm - OCR {ingestion.get('pages_ocr',0)} hlm - gagal {ingestion.get('pages_failed',0)} hlm"))
        if ingestion.get('pages_ocr'):
            portability='PORTABLE' if ingestion.get('portable') else 'LOCAL FALLBACK'
            meta.append(('OCR', f"{ingestion.get('engine','embedded_rapidocr')} / {ingestion.get('language','-')} - {ingestion.get('characters_ocr',0)} karakter OCR - {portability}"))
            if ingestion.get('average_confidence') is not None:
                meta.append(('OCR Confidence', f"{float(ingestion.get('average_confidence'))*100:.1f}% rata-rata"))
        warnings=[str(x) for x in (ingestion.get('warnings') or []) if str(x).strip()]
        if warnings:
            meta.append(('OCR Diagnostics', ' | '.join(warnings[:2])[:420]))
    if dr.get('failure_stage'):
        reasons=[]
        for item in dr.get('segment_trace') or []:
            if isinstance(item,dict) and item.get('reason'):
                reasons.append(str(item.get('reason')))
        reasons=list(dict.fromkeys(reasons))[:4]
        trace=f"{dr.get('failure_stage')}"
        if reasons: trace += ' | ' + ', '.join(reasons)
        meta.append(('AI Pipeline', trace))
        failures=dr.get('failures') or []
        if failures:
            detail=str(failures[0]).replace('\n',' ').strip()[:280]
            if detail:
                meta.append(('AI Failure Detail', detail))
    meta.append(('Verifikasi profesional', _human_release_status(x.get('professional_verification') or 'PENDING')))
    sections=[]

    # Lawyer-facing first page: strategic review first, then a compact source context.
    executive_review=_executive_legal_review_lines(x)
    if executive_review:
        sections.append(('Executive Legal Review', executive_review))

    source_context=_privacy_compact_source_context(x)
    context_lines=[]
    if x.get('title'):
        context_lines.append('Perkara: '+str(x.get('title')))
    if x.get('filename'):
        context_lines.append('Dokumen: '+str(x.get('filename')))
    if source_context:
        context_lines.append('Konteks sumber material (belum merupakan fakta terbukti): '+source_context)
    if context_lines:
        sections.append(('Konteks Perkara / Sumber', context_lines))
    if executive_review:
        sections.append(('Working Paper Terperinci', ['Bagian berikut memuat pemetaan bukti, konstruksi hukum, audit dokumen, tindakan, dan verifikasi sumber untuk penelusuran profesional.']))

    wp=x.get('case_working_paper') or {}
    if wp:
        pct=wp.get('working_paper_percentage') or {}
        pct_lines=[f"Case Readiness / Analysis Completeness: {pct.get('percentage',0)}%", f"Confidence data/analisis: {pct.get('confidence','LOW')}"]
        if pct.get('variables_increasing'):
            pct_lines.append('Variabel penambah nilai:')
            for v in pct.get('variables_increasing')[:8]:
                pct_lines.append(f"- {v.get('impact',0):+} poin | {v.get('variable','-')} | {v.get('basis','-')}")
        if pct.get('variables_decreasing'):
            pct_lines.append('Variabel pengurang nilai:')
            for v in pct.get('variables_decreasing')[:8]:
                pct_lines.append(f"- {v.get('impact',0):+} poin | {v.get('variable','-')} | {v.get('basis','-')}")
        pct_lines.append(pct.get('disclaimer') or 'Estimasi analitis kertas kerja; bukan prediksi putusan.')
        sections.append(('Case Readiness / Analysis Completeness', pct_lines))

        em=wp.get('evidence_map') or {}; basis=em.get('legal_basis') or {}
        ev_lines=[f"Dasar pemetaan: {basis.get('citation','-')}", basis.get('note') or '']
        ev_lines.append('TABEL: [Sumber/Bukti Potensial] | [Proposisi Faktual yang Perlu Diuji] | [Status Pembuktian] | [Uji Lanjut]')
        for r in (em.get('rows') or [])[:28]:
            ev_lines.append(f"[{r.get('evidence_tool','-')}] | {r.get('fact_proved','-')} | {r.get('formal_strength','-')} | {r.get('opponent_evidence_weakness','-')}")
        sections.append(('Evidence Map / Pemetaan Bukti', ev_lines))

        lc=wp.get('legal_construction') or {}
        legal_lines=['Jalinan utama: '+str(lc.get('synthesis') or x.get('legal_analysis') or '-')]
        for c in (lc.get('chains') or [])[:8]:
            score=c.get('evidence_nexus_score') or 0
            prob=c.get('probative_score') or 0
            nexus=(f" | Keterkaitan topik: {round(float(score)*100)}% — {c.get('evidence_nexus_reason','-')}" if score else '')
            probative=(f" | Bobot pembuktian: {_human_release_status(c.get('probative_level') or 'NONE')} ({round(float(prob)*100)}%) — {c.get('probative_reason','-')}" if prob or c.get('probative_reason') else '')
            legal_lines.append(f"ISU: {c.get('issue','-')} | FAKTA/DALIL: {c.get('material_fact','-')} | SUMBER: {_human_evidence_class(c.get('supporting_evidence','-'))} — {c.get('evidence_reference','-')}{nexus}{probative} | ATURAN: {c.get('legal_rule','-')} | ANALISIS: {c.get('causal_logic','-')} | STATUS: {_human_release_status(c.get('construction_status','-'))}")
        sections.append(('Analisis Hukum / Legal Construction', legal_lines))

        action_lines=[]
        for a in (wp.get('action_plan') or [])[:14]:
            action_lines.append(f"Langkah {a.get('step','-')} | {a.get('time_window','-')} | {a.get('priority','P2')} | {a.get('action','-')} | Tujuan: {a.get('objective','-')} | Kondisi: {a.get('condition','-')}")
        sections.append(('Action Plan / Rencana Tindakan', action_lines or ['Belum ada action plan taktis terstruktur.']))
    else:
        readiness=x.get('case_readiness') or {}
        if readiness:
            comp=readiness.get('components') or {}
            rlines=[f"Overall readiness: {readiness.get('overall_percentage',0)}%",
                    f"Evidence Map: {(comp.get('evidence_map') or {}).get('percentage',0)}%",
                    f"Analisis Hukum: {(comp.get('legal_analysis') or {}).get('percentage',0)}%",
                    f"Action Plan: {(comp.get('action_plan') or {}).get('percentage',0)}%",
                    readiness.get('disclaimer') or 'Bukan prediksi hasil perkara.']
            sections.append(('Case Readiness Review', rlines))
    review=x.get('professional_review') or {}
    if review:
        review_lines=[
            f"Status review: {_human_release_status(review.get('review_status','-'))}",
            f"Tipe dokumen: {_human_release_status((review.get('document_structure') or {}).get('document_type','-'))}",
        ]
        st=review.get('document_structure') or {}
        if st.get('completeness') is not None:
            review_lines.append(f"Kelengkapan struktur terdeteksi: {st.get('completeness')}%")
        if review.get('strengths'):
            review_lines.append('Kekuatan yang teridentifikasi:')
            review_lines += ['- '+str(v) for v in review.get('strengths')[:8]]
        if review.get('findings'):
            review_lines.append('Temuan kritis dan kelemahan:')
            for f in review.get('findings')[:18]:
                line=f"- [{_human_release_status(f.get('severity','-'))}] {_human_review_type(f.get('type'))}: {f.get('finding','-')}"
                if f.get('source_text'): line += f" | Teks sumber: {f.get('source_text')}"
                if f.get('candidate'):
                    cand=str(f.get('candidate'))
                    if cand.lower().startswith('kandidat:'): cand=cand.split(':',1)[1].strip()
                    line += f" | Kandidat: {cand}"
                if f.get('recommendation'): line += f" | Rekomendasi: {f.get('recommendation')}"
                review_lines.append(line)
        if review.get('recommendations'):
            review_lines.append('Rekomendasi prioritas:')
            for r in review.get('recommendations')[:14]:
                review_lines.append(f"- {r.get('priority','P2')} | {r.get('action','-')} | Dasar: {r.get('basis','-')}")
        sr=review.get('strategic_recommendation') or {}
        if sr:
            review_lines.append('Rekomendasi strategis penyusunan:')
            if sr.get('approach'): review_lines.append('Pendekatan: '+_human_release_status(sr.get('approach')))
            review_lines += ['- '+str(v) for v in (sr.get('priorities') or [])[:10]]
            if sr.get('recommended_outline'):
                review_lines.append('Struktur yang direkomendasikan:')
                review_lines += [f"{i}. {v}" for i,v in enumerate((sr.get('recommended_outline') or [])[:12],1)]
        review_lines.append(review.get('disclaimer') or '')
        sections.append(('Audit Dokumen Terperinci', review_lines))

    summary_lines=_export_item_lines(x.get('executive_summary') or x.get('decision_summary') or x.get('legal_analysis') or '-')
    if executive_review:
        summary_lines=summary_lines[:2]
        summary_lines.append('Detail temuan dan rekomendasi tersedia pada Ringkasan Review Hukum dan Audit Dokumen Terperinci.')
    sections.append(('Ringkasan Eksekutif', summary_lines))

    ledger=x.get('material_source_ledger') or []
    source_lines=[]
    for item in ledger:
        if not isinstance(item,dict): continue
        label=_human_evidence_class(item.get('display_classification') or item.get('source_classification') or item.get('label') or 'SOURCE FACT')
        statement=item.get('statement') or '-'
        segment=item.get('segment')
        evidence=item.get('evidence')
        line=f'[{label}] {statement}' + (f' (Segmen {segment})' if segment else '')
        if evidence: line += f' | Dasar dokumen: {evidence}'
        source_lines.append(line)
    sections.append(('Jejak Sumber Material', source_lines or ['Tidak ada sumber material yang layak ditampilkan.']))

    # Evidence Map deliberately summarizes mapping and gaps; it does not repeat the raw document.
    counts={}; segs={}
    for item in ledger:
        if not isinstance(item,dict): continue
        label=str(item.get('label') or 'SOURCE FACT'); counts[label]=counts.get(label,0)+1
        seg=str(item.get('segment') or 'Tanpa segmen'); segs[seg]=segs.get(seg,0)+1
    evidence_lines=[f'{k}: {v} item' for k,v in sorted(counts.items())]
    groups=x.get('evidence_groups') or []
    if groups:
        evidence_lines.append('EVIDENCE GROUPS:')
        for g in groups[:12]:
            evidence_lines.append(f"{g.get('label') or g.get('id')}: {g.get('item_count',0)} item")
            for fact in (g.get('material_facts') or [])[:6]:
                evidence_lines.append('  - '+str(fact))
    else:
        evidence_lines += [f'Segmen {k}: {v} item evidence' for k,v in list(segs.items())[:40]]
    gaps=x.get('evidentiary_gaps') or x.get('evidence_needed') or []
    if gaps:
        evidence_lines.append('EVIDENTIARY GAPS:')
        evidence_lines += ['- '+line for line in _export_item_lines(gaps)]
    if not wp:
        sections.append(('Evidence Map', evidence_lines or ['Belum ada evidence map terstruktur.']))

    legal=[]
    if x.get('legal_status'): legal.append('Status hukum positif: '+_export_scalar(x.get('legal_status')))
    if x.get('legal_analysis'): legal.append('Analisis utama: '+_export_scalar(x.get('legal_analysis')))
    for label,key in [('Mens rea / niat','mens_rea_analysis'),('Actual loss / kerugian nyata','actual_loss_analysis'),('Causal nexus','causation_analysis'),('Personal responsibility','personal_responsibility_analysis'),('Tempus / hukum temporal','temporal_law_analysis')]:
        if x.get(key): legal.append(f'{label}: {_export_scalar(x.get(key))}')
    if x.get('legal_issues'):
        legal.append('Isu hukum:'); legal += ['- '+v for v in _export_item_lines(x.get('legal_issues'))]
    if x.get('element_matrix'):
        legal.append('Matriks unsur:'); legal += ['- '+v for v in _export_item_lines(x.get('element_matrix'))]
    if not wp:
        sections.append(('Analisis Hukum', legal or ['Belum ada analisis hukum terstruktur.']))

    applicable=x.get('applicable_law') or []
    _snap_for_law=x.get('case_regulatory_snapshot') or {}
    _funnel_for_law=_snap_for_law.get('retrieval_funnel') or {}
    _verified_law=int(_funnel_for_law.get('verified_applicable') or _funnel_for_law.get('temporal_verified_applicable') or 0)
    law_title='Dasar Hukum Terverifikasi' if _verified_law>0 else 'Kandidat Dasar Hukum yang Perlu Diverifikasi'
    sections.append((law_title, _export_item_lines(applicable) or ['Belum ada kandidat dasar hukum yang terstruktur.']))

    # Case report carries only regulatory essentials. Full corpus/intelligence remains in Regulatory Corpus workspace.
    regs=x.get('regulatory_matches') or []
    snap=x.get('case_regulatory_snapshot') or {}
    regs=[r for r in regs if isinstance(r,dict) and _regulation_allowed_for_case_domains(r, snap)]
    event_year=snap.get('event_year_candidate')
    event_date=snap.get('event_date_candidate')
    reg_lines=[]
    verified_official=[
        r for r in (snap.get('official_results') or [])
        if isinstance(r,dict) and regulation_merits_reportable(r)
    ]
    for r in verified_official[:8]:
        v=r.get('positive_law_verification') or {}
        title=r.get('title') or '-'
        line=(f"{title} | Sumber resmi: {'Terkonfirmasi' if v.get('official_source_confirmed') else 'Belum terkonfirmasi'}"
              f" | Teks hukum: {'Tersedia' if v.get('text_retrieved') else 'Belum terverifikasi'}"
              f" | Status norma: {_human_release_status(v.get('legal_status') or 'UNVERIFIED')}"
              f" | Waktu berlaku: {_human_release_status(v.get('tempus_status') or 'TEMPUS_UNVERIFIED')}"
              f" | Acuan waktu: {_human_release_status(v.get('tempus_anchor_type') or 'UNKNOWN')}"
              f" | Keterkaitan perkara: {_human_release_status(v.get('case_nexus_status') or 'CASE_NEXUS_UNCERTAIN')}"
              f" | Status akhir: {_human_release_status(v.get('final_status') or 'UNVERIFIED')}")
        pv=v.get('provision_verification') or {}
        if pv.get('requested_count'):
            refs=', '.join(pv.get('verified') or pv.get('requested') or [])
            line += (f" | Verifikasi pasal: {_human_release_status(pv.get('status') or 'PROVISION_UNVERIFIED')}"
                     f" ({pv.get('verified_count',0)}/{pv.get('requested_count',0)}"
                     + (f": {refs}" if refs else '') + ')')
            cites=pv.get('citations') or []
            if cites and cites[0].get('source_url'):
                line += f" | Provision Citation: {cites[0].get('source_url')}"
        reg_lines.append(line)
    if not reg_lines:
        for r in regs[:8]:
            if not isinstance(r,dict): continue
            g=r.get('regulation') or {}
            title=g.get('qualified_citation') or g.get('nomor') or g.get('tentang') or '-'
            temporal,anchor_type=_tempus_status(g,snap)
            line=f"{title} | Waktu berlaku: {_human_release_status(temporal)} | Acuan waktu: {_human_release_status(anchor_type)}"
            arts=r.get('matched_articles') or []
            if arts:
                refs=[]
                for a in arts[:4]:
                    if isinstance(a,dict): refs.append((a.get('qualified_citation') or a.get('pasal') or a.get('topic') or '').strip())
                if refs: line += ' | Relevansi: ' + '; '.join(refs)
            reg_lines.append(line)
    sections.append(('Regulasi & Tempus', reg_lines or ['Belum ada regulasi material yang dapat dinyatakan applicable tanpa verifikasi sumber resmi.']))

    nc=x.get('norm_conflicts') or {}
    conflict_lines=_norm_conflict_export_lines(nc)
    sections.append(('Analisis Konflik Norma', conflict_lines or ['Tidak ada antinomi material yang terdeteksi; hubungan hierarki/kronologi saja tidak diperlakukan sebagai konflik norma.']))

    action=x.get('action_plan') or x.get('recommendations') or []
    action_lines=[]
    if isinstance(action,dict):
        # Export only WHAT TO DO, matching the UI contract.
        for key in ('what_to_do','actions','priorities','next_steps'):
            if action.get(key): action_lines += _export_item_lines(action.get(key))
        if not action_lines:
            for k,v in action.items():
                if any(word in k.lower() for word in ('action','do','step','priority','recommend')):
                    action_lines += _export_item_lines(v)
    else:
        action_lines=_export_item_lines(action)
    if not wp:
        sections.append(('Action Plan / Langkah Tindak Lanjut', action_lines or ['Belum ada action plan terstruktur.']))

    ov=x.get('official_verification') or {}
    snap=x.get('case_regulatory_snapshot') or {}
    funnel=snap.get('retrieval_funnel') or {}
    verify_lines=[]
    if ov or snap:
        sm=ov.get('summary') or {} if isinstance(ov,dict) else {}
        verify_lines += [
            'Status akses sumber: '+_human_release_status((ov or {}).get('status') if isinstance(ov,dict) else '-'),
            'Waktu pemeriksaan: '+_export_scalar((ov or {}).get('checked_at') if isinstance(ov,dict) else snap.get('fetched_at')),
            'Verifikasi profesional: '+_human_release_status((ov or {}).get('professional_verification') if isinstance(ov,dict) else snap.get('professional_verification') or 'PENDING'),
            f"Sumber otoritatif terjangkau: {sm.get('authoritative_sources_reached',0)}/{sm.get('authoritative_sources_total',0)}",
        ]
        if funnel:
            verify_lines += [
                'Hasil penelusuran: '+str(funnel.get('discovered',0)),
                'Hasil unik setelah penyaringan: '+str(funnel.get('unique_discovered',0)),
                'Kandidat yang berpotensi relevan: '+str(funnel.get('candidate',0)),
                'Relevan secara material: '+str(funnel.get('materially_relevant',0)),
                'Lolos filter tempus awal: '+str(funnel.get('temporal_not_excluded',0)),
                'Sumber otoritatif ditemukan: '+str(funnel.get('authoritative_source_located',0)),
                'Kandidat dokumen hukum: '+str(funnel.get('legal_document_candidates',0)),
                'Konten resmi non-hukum ditolak: '+str(funnel.get('rejected_non_legal_content',0)),
                'Status hukum positif terverifikasi: '+str(funnel.get('positive_law_verified',0)),
                'Tempus terverifikasi: '+str(funnel.get('tempus_verified',0)),
                'Regulasi terverifikasi relevan dan berlaku: '+str(funnel.get('verified_applicable',funnel.get('temporal_verified_applicable',0))),
                'Pasal yang diperiksa: '+str(funnel.get('provision_requested',0)),
                'Pasal yang berhasil diverifikasi pada teks resmi: '+str(funnel.get('provision_verified',0)),
            ]
        elif sm:
            verify_lines.append('Hasil penelusuran: '+str(sm.get('results_found',0)))
        if snap.get('event_date_candidate'):
            verify_lines.append('Kandidat tanggal peristiwa material: '+str(snap.get('event_date_candidate')))
        if snap.get('procedural_date_candidate'):
            verify_lines.append('Kandidat tanggal proses/prosedural: '+str(snap.get('procedural_date_candidate')))
        elif snap.get('event_year_candidate'):
            verify_lines.append('Kandidat tahun peristiwa untuk screening tempus: '+str(snap.get('event_year_candidate')))
        domains=snap.get('domains') or []
        if domains:
            verify_lines.append('Ruang lingkup utama:')
            for d in domains[:4]:
                if isinstance(d,dict):
                    verify_lines.append(f"- {d.get('label') or d.get('id')} ({round(float(d.get('confidence',0))*100)}%)")
        verify_lines.append('Catatan: sumber resmi yang dapat dijangkau atau ditemukan belum berarti norma tersebut telah terverifikasi berlaku pada perkara. Verifikasi profesional masih diperlukan.')
    sections.append(('Pemeriksaan Sumber Hukum Resmi', verify_lines or ['Verifikasi sumber resmi tidak dijalankan / tidak tersedia.']))

    coverage=x.get('coverage_note') or 'Verifikasi profesional: Menunggu verifikasi lawyer.'
    sections.append(('Cakupan & Verifikasi Profesional', [coverage, 'Dokumen ini adalah working paper LexiCore by ELF - Erfan\'s Law Firm dan wajib diverifikasi lawyer sebelum dipakai sebagai dasar tindakan hukum.']))
    return meta, sections


