"""Authoritative case-posture/domain classifier for LexiCore.

The classifier is deterministic and acts as a contract for downstream legal
retrieval.  AI may enrich reasoning but may not silently replace the primary
posture/domain without explicit evidence and a visible conflict flag.
"""
from __future__ import annotations
import re
from typing import Dict, List

DOMAIN_LABELS={
    'general_legal':'General Legal / Domain Belum Ditentukan',
    'corruption':'Tindak Pidana Korupsi / Pidana Khusus',
    'financial_services':'Perbankan / BPR / Jasa Keuangan',
    'criminal':'Pidana / Acara Pidana',
    'regional_government':'Pemerintahan Daerah / BUMD',
    'civil_contract':'Perdata / Perikatan',
    'civil_procedure':'Hukum Acara Perdata',
    'land_property':'Pertanahan / Properti',
    'religious_court':'Peradilan Agama / Kompetensi Absolut',
    'inheritance':'Hukum Waris / Kewarisan',
    'employment':'Ketenagakerjaan / Hubungan Industrial',
    'corporate':'Perseroan / Korporasi',
    'consumer':'Perlindungan Konsumen',
    'data_privacy':'Pelindungan Data Pribadi / ITE',
    'bankruptcy':'Kepailitan / PKPU',
    'arbitration':'Arbitrase / ADR',
    'administrative':'Hukum Administrasi / PTUN',
    'public_information':'Keterbukaan Informasi Publik',
    'investment':'Penanaman Modal / Investasi',
    'electoral_ethics':'Pemilu / Pilkada / Etik Penyelenggara',
}

NEGATION_PATTERNS=[r'tidak\s+ada',r'tanpa',r'bukan',r'tidak\s+terdapat',r'belum\s+ada']

def _present(text:str, term:str)->bool:
    low=text.lower(); term=term.lower()
    for m in re.finditer(re.escape(term),low):
        prefix=low[max(0,m.start()-45):m.start()]
        if any(re.search(p+r'\s+(?:\w+\s+){0,3}$',prefix) for p in NEGATION_PATTERNS):
            continue
        return True
    return False

def _count(text:str, terms)->int:
    return sum(1 for t in terms if _present(text,t))

def classify_case(text:str)->Dict:
    low=(text or '').lower()
    # Strong posture signals are evaluated before transaction words.
    pidana=_count(low,['berita acara pemeriksaan tersangka','tersangka','penyidikan','penuntut umum','jaksa penyidik','surat penetapan tersangka','dakwaan','tindak pidana'])
    tipikor=_count(low,['tindak pidana korupsi','tipikor','pemberantasan tindak pidana korupsi','kerugian keuangan negara','kerugian keuangan daerah','penyalahgunaan kewenangan','menguntungkan diri sendiri','menguntungkan orang lain'])
    bank=_count(low,['bpr','bank perekonomian rakyat','bank perkreditan rakyat','fasilitas kredit','pemberian kredit','komite kredit','analisa 5c','slik','ojk','agunan'])
    public=_count(low,['perumda','pemerintah kota','pemerintah daerah','bumd','kekayaan daerah','pendapatan asli daerah','keuangan daerah'])
    internal=_count(low,['direktur utama','direksi','penyimpangan prosedur','menyimpangi','tidak dilakukan survei','fraud internal','orang dalam','kepatuhan','spi','pemutus kredit'])
    civil=_count(low,['wanprestasi','somasi','cidera janji','ingkar janji','perjanjian','kontrak','utang piutang','gugatan perdata','perbuatan melawan hukum','pmh','ganti rugi','jatuh tempo','tidak membayar'])
    land=_count(low,['sertipikat','sertifikat hak milik','sertifikat tanah','sertifikat sawah','sawah bersertifikat','tanah bersertifikat','skpt','kantor pertanahan','uupa','hak atas tanah','pendaftaran tanah','bpn'])
    civilproc=_count(low,['penggugat','tergugat','eksepsi','obscuur libel','plurium litis consortium','posita','petitum','pn.','pdt.g','replik','duplik','jawaban tergugat','gugatan','permohonan provisi'])
    religious=_count(low,['pengadilan agama','peradilan agama','pasal 49','waris islam','ekonomi syariah'])
    inheritance=_count(low,['pembagian waris','warisan','ahli waris','ahliwaris','pewaris','harta waris','bagian waris','legitime portie','legitieme portie','ibu tiri','istri kedua','isteri kedua'])
    # Domain and posture are separate contracts.  Inheritance vocabulary proves
    # the subject matter, not that a lawsuit is already pending.  Escalate to a
    # waris-litigation posture only when the narrative also contains an
    # adversarial/remedial signal.  Formal pleading vocabulary is handled by
    # the civil-procedure branch below and outranks this topical signal.
    inheritance_litigation_signal=_count(low,[
        'gugatan waris','sengketa waris','perkara waris','mengajukan gugatan',
        'kuasa hukum','langkah hukum','dikuasainya','direndam','dirobek',
        'menguasai warisan','menguasai harta waris','merebut warisan'
    ])
    inheritance_specific=_count(low,[
        'legitime portie','legitieme portie','ibu tiri','istri kedua','isteri kedua',
        'anak kandung','waris islam','kompilasi hukum islam','khi'
    ])
    # Material criminal-act signals are kept separate from criminal-procedure
    # posture. They may create a secondary criminal issue (e.g. destruction of
    # a certificate inside an inheritance dispute) without falsely converting
    # the whole matter into a criminal proceeding.
    criminal_damage=_count(low,[
        'merusak','merobek','dirobek','merendam','direndam','menghancurkan',
        'membuat tidak dapat dipakai','perusakan barang','perusakan sertifikat',
        'merobek sertifikat','merendam sertifikat'
    ])
    forum_dispute=_count(low,['kompetensi absolut','kewenangan absolut','eksepsi declinatoir','exceptio declinatoir','exsepsio decklinatoir','declinatoir'])
    # Inheritance alone does not prove Religious Court jurisdiction.  It only
    # raises a forum screen when the pleading also disputes absolute
    # competence; explicit Pengadilan Agama/Pasal 49 remains the strongest
    # trigger.
    if inheritance and forum_dispute:
        religious += 1
    employment=_count(low,['phk','pemutusan hubungan kerja','pkwt','pkwtt','pekerja','buruh','pengusaha','pesangon','hubungan kerja','perjanjian kerja','upah','hubungan industrial','bipartit','mediasi hubungan industrial'])
    corporate=_count(low,['perseroan terbatas','rups','komisaris','pemegang saham','business judgment rule'])
    privacy=_count(low,['data pribadi','pelindungan data pribadi','uu pdp','transaksi elektronik','informasi elektronik'])
    bankruptcy=_count(low,['kepailitan','pkpu','pailit','dua kreditur'])
    arbitration=_count(low,['arbitrase','bani','klausul arbitrase'])
    consumer=_count(low,['perlindungan konsumen','konsumen','pelaku usaha','klausula baku','bpsk'])
    administrative=_count(low,['ptun','peradilan tata usaha negara','keputusan tata usaha negara','keputusan tun','pejabat tata usaha negara','upaya administratif','keberatan administratif','banding administratif','aaupb','asas-asas umum pemerintahan'])
    public_information=_count(low,['keterbukaan informasi publik','informasi publik','badan publik','komisi informasi','sengketa informasi'])
    investment=_count(low,['penanaman modal','investasi asing','investasi dalam negeri','bkpm','perizinan berusaha','investor'])
    electoral=_count(low,['dewan kehormatan penyelenggara pemilu','dkpp','pelanggaran kode etik','kode etik penyelenggara pemilu','pokok aduan','pengadu','teradu','komisi pemilihan umum','kpu','bawaslu','pemilihan umum','pemilu','pemilihan gubernur','pemilihan bupati','pemilihan walikota','pilkada','peraturan dkpp'])
    electoral_strong=_count(low,['dewan kehormatan penyelenggara pemilu','dkpp','pelanggaran kode etik','kode etik penyelenggara pemilu','pokok aduan','pengadu','teradu'])
    direct_criminal=_count(low,['tersangka','penyidikan','penuntut umum','jaksa penyidik','surat penetapan tersangka','dakwaan pidana','penahanan','penangkapan'])
    criminal_proceeding=bool(direct_criminal >= 1 and pidana >= 2)

    # Mandatory Tipikor priority screen: Bank/credit/public-finance signals force
    # screening, but never by themselves prove corruption.
    priority_trigger=bool(bank or public or _present(low,'keuangan negara') or _present(low,'keuangan daerah'))
    # A legal citation to a criminal/corruption statute is not enough to turn a
    # non-criminal proceeding into a criminal case.  Require independent
    # proceeding anchors.  This is the cross-domain arbitration invariant.
    corruption_predicate = criminal_proceeding and (tipikor>=1 or (bank>=2 and (public>=1 or internal>=2)))

    scores={
        'corruption': (35*tipikor + 16*pidana + 10*bank + 10*public + 8*internal) if corruption_predicate else 0,
        'financial_services': 24*bank + 5*internal,
        'criminal': 22*pidana + 8*tipikor + 9*criminal_damage,
        'regional_government': 23*public + 6*bank,
        'civil_contract': 18*civil,
        'land_property': 25*land,
        'civil_procedure': 24*civilproc,
        'religious_court': 27*religious,
        'inheritance': 28*inheritance,
        'employment': 25*employment,
        'corporate': 22*corporate,
        'data_privacy': 25*privacy,
        'bankruptcy': 25*bankruptcy,
        'arbitration': 25*arbitration,
        'consumer': 25*consumer,
        'administrative': 27*administrative,
        'public_information': 25*public_information,
        'investment': 24*investment,
        'electoral_ethics': 30*electoral_strong + 12*electoral,
    }

    electoral_proceeding_anchor=bool(re.search(r'\b\d+[A-Za-z0-9/-]*-PKE-DKPP\b|\bP/L-DKPP\b', text or '', re.I)) or _present(low,'jawaban atas laporan dugaan pelanggaran kode etik') or _present(low,'dewan kehormatan penyelenggara pemilu')
    electoral_posture = electoral_proceeding_anchor or electoral_strong >= 2 or _present(low,'dkpp')

    def _dedupe(items):
        out=[]
        for item in items:
            if item and item not in out:
                out.append(item)
        return out

    def _substantive_primary(candidates):
        """Choose merits domain only; procedure/forum must not erase merits."""
        visible=[d for d in candidates if scores.get(d,0)>0]
        return max(visible, key=lambda d:scores.get(d,0)) if visible else None

    def _procedure_secondary(secondary):
        # A pleading signal is a lane, not the merits. Preserve it whenever the
        # primary domain is substantive.
        if civilproc and 'civil_procedure' not in secondary:
            secondary.append('civil_procedure')
        return _dedupe(secondary)
    # Proceeding-type anchors outrank topical vocabulary.  A DKPP/KPU ethics
    # proceeding is not criminal merely because a cited statute or OCR fragment
    # contains the word 'pidana'.  Only direct criminal-procedure anchors may
    # create a mixed criminal secondary domain.
    if electoral_posture:
        posture='ELECTORAL_ETHICS_PROCEEDING'
        primary='electoral_ethics'
        secondary=[]
        if criminal_proceeding:
            secondary.append('criminal')
        if administrative:
            secondary.append('administrative')
        supporting=[]
    elif corruption_predicate:
        posture='PIDANA_KHUSUS_PENYIDIKAN'
        primary='corruption'
        # Civil contract remains a supporting relationship even though a credit
        # agreement exists; it may not displace the criminal posture.
        scores['civil_contract']=min(scores['civil_contract'],24)
        secondary=[d for d in ('financial_services','criminal','regional_government') if scores.get(d,0)>0]
        supporting=['civil_contract'] if civil or bank else []
    elif administrative:
        posture='TATA_USAHA_NEGARA'
        primary='administrative'; secondary=[]; supporting=[]
        if public_information: secondary.append('public_information')
        if investment: secondary.append('investment')
    elif public_information:
        posture='SENGKETA_INFORMASI_PUBLIK'; primary='public_information'; secondary=['administrative'] if administrative else []; supporting=[]
    elif investment:
        posture='REGULATORY_INVESTMENT'; primary='investment'; secondary=['corporate'] if corporate else []; supporting=['civil_contract'] if civil else []
    elif civilproc:
        # Procedural vocabulary determines posture, never the merits. Forum
        # vocabulary (religious_court) is also kept separate when a substantive
        # domain such as inheritance is visible.
        posture='PERDATA_LITIGASI'
        substantive_candidates=(
            'inheritance','employment','civil_contract','land_property',
            'corporate','consumer','bankruptcy','arbitration','data_privacy'
        )
        primary=_substantive_primary(substantive_candidates)
        if primary:
            secondary=['civil_procedure']
            secondary += [d for d in substantive_candidates if d!=primary and scores.get(d,0)>0]
            if religious:
                secondary.append('religious_court')
            if criminal_damage:
                secondary.append('criminal')
            secondary=_dedupe(secondary)
        elif religious:
            primary='religious_court'; secondary=['civil_procedure']
        else:
            primary='civil_procedure'; secondary=[]
        supporting=[]
    elif inheritance and inheritance_specific:
        posture='WARIS_LITIGASI' if inheritance_litigation_signal else 'GENERAL_LEGAL'
        primary='inheritance'
        secondary=[d for d in ('land_property','religious_court') if scores.get(d,0)>0]
        if criminal_damage:
            secondary.append('criminal')
        secondary=_procedure_secondary(secondary)
        supporting=['civil_contract'] if civil else []
    elif inheritance:
        # Generic inheritance vocabulary alone is insufficient for a confident
        # specialist route. Preserve the legacy fail-safe GENERAL_LEGAL contract
        # until a specific doctrine/party relationship or procedural posture is
        # visible in the text.
        posture='GENERAL_LEGAL'
        primary='general_legal'
        secondary=[]
        supporting=[]
    elif land or religious:
        posture='PERDATA_LITIGASI'
        # Prefer a merits domain over a forum label. Religious-court remains a
        # forum lane unless it is the only reliable signal.
        primary=_substantive_primary(('land_property','civil_contract'))
        if primary:
            secondary=[]
            if religious:
                secondary.append('religious_court')
        else:
            primary='religious_court'
            secondary=[]
        secondary=_procedure_secondary(secondary)
        supporting=[]
    elif employment:
        posture='HUBUNGAN_INDUSTRIAL'
        primary='employment'; secondary=['civil_procedure'] if civilproc else []; supporting=[]
    elif bankruptcy:
        posture='NIAGA_KEPAILITAN'; primary='bankruptcy'; secondary=['civil_contract'] if civil else []; supporting=[]
    elif arbitration:
        posture='ARBITRASE_ADR'; primary='arbitration'; secondary=['civil_contract'] if civil else []; supporting=[]
    elif bank:
        posture='REGULATORY_FINANCIAL_SERVICES'; primary='financial_services'; secondary=['civil_contract'] if civil else []; supporting=[]
    elif privacy:
        posture='DATA_PRIVACY_DIGITAL'; primary='data_privacy'; secondary=[]; supporting=[]
    elif consumer:
        posture='PERLINDUNGAN_KONSUMEN'; primary='consumer'; secondary=['civil_contract'] if civil else []; supporting=[]
    elif corporate:
        posture='KORPORASI'; primary='corporate'; secondary=['civil_contract'] if civil else []; supporting=[]
    else:
        posture='PERDATA_SENGKETA_KONTRAK' if civil else 'GENERAL_LEGAL'
        if civil:
            primary='civil_contract'
        else:
            best=max(scores,key=scores.get)
            primary=best if scores.get(best,0)>0 else 'general_legal'
        secondary=[]; supporting=[]

    # Final cross-domain invariants. A material criminal act may coexist with a
    # civil/inheritance matter without changing posture; civil-procedure is
    # preserved whenever explicit pleading vocabulary exists.
    secondary=_dedupe(secondary)
    if primary not in ('criminal','corruption') and criminal_damage and primary not in ('general_legal','civil_procedure'):
        secondary=_dedupe(secondary + ['criminal'])
    if civilproc and primary != 'civil_procedure' and posture in ('PERDATA_LITIGASI','WARIS_LITIGASI','HUBUNGAN_INDUSTRIAL','NIAGA_KEPAILITAN','ARBITRASE_ADR'):
        secondary=_procedure_secondary(secondary)
    secondary=[d for d in secondary if d!=primary]

    def item(d,role):
        raw=scores.get(d,0); conf=99 if raw>=80 else max(20,min(95,30+raw))
        return {'id':d,'label':DOMAIN_LABELS.get(d,d),'role':role,'score':raw,'confidence':conf}
    domains=[item(primary,'PRIMARY')]
    domains += [item(d,'SECONDARY') for d in secondary if d!=primary]
    domains += [item(d,'SUPPORTING_ONLY') for d in supporting if d!=primary and d not in secondary]
    formal_context=_legal_area_and_user_position(text or '', posture, primary)
    return {
        'classifier_version':'1.5.8',
        'posture':posture,'primary_domain':primary,'domains':domains,
        **formal_context,
        'priority_tipikor_screen':{
            'required':priority_trigger,'corruption_predicate_detected':corruption_predicate,
            'note':'Screening prioritas Tipikor bukan kesimpulan terpenuhinya unsur. Melawan hukum/penyalahgunaan kewenangan, mens rea, kerugian aktual, kausalitas dan pertanggungjawaban individual tetap harus dibuktikan.'
        },
        'domain_contract':[d['id'] for d in domains if d['role'] in ('PRIMARY','SECONDARY')],
        'supporting_only':[d['id'] for d in domains if d['role']=='SUPPORTING_ONLY'],
        'boundary_guard':{
            'proceeding_anchor':'ELECTORAL_ETHICS' if electoral_posture else ('CRIMINAL' if criminal_proceeding else 'UNRESOLVED'),
            'electoral_anchor_score':electoral_strong,
            'electoral_proceeding_anchor':electoral_proceeding_anchor,
            'direct_criminal_anchor_score':direct_criminal,
            'rule':'proceeding-type anchors outrank generic topic/article vocabulary',
        },
        'arbitration_trace': {
            'civil_procedure_signal': bool(civilproc),
            'criminal_damage_signal': bool(criminal_damage),
            'inheritance_signal': bool(inheritance),
            'rule': 'merits domain is primary; procedure/forum/material secondary issues are preserved independently',
        },
        'forum_screen': {
            'inheritance_detected': bool(inheritance),
            'absolute_competence_disputed': bool(forum_dispute),
            'religious_court_explicit': bool(_count(low,['pengadilan agama','peradilan agama','pasal 49'])),
            'note': 'Isu waris tidak otomatis menentukan forum. Kompetensi absolut wajib diuji dari status para pihak, objek sengketa, petitum, dan dasar kewenangan yang benar-benar berlaku.'
        },
    }


def _legal_area_and_user_position(text: str, posture: str, primary: str) -> Dict:
    """Derive additive legal-area and document-side position contracts.

    This is deliberately fail-closed: it classifies the procedural side expressed
    by the analysed document, not the ultimate merits and not a person identity.
    Existing posture/domain outputs remain authoritative and unchanged.
    """
    low=(text or '').lower()

    if posture in ('PIDANA_KHUSUS_PENYIDIKAN',) or primary in ('criminal','corruption'):
        area='PIDANA'
    elif posture in ('TATA_USAHA_NEGARA','SENGKETA_INFORMASI_PUBLIK') or primary in ('administrative','public_information'):
        area='TUN'
    elif primary == 'religious_court':
        area='AGAMA'
    elif posture == 'ELECTORAL_ETHICS_PROCEEDING' or primary == 'electoral_ethics':
        area='ETIK_ADMINISTRATIF'
    elif primary in ('civil_contract','civil_procedure','land_property','inheritance','employment','corporate','consumer','bankruptcy','arbitration'):
        area='PERDATA'
    elif primary in ('financial_services','investment','data_privacy','regional_government'):
        area='REGULATORI'
    else:
        area='UMUM'

    # Strong document-role anchors.  A response/defence marker is evaluated
    # before generic party-name mentions because pleadings often quote both sides.
    role='BELUM_TERIDENTIFIKASI'; confidence='LOW'; basis='No decisive document-side marker.'
    response=bool(re.search(r'\b(?:jawaban|tanggapan|sanggahan|pembelaan|eksepsi|nota keberatan)\b', low))
    claim=bool(re.search(r'\b(?:gugatan|pengaduan|laporan|permohonan)\b', low))

    ordered=[]
    if response:
        ordered.extend([
            ('TERADU', r'\bteradu\b'), ('TERGUGAT', r'\btergugat\b'),
            ('TERMOHON', r'\btermohon\b'), ('TERDAKWA', r'\bterdakwa\b'),
            ('TERSANGKA', r'\btersangka\b'),
        ])
    if claim:
        ordered.extend([
            ('PENGGUGAT', r'\bpenggugat\b'), ('PENGADU', r'\bpengadu\b'),
            ('PELAPOR', r'\bpelapor\b'), ('PEMOHON', r'\bpemohon\b'),
            ('KORBAN', r'\bkorban\b'),
        ])
    # If structure is not decisive, accept only highly explicit self-position
    # formulations; bare party mentions remain insufficient.
    for candidate, pattern in ordered:
        if re.search(pattern, low):
            role=candidate; confidence='HIGH'; basis='Document structure + explicit party-side marker.'
            break
    if role == 'BELUM_TERIDENTIFIKASI':
        explicit=[
            ('TERDAKWA', r'\b(?:saya|kami)\s+(?:sebagai\s+)?terdakwa\b'),
            ('TERSANGKA', r'\b(?:saya|kami)\s+(?:sebagai\s+)?tersangka\b'),
            ('PENGGUGAT', r'\b(?:saya|kami)\s+(?:sebagai\s+)?penggugat\b'),
            ('TERGUGAT', r'\b(?:saya|kami)\s+(?:sebagai\s+)?tergugat\b'),
            ('PEMOHON', r'\b(?:saya|kami)\s+(?:sebagai\s+)?pemohon\b'),
            ('TERMOHON', r'\b(?:saya|kami)\s+(?:sebagai\s+)?termohon\b'),
            ('PENGADU', r'\b(?:saya|kami)\s+(?:sebagai\s+)?pengadu\b'),
            ('TERADU', r'\b(?:saya|kami)\s+(?:sebagai\s+)?teradu\b'),
            ('KORBAN', r'\b(?:saya|kami)\s+(?:sebagai\s+)?korban\b'),
        ]
        for candidate, pattern in explicit:
            if re.search(pattern, low):
                role=candidate; confidence='MEDIUM'; basis='Explicit self-position marker.'
                break

    return {
        'ranah_hukum': area,
        'posisi_pengguna': role,
        'posisi_pengguna_confidence': confidence,
        'posisi_pengguna_basis': basis,
    }

FEW_SHOT_BOUNDARY = """
BATAS DEMARKASI DOMAIN — WAJIB DIPATUHI
Contoh A — TIPIKOR BPR:
Direktur Utama Perumda BPR diperiksa sebagai tersangka atas fasilitas kredit Rp255 juta; terdapat isu survei, 5C, penyimpangan prosedur/kewenangan dan dugaan kerugian keuangan daerah. Walaupun ada Perjanjian Kredit, klasifikasi: PRIMARY Tipikor/Pidana Khusus; SECONDARY Perbankan/BPR, BUMD, Acara Pidana; Perdata/Perikatan hanya SUPPORTING.

Contoh B — WANPRESTASI MURNI:
Bank/kreditur menagih debitur yang menunggak berdasarkan perjanjian kredit; tidak ada penyidikan, fraud internal, manipulasi proses kredit, penyalahgunaan kewenangan atau kerugian keuangan negara/daerah. Klasifikasi: PRIMARY Perdata/Perikatan/Wanprestasi; Perbankan SECONDARY; Tipikor bukan primary.
""".strip()
