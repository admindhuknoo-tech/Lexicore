"""Authoritative case-posture/domain classifier for LexiCore.

The classifier is deterministic and acts as a contract for downstream legal
retrieval.  AI may enrich reasoning but may not silently replace the primary
posture/domain without explicit evidence and a visible conflict flag.
"""
from __future__ import annotations
import re
from typing import Dict, List

DOMAIN_LABELS={
    'corruption':'Tindak Pidana Korupsi / Pidana Khusus',
    'financial_services':'Perbankan / BPR / Jasa Keuangan',
    'criminal':'Pidana / Acara Pidana',
    'regional_government':'Pemerintahan Daerah / BUMD',
    'civil_contract':'Perdata / Perikatan',
    'civil_procedure':'Hukum Acara Perdata',
    'land_property':'Pertanahan / Properti',
    'religious_court':'Peradilan Agama / Kompetensi Absolut',
    'employment':'Ketenagakerjaan / Hubungan Industrial',
    'corporate':'Perseroan / Korporasi',
    'consumer':'Perlindungan Konsumen',
    'data_privacy':'Pelindungan Data Pribadi / ITE',
    'bankruptcy':'Kepailitan / PKPU',
    'arbitration':'Arbitrase / ADR',
    'administrative':'Hukum Administrasi / PTUN',
    'public_information':'Keterbukaan Informasi Publik',
    'investment':'Penanaman Modal / Investasi',
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
    tipikor=_count(low,['tindak pidana korupsi','tipikor','pemberantasan tindak pidana korupsi','kerugian keuangan negara','kerugian keuangan daerah','penyalahgunaan kewenangan','menguntungkan diri sendiri','menguntungkan orang lain','pasal 2','pasal 3'])
    bank=_count(low,['bpr','bank perekonomian rakyat','bank perkreditan rakyat','fasilitas kredit','pemberian kredit','komite kredit','analisa 5c','slik','ojk','agunan'])
    public=_count(low,['perumda','pemerintah kota','pemerintah daerah','bumd','kekayaan daerah','pendapatan asli daerah','keuangan daerah'])
    internal=_count(low,['direktur utama','direksi','penyimpangan prosedur','menyimpangi','tidak dilakukan survei','fraud internal','orang dalam','kepatuhan','spi','pemutus kredit'])
    civil=_count(low,['wanprestasi','somasi','cidera janji','perjanjian','utang piutang','gugatan perdata','perbuatan melawan hukum'])
    land=_count(low,['sertipikat','sertifikat hak milik','skpt','kantor pertanahan','uupa','hak atas tanah','pendaftaran tanah','bpn'])
    civilproc=_count(low,['penggugat','tergugat','eksepsi','obscuur libel','plurium litis consortium','posita','petitum','pn.','pdt.g'])
    religious=_count(low,['pengadilan agama','peradilan agama','pasal 49','waris islam','ekonomi syariah'])
    inheritance=_count(low,['pembagian waris','warisan','ahli waris','ahliwaris','pewaris','harta waris','bagian waris'])
    forum_dispute=_count(low,['kompetensi absolut','kewenangan absolut','eksepsi declinatoir','exceptio declinatoir','exsepsio decklinatoir','declinatoir'])
    # Inheritance alone does not prove Religious Court jurisdiction.  It only
    # raises a forum screen when the pleading also disputes absolute
    # competence; explicit Pengadilan Agama/Pasal 49 remains the strongest
    # trigger.
    if inheritance and forum_dispute:
        religious += 1
    employment=_count(low,['phk','pkwt','pekerja','buruh','pesangon','hubungan industrial'])
    corporate=_count(low,['perseroan terbatas','rups','komisaris','pemegang saham','business judgment rule'])
    privacy=_count(low,['data pribadi','pelindungan data pribadi','uu pdp','transaksi elektronik','informasi elektronik'])
    bankruptcy=_count(low,['kepailitan','pkpu','pailit','dua kreditur'])
    arbitration=_count(low,['arbitrase','bani','klausul arbitrase'])
    consumer=_count(low,['perlindungan konsumen','konsumen','pelaku usaha','klausula baku','bpsk'])
    administrative=_count(low,['ptun','peradilan tata usaha negara','keputusan tata usaha negara','keputusan tun','pejabat tata usaha negara','upaya administratif','keberatan administratif','banding administratif','aaupb','asas-asas umum pemerintahan'])
    public_information=_count(low,['keterbukaan informasi publik','informasi publik','badan publik','komisi informasi','sengketa informasi'])
    investment=_count(low,['penanaman modal','investasi asing','investasi dalam negeri','bkpm','perizinan berusaha','investor'])

    # Mandatory Tipikor priority screen: Bank/credit/public-finance signals force
    # screening, but never by themselves prove corruption.
    priority_trigger=bool(bank or public or _present(low,'keuangan negara') or _present(low,'keuangan daerah'))
    corruption_predicate = pidana>=2 and (tipikor>=1 or (bank>=2 and (public>=1 or internal>=2)))

    scores={
        'corruption': (35*tipikor + 16*pidana + 10*bank + 10*public + 8*internal) if corruption_predicate else 0,
        'financial_services': 24*bank + 5*internal,
        'criminal': 22*pidana + 8*tipikor,
        'regional_government': 23*public + 6*bank,
        'civil_contract': 18*civil,
        'land_property': 25*land,
        'civil_procedure': 24*civilproc,
        'religious_court': 27*religious,
        'employment': 25*employment,
        'corporate': 22*corporate,
        'data_privacy': 25*privacy,
        'bankruptcy': 25*bankruptcy,
        'arbitration': 25*arbitration,
        'consumer': 25*consumer,
        'administrative': 27*administrative,
        'public_information': 25*public_information,
        'investment': 24*investment,
    }

    if corruption_predicate:
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
    elif civilproc or land or religious:
        posture='PERDATA_LITIGASI'
        primary=max(('civil_procedure','land_property','religious_court','civil_contract'), key=lambda d:scores.get(d,0))
        secondary=[d for d in ('land_property','civil_procedure','religious_court','civil_contract') if d!=primary and scores.get(d,0)>0]
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
        primary='civil_contract' if civil else max(scores,key=scores.get)
        secondary=[]; supporting=[]

    def item(d,role):
        raw=scores.get(d,0); conf=99 if raw>=80 else max(20,min(95,30+raw))
        return {'id':d,'label':DOMAIN_LABELS.get(d,d),'role':role,'score':raw,'confidence':conf}
    domains=[item(primary,'PRIMARY')]
    domains += [item(d,'SECONDARY') for d in secondary if d!=primary]
    domains += [item(d,'SUPPORTING_ONLY') for d in supporting if d!=primary and d not in secondary]
    return {
        'posture':posture,'primary_domain':primary,'domains':domains,
        'priority_tipikor_screen':{
            'required':priority_trigger,'corruption_predicate_detected':corruption_predicate,
            'note':'Screening prioritas Tipikor bukan kesimpulan terpenuhinya unsur. Melawan hukum/penyalahgunaan kewenangan, mens rea, kerugian aktual, kausalitas dan pertanggungjawaban individual tetap harus dibuktikan.'
        },
        'domain_contract':[d['id'] for d in domains if d['role'] in ('PRIMARY','SECONDARY')],
        'supporting_only':[d['id'] for d in domains if d['role']=='SUPPORTING_ONLY'],
        'forum_screen': {
            'inheritance_detected': bool(inheritance),
            'absolute_competence_disputed': bool(forum_dispute),
            'religious_court_explicit': bool(_count(low,['pengadilan agama','peradilan agama','pasal 49'])),
            'note': 'Isu waris tidak otomatis menentukan forum. Kompetensi absolut wajib diuji dari status para pihak, objek sengketa, petitum, dan dasar kewenangan yang benar-benar berlaku.'
        },
    }

FEW_SHOT_BOUNDARY = """
BATAS DEMARKASI DOMAIN — WAJIB DIPATUHI
Contoh A — TIPIKOR BPR:
Direktur Utama Perumda BPR diperiksa sebagai tersangka atas fasilitas kredit Rp255 juta; terdapat isu survei, 5C, penyimpangan prosedur/kewenangan dan dugaan kerugian keuangan daerah. Walaupun ada Perjanjian Kredit, klasifikasi: PRIMARY Tipikor/Pidana Khusus; SECONDARY Perbankan/BPR, BUMD, Acara Pidana; Perdata/Perikatan hanya SUPPORTING.

Contoh B — WANPRESTASI MURNI:
Bank/kreditur menagih debitur yang menunggak berdasarkan perjanjian kredit; tidak ada penyidikan, fraud internal, manipulasi proses kredit, penyalahgunaan kewenangan atau kerugian keuangan negara/daerah. Klasifikasi: PRIMARY Perdata/Perikatan/Wanprestasi; Perbankan SECONDARY; Tipikor bukan primary.
""".strip()
