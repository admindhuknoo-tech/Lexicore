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


def _case_export_sections(x):
    """Single canonical export model for PDF and DOCX case-analysis results."""
    dr=x.get('document_reading') or {}
    provenance=x.get('analysis_provenance') or {}
    method=provenance.get('mode') or x.get('analytical_method') or 'CASE_ANALYSIS'
    provider=provenance.get('provider') or dr.get('provider') or '-'
    model=provenance.get('model') or dr.get('model') or '-'
    meta=[
        ('Judul', x.get('title') or 'Case Analysis'),
        ('Metode', method),
        ('AI Provider / Model', f'{provider} / {model}'),
        ('Input', x.get('input_type') or '-'),
        ('Dokumen', x.get('filename') or '-'),
        ('Pembacaan', f"{dr.get('status','UNKNOWN')} - {dr.get('segments_read',0)}/{dr.get('segments_total',0)} segmen - {dr.get('characters',0)} karakter"),
    ]
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
    meta.append(('Professional Verification', x.get('professional_verification') or 'PENDING'))
    sections=[]
    readiness=x.get('case_readiness') or {}
    if readiness:
        comp=readiness.get('components') or {}
        rlines=[f"Overall readiness: {readiness.get('overall_percentage',0)}%",
                f"Evidence Map: {(comp.get('evidence_map') or {}).get('percentage',0)}%",
                f"Analisis Hukum: {(comp.get('legal_analysis') or {}).get('percentage',0)}%",
                f"Action Plan: {(comp.get('action_plan') or {}).get('percentage',0)}%",
                readiness.get('disclaimer') or 'Bukan prediksi hasil perkara.']
        sections.append(('Case Readiness Review', rlines))
    sections.append(('Ringkasan Eksekutif', _export_item_lines(x.get('executive_summary') or x.get('decision_summary') or x.get('legal_analysis') or '-')))

    ledger=x.get('source_ledger') or []
    source_lines=[]
    for item in ledger:
        if not isinstance(item,dict): continue
        label=item.get('label') or 'SOURCE FACT'
        statement=item.get('statement') or '-'
        segment=item.get('segment')
        evidence=item.get('evidence')
        line=f'[{label}] {statement}' + (f' (Segmen {segment})' if segment else '')
        if evidence: line += f' | Dasar dokumen: {evidence}'
        source_lines.append(line)
    sections.append(('Dokumen Sumber - Source Ledger', source_lines or ['Tidak ada source ledger terstruktur.']))

    # Evidence Map deliberately summarizes mapping and gaps; it does not repeat the raw document.
    counts={}; segs={}
    for item in ledger:
        if not isinstance(item,dict): continue
        label=str(item.get('label') or 'SOURCE FACT'); counts[label]=counts.get(label,0)+1
        seg=str(item.get('segment') or 'Tanpa segmen'); segs[seg]=segs.get(seg,0)+1
    evidence_lines=[f'{k}: {v} item' for k,v in sorted(counts.items())]
    evidence_lines += [f'Segmen {k}: {v} item evidence' for k,v in list(segs.items())[:40]]
    gaps=x.get('evidentiary_gaps') or x.get('evidence_needed') or []
    if gaps:
        evidence_lines.append('EVIDENTIARY GAPS:')
        evidence_lines += ['- '+line for line in _export_item_lines(gaps)]
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
    sections.append(('Analisis Hukum', legal or ['Belum ada analisis hukum terstruktur.']))

    applicable=x.get('applicable_law') or []
    sections.append(('Dasar Hukum', _export_item_lines(applicable) or ['Belum ada dasar hukum yang terstruktur.']))

    # Case report carries only regulatory essentials. Full corpus/intelligence remains in Regulatory Corpus workspace.
    regs=x.get('regulatory_matches') or []
    snap=x.get('case_regulatory_snapshot') or {}
    regs=[r for r in regs if isinstance(r,dict) and _regulation_allowed_for_case_domains(r, snap)]
    event_year=snap.get('event_year_candidate')
    event_date=snap.get('event_date_candidate')
    reg_lines=[]
    for r in regs[:8]:
        if not isinstance(r,dict): continue
        g=r.get('regulation') or {}
        title=g.get('qualified_citation') or g.get('nomor') or g.get('tentang') or '-'
        eff=str(g.get('effective_date') or g.get('berlaku') or '')
        temporal='UNVERIFIED'
        if event_date and eff:
            if eff > str(event_date):
                temporal='POST_TEMPUS_EXCLUDED'
            else:
                temporal='POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE'
        elif event_year and eff[:4].isdigit():
            eff_year=int(eff[:4])
            evt_year=int(event_year)
            if eff_year > evt_year:
                temporal='POST_TEMPUS_EXCLUDED'
            elif eff_year == evt_year:
                # Year-only evidence cannot establish whether a regulation took effect
                # before or after the material event within that same year.
                temporal='TEMPUS_REQUIRES_EXACT_DATE'
            else:
                temporal='POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE'
        line=f"{title} | Tempus: {temporal}"
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
    sections.append(('Action Plan / Langkah Tindak Lanjut', action_lines or ['Belum ada action plan terstruktur.']))

    ov=x.get('official_verification') or {}
    snap=x.get('case_regulatory_snapshot') or {}
    funnel=snap.get('retrieval_funnel') or {}
    verify_lines=[]
    if ov or snap:
        sm=ov.get('summary') or {} if isinstance(ov,dict) else {}
        verify_lines += [
            'Status akses sumber: '+_export_scalar((ov or {}).get('status') if isinstance(ov,dict) else '-'),
            'Waktu pemeriksaan: '+_export_scalar((ov or {}).get('checked_at') if isinstance(ov,dict) else snap.get('fetched_at')),
            'Verifikasi profesional: '+_export_scalar((ov or {}).get('professional_verification') if isinstance(ov,dict) else snap.get('professional_verification') or 'PENDING'),
            f"Sumber otoritatif terjangkau: {sm.get('authoritative_sources_reached',0)}/{sm.get('authoritative_sources_total',0)}",
        ]
        if funnel:
            verify_lines += [
                'Hasil discovery: '+str(funnel.get('discovered',0)),
                'Hasil unik: '+str(funnel.get('unique_discovered',0)),
                'Kandidat relevan: '+str(funnel.get('candidate',0)),
                'Relevan secara material: '+str(funnel.get('materially_relevant',0)),
                'Lolos filter tempus awal: '+str(funnel.get('temporal_not_excluded',0)),
                'Sumber otoritatif ditemukan: '+str(funnel.get('authoritative_source_located',0)),
                'Berlaku pada tempus (terverifikasi): '+str(funnel.get('temporal_verified_applicable',0)),
            ]
        elif sm:
            verify_lines.append('Hasil discovery: '+str(sm.get('results_found',0)))
        if snap.get('event_date_candidate'):
            verify_lines.append('Kandidat tanggal peristiwa untuk screening tempus: '+str(snap.get('event_date_candidate')))
        elif snap.get('event_year_candidate'):
            verify_lines.append('Kandidat tahun peristiwa untuk screening tempus: '+str(snap.get('event_year_candidate')))
        domains=snap.get('domains') or []
        if domains:
            verify_lines.append('Ruang lingkup utama:')
            for d in domains[:4]:
                if isinstance(d,dict):
                    verify_lines.append(f"- {d.get('label') or d.get('id')} ({round(float(d.get('confidence',0))*100)}%)")
        verify_lines.append('Catatan: source reachable / source located bukan sama dengan norma telah diverifikasi berlaku. Professional Verification tetap PENDING.')
    sections.append(('Verifikasi Sumber Hukum Resmi', verify_lines or ['Verifikasi sumber resmi tidak dijalankan / tidak tersedia.']))

    coverage=x.get('coverage_note') or 'Professional Verification: PENDING.'
    sections.append(('Cakupan & Verifikasi Profesional', [coverage, 'Dokumen ini adalah working paper LexiCore by ELF - Erfan\'s Law Firm dan wajib diverifikasi lawyer sebelum dipakai sebagai dasar tindakan hukum.']))
    return meta, sections


