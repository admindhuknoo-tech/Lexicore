from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


def _clean(v: Any) -> str:
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def _tokens(text: str) -> set[str]:
    stop = {
        'yang','dan','atau','untuk','dari','pada','dalam','oleh','sebagai','adalah','bahwa','ini','itu','telah','akan','agar','atas',
        'kepada','terhadap','menjadi','dapat','harus','apakah','terdapat','perlu','belum','sudah','secara','serta','antara','setiap',
        'suatu','karena','namun','tidak','bukan','juga','lebih','masih','maka','bila','jika','tersebut','perkara','hukum','fakta',
        'bukti','unsur','pihak','dokumen','analisis'
    }
    return {t for t in re.findall(r'[a-zA-ZÀ-ÿ0-9]+', str(text or '').lower()) if len(t) >= 3 and t not in stop and not t.isdigit()}


DOMAIN_ELEMENT_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    'electoral_ethics': [
        {
            'id': 'forum_subject',
            'description': 'Kedudukan pihak sebagai penyelenggara/teradu dan kewenangan forum etik yang memeriksa',
            'keywords': ['dkpp','kpu','bawaslu','teradu','pengadu','anggota kpu','penyelenggara','kewenangan','kode etik'],
        },
        {
            'id': 'normative_duty',
            'description': 'Norma etik/kelembagaan yang secara spesifik membentuk kewajiban atau larangan',
            'keywords': ['kode etik','pedoman perilaku','asas mandiri','jujur','adil','profesional','akuntabel','pasal','peraturan dkpp'],
        },
        {
            'id': 'material_conduct',
            'description': 'Tindakan/kelalaian material yang secara konkret dipersoalkan dalam aduan',
            'keywords': ['terlibat','kepengurusan','pengurus','menjabat','status','organisasi','mengundurkan diri','memberhentikan','surat pernyataan','hadir','kehadiran','narasumber','atribut'],
        },
        {
            'id': 'status_timeline',
            'description': 'Status jabatan/keanggotaan dan kronologi tanggal yang menentukan posisi etik pada tempus peristiwa',
            'keywords': ['tanggal','periode','pengunduran diri','mengundurkan diri','memberhentikan','ditetapkan','surat keputusan','sk ','periode 2020-2025','pendidikan','kuliah','perkuliahan','izin','s1','s2'],
        },
        {
            'id': 'proof_authenticity',
            'description': 'Keaslian, isi, kewenangan penerbit, dan relevansi bukti T/P atau surat keputusan yang dirujuk',
            'keywords': ['bukti t-','bukti p-','surat keputusan','sk ','rekomendasi','surat dinas','ditandatangani','materai','dokumen'],
        },
        {
            'id': 'nexus_impact',
            'description': 'Hubungan antara status/tindakan yang terbukti dengan dugaan pelanggaran etik serta dampaknya pada integritas/kewajiban penyelenggara',
            'keywords': ['karena','sehingga','akibat','kehormatan','integritas','kode etik','terlibat','status','kepengurusan','pengunduran diri','konflik kepentingan','mengganggu','gangguan tugas','keuntungan pribadi','pendidikan','perkuliahan'],
        },
    ],
    'civil_contract': [
        {'id':'valid_contract','description':'Keberadaan dan keabsahan hubungan/perjanjian yang mengikat para pihak','keywords':['perjanjian','kontrak','kesepakatan','pasal 1320','pasal 1338']},
        {'id':'obligation','description':'Prestasi/kewajiban konkret yang harus dipenuhi','keywords':['kewajiban','prestasi','pembayaran','penyerahan','jatuh tempo']},
        {'id':'breach','description':'Cidera janji/wanprestasi atau kegagalan memenuhi prestasi','keywords':['wanprestasi','cidera janji','tidak membayar','terlambat','lalai']},
        {'id':'default_notice','description':'Somasi/pernyataan lalai bila diperlukan menurut hubungan hukum','keywords':['somasi','teguran','dinyatakan lalai','pasal 1238']},
        {'id':'loss_nexus','description':'Kerugian dan hubungan kausal dengan pelanggaran kewajiban','keywords':['kerugian','ganti rugi','akibat','kausal','sebab']},
    ],
    'civil_tort': [
        {'id':'pmh_unlawful_act','description':'Perbuatan melawan hukum yang secara konkret didalilkan dan dapat diatribusikan kepada pihak tertentu','keywords':['perbuatan melawan hukum','pmh','melawan hukum','perbuatan','atribusi']},
        {'id':'pmh_fault','description':'Kesalahan atau dasar pertanggungjawaban yang relevan terhadap perbuatan yang didalilkan','keywords':['kesalahan','kelalaian','sengaja','tanggung jawab','bertanggung jawab']},
        {'id':'pmh_loss','description':'Kerugian yang nyata dan dapat dibuktikan sebagai akibat yang diklaim','keywords':['kerugian','ganti rugi','rugi','kehilangan']},
        {'id':'pmh_causation','description':'Hubungan kausal antara perbuatan yang didalilkan dan kerugian yang dimintakan pemulihan','keywords':['akibat','kausal','sebab','hubungan sebab','kerugian']},
        {'id':'pmh_remedy','description':'Pemulihan/petitum yang mempunyai dasar dan proporsional terhadap PMH yang terbukti','keywords':['petitum','ganti rugi','pemulihan','pembatalan','menghukum','permohonan']},
    ],
    'civil_procedure': [
        {'id':'procedural_standing','description':'Kedudukan hukum, kapasitas para pihak, dan kelengkapan kuasa/representasi','keywords':['legal standing','kedudukan hukum','kapasitas','surat kuasa','penggugat','tergugat','para pihak']},
        {'id':'absolute_competence','description':'Kompetensi absolut forum berdasarkan subjek, objek, dan karakter hubungan hukum','keywords':['kompetensi absolut','kewenangan absolut','pengadilan agama','pengadilan negeri','waris','objek sengketa']},
        {'id':'relative_competence','description':'Kompetensi relatif dan dasar pemilihan pengadilan yang memeriksa','keywords':['kompetensi relatif','kewenangan relatif','domisili','tempat tinggal','forum','pengadilan negeri']},
        {'id':'pleading_consistency','description':'Kejelasan dan konsistensi posita, petitum, objek sengketa, serta pihak yang ditarik','keywords':['posita','petitum','obscuur','kabur','objek sengketa','plurium','kurang pihak']},
        {'id':'procedural_consequence','description':'Akibat hukum dan petitum yang proporsional terhadap cacat formil/prosedural yang terbukti','keywords':['tidak dapat diterima','niet ontvankelijke','no','petitum','akibat hukum','eksepsi']},
    ],
    'land_property': [
        {'id':'land_right_identity','description':'Identitas objek tanah dan dasar/alas hak yang menjadi sumber klaim','keywords':['sertipikat','sertifikat','shm','buku tanah','surat ukur','alas hak','warkah','objek sengketa']},
        {'id':'land_registration_history','description':'Riwayat pendaftaran, peralihan, data fisik/yuridis, dan proses penerbitan hak','keywords':['pendaftaran tanah','peralihan','balik nama','data fisik','data yuridis','bpn','kantor pertanahan','skpt']},
        {'id':'certificate_validity','description':'Keabsahan/status sertipikat dan dasar konkret serangan atau pembelaan terhadap sertipikat','keywords':['cacat hukum','pembatalan sertipikat','sertipikat cacat','sertifikat cacat','keabsahan sertipikat','pasal 32']},
        {'id':'land_claim_nexus','description':'Hubungan antara alas hak/riwayat penguasaan dengan hak yang dituntut dan kerugian yang diklaim','keywords':['hak atas tanah','penguasaan','kepemilikan','kerugian','akibat','hubungan','kausal']},
    ],
    'religious_court': [
        {'id':'religious_forum_subject','description':'Status para pihak dan hubungan hukum yang menentukan kemungkinan kewenangan Peradilan Agama','keywords':['pengadilan agama','peradilan agama','agama islam','muslim','para pihak','status para pihak']},
        {'id':'inheritance_character','description':'Karakter sengketa waris, pewaris, ahli waris, harta peninggalan, dan pembagian yang dipersoalkan','keywords':['waris','pewaris','ahli waris','harta peninggalan','harta waris','pembagian waris']},
        {'id':'religious_absolute_competence','description':'Nexus antara status para pihak/objek sengketa dan kompetensi absolut Peradilan Agama','keywords':['kompetensi absolut','kewenangan peradilan agama','pasal 49','waris islam','objek sengketa']},
    ],
    'employment': [
        {'id':'employment_relation','description':'Adanya hubungan kerja dan status pekerja/pemberi kerja','keywords':['pekerja','buruh','karyawan','pemberi kerja','hubungan kerja','pkwt','pkwtt']},
        {'id':'employer_action','description':'Tindakan perusahaan yang dipersoalkan, termasuk PHK/perubahan syarat kerja','keywords':['phk','pemutusan hubungan kerja','surat peringatan','mutasi','skorsing']},
        {'id':'procedure','description':'Pemenuhan prosedur wajib, termasuk pemberitahuan/bipartit/PHI bila relevan','keywords':['bipartit','phi','pemberitahuan','perundingan','mediasi']},
        {'id':'normative_rights','description':'Hak normatif seperti upah, kompensasi, pesangon, atau hak lain','keywords':['upah','pesangon','kompensasi','hak normatif']},
        {'id':'impact_nexus','description':'Hubungan tindakan perusahaan dengan kerugian/hak yang dituntut','keywords':['kerugian','kehilangan upah','akibat','hak','kompensasi']},
    ],
}


DOMAIN_ISSUE_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    'electoral_ethics': [
        {
            'id':'organization_status',
            'issue':'Apakah status kepengurusan/afiliasi organisasi benar-benar masih aktif pada tempus yang relevan?',
            'element_ids':['material_conduct','status_timeline','proof_authenticity','nexus_impact'],
            'risk_kind':'status_and_affiliation',
            'keywords':['pengurus','kepengurusan','menjabat','lazismu','knpi','mengundurkan diri','pengunduran diri','memberhentikan','status organisasi'],
        },
        {
            'id':'appearance_affiliation',
            'issue':'Apakah tindakan atau kehadiran publik hanya menimbulkan appearance of affiliation atau membuktikan konflik kepentingan aktual?',
            'element_ids':['material_conduct','normative_duty','nexus_impact'],
            'risk_kind':'appearance_vs_actual_conflict',
            'keywords':['hadir','kehadiran','narasumber','tamu','atribut','afiliasi','konflik kepentingan','kegiatan','appearance'],
        },
        {
            'id':'professional_activity',
            'issue':'Apakah kegiatan/profesi/pendidikan lain terjadi pada tempus yang dilarang dan mempunyai nexus dengan pelaksanaan tugas penyelenggara?',
            'element_ids':['status_timeline','normative_duty','nexus_impact'],
            'risk_kind':'outside_activity',
            'keywords':['pendidikan','kuliah','perkuliahan','s1','s2','izin','kegiatan lain','profesi','tempus'],
        },
        {
            'id':'document_integrity',
            'issue':'Apakah dokumen, gelar, status, atau keterangan yang dipersoalkan terbukti tidak sah/menyesatkan berdasarkan bukti primer?',
            'element_ids':['proof_authenticity','material_conduct','nexus_impact'],
            'risk_kind':'integrity_and_authenticity',
            'keywords':['gelar','ijazah','palsu','tidak sah','keabsahan','dokumen','keterangan','penerbit'],
        },
    ],
    'civil_contract': [
        {'id':'contract_binding','issue':'Apakah terdapat hubungan kontraktual yang sah dan kewajiban yang mengikat?','element_ids':['valid_contract','obligation'],'risk_kind':'binding_obligation'},
        {'id':'breach_default','issue':'Apakah terjadi wanprestasi/cidera janji dan, bila relevan, telah ada keadaan lalai?','element_ids':['breach','default_notice'],'risk_kind':'breach'},
        {'id':'loss_causation','issue':'Apakah kerugian yang diklaim mempunyai hubungan kausal dengan pelanggaran kewajiban?','element_ids':['loss_nexus'],'risk_kind':'loss_nexus'},
    ],
    'civil_tort': [
        {'id':'pmh_elements','issue':'Apakah dalil Perbuatan Melawan Hukum mempunyai perbuatan konkret, dasar kesalahan/pertanggungjawaban, kerugian, hubungan kausal, dan petitum yang dapat diuji?','element_ids':['pmh_unlawful_act','pmh_fault','pmh_loss','pmh_causation','pmh_remedy'],'risk_kind':'civil_tort_liability','keywords':['perbuatan melawan hukum','pmh','kerugian','kausal','ganti rugi','petitum']},
    ],
    'civil_procedure': [
        {'id':'procedural_validity','issue':'Apakah gugatan memenuhi syarat formil, para pihak lengkap, posita-petitum konsisten, dan pengadilan yang dipilih memiliki kompetensi absolut serta relatif?','element_ids':['procedural_standing','absolute_competence','relative_competence','pleading_consistency','procedural_consequence'],'risk_kind':'procedure_and_forum','keywords':['kompetensi','gugatan','penggugat','tergugat','posita','petitum','eksepsi','surat kuasa']},
    ],
    'land_property': [
        {'id':'land_title_chain','issue':'Bagaimana riwayat alas hak, data fisik/yuridis, proses pendaftaran, status sertipikat, dan hubungan antara bukti keperdataan dengan administrasi pertanahan?','element_ids':['land_right_identity','land_registration_history','certificate_validity','land_claim_nexus'],'risk_kind':'land_title_and_registration','keywords':['sertipikat','sertifikat','alas hak','buku tanah','warkah','pendaftaran tanah','bpn','skpt']},
    ],
    'religious_court': [
        {'id':'religious_absolute_forum','issue':'Apakah materi sengketa termasuk kompetensi absolut Peradilan Agama berdasarkan status para pihak dan objek sengketa yang sebenarnya?','element_ids':['religious_forum_subject','inheritance_character','religious_absolute_competence'],'risk_kind':'absolute_competence','keywords':['waris','pengadilan agama','peradilan agama','kompetensi absolut','pasal 49','ahli waris']},
    ],
    'employment': [
        {'id':'employment_status','issue':'Apakah hubungan kerja dan status para pihak dapat dibuktikan?','element_ids':['employment_relation'],'risk_kind':'employment_status'},
        {'id':'employer_measure','issue':'Apakah tindakan perusahaan/PHK mempunyai dasar dan prosedur yang dapat diverifikasi?','element_ids':['employer_action','procedure'],'risk_kind':'employer_action'},
        {'id':'rights_loss','issue':'Apakah hak normatif dan kerugian yang diklaim mempunyai nexus dengan tindakan perusahaan?','element_ids':['normative_rights','impact_nexus'],'risk_kind':'rights_impact'},
    ],
}

CORRECTIVE_CUES = (
    'mengundurkan diri','pengunduran diri','dikoreksi','koreksi','dihapus','memberhentikan dengan hormat',
    'klarifikasi','perbaikan','memperbaiki','revisi'
)
INTENT_CUES = ('sengaja','niat','itikad buruk','bad faith','mengetahui','dengan sadar','bermaksud')
IMPACT_CUES = ('kerugian','dampak','mengganggu','terganggu','konflik kepentingan','keuntungan pribadi','penyalahgunaan')



COUNTER_CUES = (
    'menolak', 'tidak benar', 'tidak mengetahui', 'mengundurkan diri', 'pengunduran diri', 'memberhentikan dengan hormat',
    'bukan', 'sanggahan', 'membantah', 'tidak terlibat', 'tidak pernah', 'cacat hukum'
)


def _active_domains(domain_contract: Dict[str, Any] | None) -> List[str]:
    dc = domain_contract or {}
    out = list(dc.get('domain_contract') or [])
    primary = dc.get('primary_domain')
    if primary and primary not in out:
        out.insert(0, primary)
    return out


def _reasoning_domains(active: List[str], ledger: Iterable[Dict[str, Any]]) -> List[str]:
    """Refine broad Perdata/Perikatan routing for the element-test layer only.

    The classifier intentionally groups PMH and contract disputes under the
    broad civil_contract retrieval domain. The reasoning contract must not
    therefore force wanprestasi elements onto a PMH pleading.
    """
    corpus=' '.join(_clean(x.get('statement') or x.get('evidence')).lower() for x in (ledger or []) if isinstance(x,dict))
    pmh=any(k in corpus for k in ('perbuatan melawan hukum',' pmh ','pasal 1365'))
    # Do not infer a contract dispute merely because the source contains a bare
    # word 'perjanjian' in argument/citation text. Require an actual breach/contract
    # formulation before activating wanprestasi elements.
    contract=any(k in corpus for k in ('wanprestasi','cidera janji','ingkar janji','berdasarkan perjanjian','perjanjian antara','kontrak antara','kewajiban kontraktual','prestasi yang wajib','kewajiban berdasarkan kontrak'))
    out=[]
    for d in active:
        if d=='civil_contract' and pmh and not contract:
            d='civil_tort'
        if d not in out:
            out.append(d)
    return out


def _candidate_rows(ledger: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Keep pleading/allegation and evidentiary channels separate. A denial, legal
    # argument, heading, metadata block, or pleaded fact is not counter-evidence
    # or supporting evidence merely because it shares keywords with an element.
    from services.case_consistency_guard import classify_source_item
    from services.semantic_admission import route_allowed
    rows=[]
    for idx,item in enumerate(ledger or []):
        if not isinstance(item,dict):
            continue
        statement=_clean(item.get('statement') or item.get('evidence'))
        if not statement:
            continue
        label=str(item.get('label') or 'SOURCE FACT').upper()
        meta=classify_source_item(item)
        cls=str(item.get('display_classification') or item.get('source_classification') or meta.get('classification') or 'SOURCE_FACT').upper()
        # SAL is authoritative for route eligibility. A fact assertion may feed
        # issue/alleged-act reasoning but cannot become proof merely because the
        # legacy classifier calls it SOURCE_FACT/CASE_FACT.
        evidence_eligible=route_allowed(item, 'Evidence Map') and cls in {'ACTUAL_EVIDENTIARY_ITEM','EVIDENCE_ASSERTION','CASE_FACT','SOURCE_FACT'}
        allegation_eligible=route_allowed(item, 'Alleged Act') and (cls in {'PLEADED_FACT','PLEADING_ASSERTION','ALLEGED_ROLE','CASE_FACT','SOURCE_FACT'} or label in {'ALLEGATION','ADMISSION','DENIAL / LIMITATION'})
        counter_argument=(label=='DENIAL / LIMITATION' or cls=='LEGAL_ARGUMENT' or any(cue in statement.lower() for cue in COUNTER_CUES))
        rows.append({
            'index':item.get('source_index',idx),'statement':statement,'label':label,'segment':item.get('segment'),
            'classification':cls,'evidence_eligible':evidence_eligible,'allegation_eligible':allegation_eligible,
            'counter_argument':counter_argument,
        })
    return rows


def _is_legal_argument_or_metadata(statement: str) -> bool:
    low=_clean(statement).lower()
    prefixes=(
        'eksepsi ', 'exceptio ', 'ekseptio ', 'jawaban pertama ', 'dalam eksepsi',
        'dalam pokok perkara', 'petitum', 'kepada yth', 'yang bertanda tangan',
    )
    return low.startswith(prefixes) or any(x in low for x in (
        'gugatan kurang pihak (plurium litis consortium)',
        'obscuur libel', 'exceptio declinatoir', 'eksepsi kompetensi',
    ))


def evidence_proposition_admissibility(statement: str, *, element_id: str = '', element_name: str = '', owner_domain: str = '') -> tuple[bool, str]:
    """Return whether a source proposition can count as evidence for an element.

    This is intentionally stricter than topical relevance.  Questions, procedural
    metadata, accusation labels, and contextual banking facts remain leads unless
    they assert a fact that bears on the proposition the element actually tests.
    """
    text=_clean(statement).lower()
    if not text or _is_legal_argument_or_metadata(text):
        return False, 'LEGAL_ARGUMENT_OR_METADATA'
    if re.match(r'^(?:apakah|kapan|apa\s+fungsi|benarkah|diperlihatkan kepada saudara|pertanyaan)', text):
        return False, 'QUESTION_NOT_PROOF'
    if any(x in text for x in ('surat panggilan tersangka', 'saya mengerti sehubungan dengan adanya surat panggilan', 'berita acara pemeriksaan tersangka')):
        return False, 'PROCEDURAL_CONTEXT_ONLY'

    domain=str(owner_domain or '').lower()
    eid=str(element_id or '').lower()
    name=_clean(element_name).lower()
    anchors={
        'civil_procedure': ('surat kuasa','identitas','relaas','panggilan','domisili','alamat','pengadilan','tanggal gugatan'),
        'land_property': ('sertipikat','sertifikat','surat ukur','buku tanah','warkah','skpt','bpn','ptsl','bidang tanah','pemegang hak'),
        'religious_court': ('beragama islam','agama islam','ahli waris','pewaris','waris','harta peninggalan','pembagian waris'),
        'civil_contract': ('perjanjian','kontrak','wanprestasi','cidera janji','prestasi','somasi','pembayaran','kewajiban kontraktual'),
        'civil_tort': ('perbuatan melawan hukum','kerugian','tindakan','perbuatan','kesalahan','ganti rugi'),
    }
    if domain in anchors and not any(a in text for a in anchors[domain]):
        return False, 'DOMAIN_PROPOSITION_MISMATCH'
    if eid in {'procedural_consequence','pleading_consistency'} and any(a in text for a in ('skpt','sertipikat','sertifikat','bpn')):
        return False, 'PROCEDURAL_ELEMENT_PROPERTY_FACT_MISMATCH'
    if eid in {'valid_contract','obligation','breach','default_notice','loss_nexus'} and domain=='civil_contract' and not any(a in text for a in anchors['civil_contract']):
        return False, 'CONTRACT_PROPOSITION_MISMATCH'

    # Criminal/Tipikor specialized matrices frequently arrive without owner_domain.
    # Infer the proposition from the legal element name, but never from the case label.
    if 'melawan hukum' in name or 'penyalahgunaan kewenangan' in name:
        proof=('menyalahgunakan kewenangan','melampaui kewenangan','melampaui wewenang','bertentangan dengan','tidak sesuai pkpb','tidak sesuai sop','melanggar prosedur','menyimpang dari prosedur','tanpa kewenangan')
        if not any(a in text for a in proof):
            return False, 'UNLAWFUL_ACT_PROPOSITION_NOT_PROVED'
    elif 'mens rea' in name or 'menguntungkan' in name or 'kesengajaan' in name:
        proof=('sengaja','dengan sadar','mengetahui bahwa','bermaksud','bertujuan','menguntungkan','keuntungan pribadi','aliran dana','fee','kickback','gratifikasi','afiliasi','hubungan khusus')
        if not any(a in text for a in proof):
            return False, 'MENS_REA_PROPOSITION_NOT_PROVED'
    elif 'kerugian keuangan' in name or 'kerugian negara' in name or 'kerugian daerah' in name:
        proof=('kerugian keuangan negara','kerugian negara','kerugian daerah','actual loss','hasil audit','laporan hasil perhitungan','outstanding','saldo pokok','nilai kerugian','jumlah kerugian','pemulihan')
        if not any(a in text for a in proof):
            return False, 'STATE_LOSS_PROPOSITION_NOT_PROVED'
    elif 'kausal' in name:
        proof=('menyebabkan','disebabkan','akibat dari','mengakibatkan','karena keputusan','berujung pada','hubungan sebab','kausal')
        if not any(a in text for a in proof):
            return False, 'CAUSATION_PROPOSITION_NOT_PROVED'
    elif 'personal responsibility' in name or 'tanggung jawab personal' in name or 'atribusi' in name:
        proof=('menandatangani','memutus','menyetujui','memberikan persetujuan','kewenangan pemutus','pemutus akhir','bertanggung jawab','melakukan','memerintahkan')
        if not any(a in text for a in proof):
            return False, 'PERSONAL_ATTRIBUTION_NOT_PROVED'
    return True, 'PROPOSITION_COMPATIBLE'


def _proposition_compatible(row: Dict[str, Any], element: Dict[str, Any]) -> bool:
    allowed,_ = evidence_proposition_admissibility(
        row.get('statement',''),
        element_id=str(element.get('id') or ''),
        element_name=str(element.get('description') or element.get('element') or ''),
        owner_domain=str(element.get('_owner_domain') or element.get('owner_domain') or ''),
    )
    return allowed


def _map_row_to_element(row: Dict[str, Any], element: Dict[str, Any]) -> float:
    low=row['statement'].lower()
    keyword_hits=sum(1 for kw in element.get('keywords',[]) if kw in low)
    etoks=_tokens(element.get('description',''))
    rtoks=_tokens(row['statement'])
    lexical=len(etoks & rtoks)
    return keyword_hits*2.0 + lexical*0.45


def _source_quality(row: Dict[str, Any]) -> float:
    """Estimate textual usability only; never truth or evidentiary weight."""
    text=_clean(row.get('statement'))
    if not text:
        return 0.0
    toks=re.findall(r'[A-Za-zÀ-ÿ0-9]+',text)
    if not toks:
        return 0.0
    good=[t for t in toks if len(t)>=3 or t.isdigit()]
    ratio=len(good)/max(1,len(toks))
    weird=len(re.findall(r'(?:\b[a-zA-Z]\b\s*){4,}|[^\w\s.,;:/()\-]{3,}',text))
    q=max(0.0,min(1.0,ratio-(0.12*weird)))
    if re.search(r'\b(?:Pasal|Undang-Undang|Peraturan|Surat Keputusan|Bukti\s+[TP]-?\d+)\b',text,re.I):
        q=max(q,0.68)
    return round(q,2)


def _issue_relevance_score(statement: str, issue: Dict[str, Any]) -> float:
    low=_clean(statement).lower()
    kws=[str(k).lower() for k in (issue.get('keywords') or []) if k]
    keyword_hits=sum(1 for kw in kws if kw in low)
    lexical=len(_tokens(issue.get('issue','')) & _tokens(statement))
    return keyword_hits*2.2 + lexical*0.35


def _dedupe_evidence(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    out=[]; seen=set()
    for row in rows:
        key=(row.get('source_index'), _clean(row.get('statement'))[:120])
        if key in seen:
            continue
        seen.add(key); out.append(row)
        if len(out)>=limit:
            break
    return out


def _issue_evidence_allowed(ev: Dict[str, Any], issue: Dict[str, Any]) -> bool:
    rel=_issue_relevance_score(ev.get('statement',''),issue)
    if issue.get('keywords'):
        return rel >= 2.0
    return rel >= 1.0 or float(ev.get('mapping_score') or 0) >= 5.0



def _mapping_confidence(support: List[Dict[str, Any]], counter: List[Dict[str, Any]]) -> float:
    """Confidence that sources are topically mapped, not confidence that a legal element is satisfied."""
    scores=[float(x.get('mapping_score') or 0) for x in (support+counter)]
    if not scores:
        return 0.0
    top=max(scores)
    breadth=min(4, len(scores))
    return round(min(0.92, 0.28 + min(top,8.0)*0.06 + breadth*0.06), 2)


def _build_issue_tests(active: List[str], matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id={str(x.get('id')):x for x in matrix if isinstance(x,dict)}
    templates=[]; seen_issue_ids=set()
    for d in active:
        for issue in DOMAIN_ISSUE_TEMPLATES.get(d, []):
            iid=str(issue.get('id') or '')
            if not iid or iid in seen_issue_ids:
                continue
            seen_issue_ids.add(iid); templates.append(issue)
    out=[]
    for issue in templates:
        rows=[by_id[eid] for eid in issue.get('element_ids',[]) if eid in by_id]
        if not rows:
            continue
        support=[]; counter=[]
        for row in rows:
            for ev in (row.get('supporting_evidence') or []):
                rel=_issue_relevance_score(ev.get('statement',''),issue)
                if _issue_evidence_allowed(ev,issue):
                    support.append({**ev,'proposition_score':round(rel,2)})
            for ev in (row.get('counter_evidence') or []):
                rel=_issue_relevance_score(ev.get('statement',''),issue)
                if _issue_evidence_allowed(ev,issue):
                    counter.append({**ev,'proposition_score':round(rel,2)})
        support=sorted(_dedupe_evidence(support,8),key=lambda x:(float(x.get('proposition_score') or 0),float(x.get('mapping_score') or 0)),reverse=True)
        counter=sorted(_dedupe_evidence(counter,8),key=lambda x:(float(x.get('proposition_score') or 0),float(x.get('mapping_score') or 0)),reverse=True)
        statuses=[r.get('status') for r in rows]
        if 'DISPUTED' in statuses or (support and counter):
            status='DISPUTED'
        elif support:
            status='PARTIALLY_SUPPORTED'
        elif counter:
            status='COUNTER_EVIDENCE_ONLY'
        else:
            status='NOT_ESTABLISHED'
        out.append({
            'id':issue['id'],
            'issue':issue['issue'],
            'risk_kind':issue.get('risk_kind'),
            'elements':[{
                'id':r.get('id'),
                'description':r.get('element'),
                'status':r.get('status'),
                'mapping_confidence':r.get('mapping_confidence',0.0),
                'supporting_evidence':[ev for ev in (r.get('supporting_evidence') or []) if _issue_evidence_allowed(ev,issue)][:3],
                'counter_evidence':[ev for ev in (r.get('counter_evidence') or []) if _issue_evidence_allowed(ev,issue)][:3],
            } for r in rows],
            'supporting_evidence':support[:5],
            'counter_evidence':counter[:5],
            'status':status,
            'legal_conclusion':'VERIFICATION_REQUIRED',
        })
    return out


def _build_risk_and_mitigation(issue_tests: List[Dict[str, Any]], source_rows: List[Dict[str, Any]], causation: Dict[str, Any], active_domains: List[str] | None=None) -> tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    corpus=' '.join(r.get('statement','').lower() for r in source_rows)
    corrective=[r for r in source_rows if any(c in r.get('statement','').lower() for c in CORRECTIVE_CUES)]
    intent=[r for r in source_rows if any(c in r.get('statement','').lower() for c in INTENT_CUES)]
    impact=[r for r in source_rows if any(c in r.get('statement','').lower() for c in IMPACT_CUES)]
    risks=[]
    for issue in issue_tests:
        s=len(issue.get('supporting_evidence') or [])
        c=len(issue.get('counter_evidence') or [])
        if s and c:
            level='MATERIAL_IF_PROVEN'
        elif s:
            level='POTENTIAL'
        elif c:
            level='LOWERED_BY_COUNTER_EVIDENCE'
        else:
            level='UNASSESSED'
        risks.append({
            'issue_id':issue.get('id'),
            'issue':issue.get('issue'),
            'classification':level,
            'basis':f'{s} supporting mapping; {c} counter mapping; legal satisfaction not claimed.',
            'mapping_confidence':_mapping_confidence((issue.get('supporting_evidence') or [])[:4], (issue.get('counter_evidence') or [])[:4]),
            'verification_required':True,
        })
    mitigation={
        'corrective_action':[{
            'source_index':r.get('index'),'statement':r.get('statement','')[:500]
        } for r in corrective[:6]],
        'intent': 'INTENT_EVIDENCE_PRESENT_NEEDS_TEST' if intent else 'BAD_FAITH_NOT_ESTABLISHED_FROM_CURRENT_LEDGER',
        'impact': 'IMPACT_EVIDENCE_PRESENT_NEEDS_NEXUS_TEST' if impact else 'ACTUAL_IMPACT_NOT_ESTABLISHED_FROM_CURRENT_LEDGER',
        'proportionality':'ASSESS_AFTER_ELEMENT_AND_IMPACT_VERIFICATION',
        'verification_required':True,
    }
    # Strategy is a procedural drafting posture, not a factual/legal conclusion.
    posture=[]
    if any(i.get('status')=='COUNTER_EVIDENCE_ONLY' for i in issue_tests): posture.append('DENY_UNSUPPORTED_ALLEGATION')
    if any(i.get('status')=='DISPUTED' for i in issue_tests): posture.append('DISTINGUISH_AMBIGUOUS_FACT_AND_CAPACITY')
    if corrective: posture.append('SHOW_CORRECTIVE_ACTION')
    intent_domains={'criminal','corruption','anti_corruption','electoral_ethics','criminal_procedure'}
    if mitigation['intent'].startswith('BAD_FAITH_NOT') and intent_domains.intersection(set(active_domains or [])):
        posture.append('MITIGATE_INTENT_ONLY_IF_PRIMARY_EVIDENCE_REMAINS_ABSENT')
    if causation.get('status') in {'NEXUS_NOT_ESTABLISHED','COUNTER_EVIDENCE_PRESENT','DISPUTED'}: posture.append('CHALLENGE_OR_LIMIT_CAUSAL_NEXUS')
    posture.append('REQUEST_PROPORTIONAL_OUTCOME_IF_LIMITED_BREACH_IS_ESTABLISHED')
    pleading={
        'strategy_sequence':posture,
        'output_readiness':'WORKING_DRAFT_ONLY',
        'requires_professional_verification':True,
        'note':'Strategi diturunkan dari mapping sumber/elemen dan tidak mengubah status fakta, tempus, atau applicability.',
    }
    return risks, mitigation, pleading


def build_element_reasoning(*, domain_contract: Dict[str, Any] | None, ledger: Iterable[Dict[str, Any]], existing_matrix: List[Dict[str, Any]] | None=None) -> Dict[str, Any]:
    """Build fail-closed element/evidence reasoning without changing legal-verification plumbing.

    The service does not claim an element is legally satisfied merely because a sentence
    shares vocabulary.  It only creates a traceable mapping so a lawyer can see which
    source items support or counter each element and which elements remain unassessed.
    """
    existing_matrix=list(existing_matrix or [])
    active=_active_domains(domain_contract)
    active_reasoning=_reasoning_domains(active, ledger)

    # Preserve specialized matrices that already exist (e.g. corruption) and only
    # enrich them when possible.  For newly supported domains, use deterministic templates.
    if existing_matrix:
        templates=[]
        for i,row in enumerate(existing_matrix):
            templates.append({
                'id': row.get('id') or f'existing_{i+1}',
                'description': row.get('element') or row.get('description') or f'Element {i+1}',
                'keywords': list(_tokens((row.get('element') or '') + ' ' + (row.get('prosecution_support') or '') + ' ' + (row.get('defense_focus') or ''))),
                '_existing': row,
                '_owner_domain': row.get('owner_domain') or ('criminal' if any(k in (row.get('element') or '').lower() for k in ('melawan hukum','penyalahgunaan','mens rea','menguntungkan','kerugian keuangan','kausal','personal responsibility','tanggung jawab')) else None),
            })
    else:
        templates=[]; seen_template_ids=set()
        # Cross-domain contract: a litigated matter may simultaneously require
        # procedural, property, inheritance/forum, and substantive elements.
        # Merge all PRIMARY/SECONDARY domain templates rather than allowing the
        # first detected domain to erase the others.
        for domain in active_reasoning:
            issue_by_element={}
            for issue_tpl in DOMAIN_ISSUE_TEMPLATES.get(domain, []):
                for eid in issue_tpl.get('element_ids', []):
                    issue_by_element[str(eid)] = issue_tpl
            for template in DOMAIN_ELEMENT_TEMPLATES.get(domain, []):
                tid=str(template.get('id') or '')
                if not tid or tid in seen_template_ids:
                    continue
                seen_template_ids.add(tid)
                owner_issue=issue_by_element.get(tid) or {}
                templates.append({**template, '_owner_domain':domain, '_owner_issue_id':owner_issue.get('id'), '_owner_issue':owner_issue.get('issue')})

    if not templates:
        return {
            'element_matrix': existing_matrix,
            'evidence_to_element_mapping': [],
            'element_test_summary': {'status':'NOT_AVAILABLE_FOR_DOMAIN','assessed':0,'total':len(existing_matrix),'percentage':0},
            'causation_analysis': {'status':'NOT_ASSESSED','reason':'Belum tersedia template element/nexus untuk domain ini.'},
            'issue_element_tests':[], 'risk_assessment':[], 'mitigation_strategy':{}, 'pleading_strategy':{}
        }

    source_rows=_candidate_rows(ledger)
    matrix=[]; mapping=[]
    for template in templates:
        support=[]; counter=[]; alleged=[]; counter_arguments=[]
        scored=[]
        for row in source_rows:
            score=_map_row_to_element(row,template)
            quality=_source_quality(row)
            if row.get('allegation_eligible') and score >= 1.8:
                target = counter_arguments if row.get('counter_argument') else alleged
                target.append({
                    'source_index':row['index'],'segment':row.get('segment'),'label':row.get('label'),
                    'statement':row['statement'][:700],'mapping_score':round(score,2),
                    'source_classification':row.get('classification'),
                })
            # Evidence mapping is stricter than allegation mapping. Pleadings,
            # denials and legal arguments stay outside Evidence/Counter-Evidence.
            if not row.get('evidence_eligible'):
                continue
            if score < 1.8 or quality < 0.50:
                continue
            if not _proposition_compatible(row, template):
                continue
            scored.append((score,quality,row))
        scored.sort(key=lambda x:(-x[0],-x[1],x[2]['index']))
        for score,quality,row in scored[:8]:
            evidence={
                'source_index':row['index'],
                'segment':row.get('segment'),
                'label':row.get('label'),
                'statement':row['statement'][:700],
                'mapping_score':round(score,2),
                'source_quality':quality,
            }
            low=row['statement'].lower()
            is_counter=(row.get('label') in {'DENIAL / LIMITATION'} or any(cue in low for cue in COUNTER_CUES))
            (counter if is_counter else support).append(evidence)
            mapping.append({
                'element_id':template['id'],
                'element':template['description'],
                'source_index':row['index'],
                'role':'COUNTER' if is_counter else 'SUPPORT',
                'statement':row['statement'][:500],
                'score':round(score,2),
                'source_quality':quality,
            })

        if support and counter:
            status='DISPUTED'
        elif support:
            status='PARTIALLY_SUPPORTED'
        elif counter:
            status='COUNTER_EVIDENCE_ONLY'
        else:
            status='NOT_ESTABLISHED'

        existing=template.get('_existing') or {}
        matrix.append({
            'id':template['id'],
            'element':template['description'],
            'owner_domain':template.get('_owner_domain'),
            'owner_issue_id':template.get('_owner_issue_id'),
            'owner_issue':template.get('_owner_issue'),
            'supporting_evidence':support[:4],
            'counter_evidence':counter[:4],
            'status':status,
            'prosecution_support':existing.get('prosecution_support'),
            'defense_focus':existing.get('defense_focus'),
            'prior_status':existing.get('status'),
            'mapping_confidence':_mapping_confidence(support[:4],counter[:4]),
            'alleged_act': (sorted(alleged,key=lambda x:float(x.get('mapping_score') or 0),reverse=True)[0]['statement'] if alleged else ''),
            'alleged_act_sources': sorted(alleged,key=lambda x:float(x.get('mapping_score') or 0),reverse=True)[:4],
            'counter_arguments': sorted(counter_arguments,key=lambda x:float(x.get('mapping_score') or 0),reverse=True)[:4],
            'verification_required':True,
        })

    assessed=sum(1 for row in matrix if row['supporting_evidence'] or row['counter_evidence'])
    percentage=round(100*assessed/max(1,len(matrix)))

    nexus_rows=[row for row in matrix if row['id'] in {'nexus_impact','loss_nexus','impact_nexus'} or 'kausal' in row['element'].lower() or 'hubungan' in row['element'].lower() and 'akibat' in row['element'].lower()]
    if nexus_rows:
        nx=nexus_rows[0]
        if nx['supporting_evidence'] and nx['counter_evidence']:
            nstatus='DISPUTED'
        elif nx['supporting_evidence']:
            nstatus='PARTIAL_NEXUS_IDENTIFIED'
        elif nx['counter_evidence']:
            nstatus='COUNTER_EVIDENCE_PRESENT'
        else:
            nstatus='NEXUS_NOT_ESTABLISHED'
        causation={
            'status':nstatus,
            'element_id':nx['id'],
            'supporting_evidence':nx['supporting_evidence'][:3],
            'counter_evidence':nx['counter_evidence'][:3],
            'reason':'Hubungan sebab/akibat atau impact hanya dapat dinaikkan setelah fakta material, bukti primer, dan nexus normatif diverifikasi.'
        }
    else:
        causation={'status':'NOT_ASSESSED','reason':'Domain ini belum memiliki elemen nexus/impact terstruktur.'}

    issue_tests=_build_issue_tests(active_reasoning,matrix)
    risk_assessment, mitigation_strategy, pleading_strategy=_build_risk_and_mitigation(issue_tests,source_rows,causation,active_reasoning)

    return {
        'element_matrix':matrix,
        'evidence_to_element_mapping':mapping[:40],
        'element_test_summary':{
            'status':'PARTIAL' if assessed < len(matrix) else 'MAPPED_NOT_LEGALLY_PROVEN',
            'assessed':assessed,
            'total':len(matrix),
            'percentage':percentage,
            'legal_satisfaction_claimed':False,
        },
        'issue_element_tests':issue_tests,
        'causation_analysis':causation,
        'risk_assessment':risk_assessment,
        'mitigation_strategy':mitigation_strategy,
        'pleading_strategy':pleading_strategy,
    }
