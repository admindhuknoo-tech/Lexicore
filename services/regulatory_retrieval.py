"""Dynamic, case-scoped regulatory retrieval for LexiCore.

v1.3.5.2 precision rules:
- regulation follows the case, not a giant local corpus;
- strong legal entities outrank generic vocabulary;
- query generation is issue/domain driven and rejects orphan articles;
- discovery results are funneled: discovered -> candidate -> materially relevant
  -> temporal screen -> authoritative source located;
- temporal screening never claims final applicability without professional review.
"""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable

from legal_sources import federated_search, federated_search_many, supplementary_search_many, fetch_official_document, resolve_official_fulltext
from services.positive_law_verification import html_to_text, verify_document_candidate, verify_provisions, classify_legal_document_candidate, regulation_identity, evaluate_case_nexus, normalize_provision_ref
from services.case_domain_classifier import classify_case
from database import RegulatoryCorpusManager

DOMAIN_RULES = [
    {
        "id": "financial_services", "label": "Perbankan / Jasa Keuangan",
        "keywords": {"bpr":5.0,"bank":2.0,"kredit":1.5,"debitur":1.5,"ojk":5.0,"pojk":5.0,"seojk":5.0,"slik":4.0,"bmpk":5.0,"agunan":2.0,"fidusia":2.0,"perkreditan":3.0,"komite kredit":4.0,"prinsip kehati-hatian":4.0},
        "sources": ("ojk", "bpk"),
        "queries": (
            "BPR tata kelola Direksi persetujuan kredit",
            "POJK BPR manajemen risiko kredit",
            "BPR prinsip kehati-hatian analisis kredit",
            "BPR batas maksimum pemberian kredit BMPK",
        ),
    },
    {
        "id": "employment", "label": "Ketenagakerjaan",
        "keywords": {"phk":5.0,"pemutusan hubungan kerja":5.0,"pesangon":4.0,"pkwt":5.0,"pkwtt":5.0,"pekerja":1.0,"buruh":2.0,"ketenagakerjaan":4.0,"upah":2.0,"outsourcing":3.0},
        "sources": ("kemnaker", "bpk"),
        "queries": ("UU Ketenagakerjaan PHK pesangon", "PP 35 Tahun 2021 PKWT PHK"),
    },
    {
        "id": "corruption", "label": "Tindak Pidana Korupsi",
        "keywords": {"korupsi":5.0,"tipikor":5.0,"kerugian negara":4.0,"memperkaya":3.0,"penyalahgunaan kewenangan":5.0,"gratifikasi":4.0,"suap":4.0,"pasal 603":5.0},
        "sources": ("bpk", "kemenkum", "mk", "ma"),
        "queries": ("UU Tipikor penyalahgunaan kewenangan kerugian negara", "KUHP tindak pidana korupsi Pasal 603"),
    },
    {
        "id": "criminal", "label": "Pidana / Acara Pidana",
        "keywords": {"tersangka":4.0,"terdakwa":4.0,"penyidikan":4.0,"penuntutan":4.0,"bap":4.0,"pidana":2.0,"kuhp":5.0,"kuhap":5.0,"praperadilan":5.0},
        "sources": ("bpk", "kemenkum", "mk", "ma"),
        "queries": ("KUHAP hak tersangka penyidikan", "KUHP asas legalitas tempus delicti"),
    },
    {
        "id": "civil_contract", "label": "Perdata / Perikatan",
        "keywords": {"perjanjian":0.7,"kontrak":1.5,"wanprestasi":5.0,"utang":0.8,"piutang":1.0,"ganti rugi":1.0,"kuhperdata":5.0,"perikatan":3.0},
        "sources": ("bpk", "ma"),
        "queries": ("KUHPerdata perjanjian wanprestasi",),
    },
    {
        "id": "corporate", "label": "Perseroan / Korporasi",
        "keywords": {"perseroan":5.0,"direksi":1.5,"komisaris":2.0,"pemegang saham":3.0,"pt ":3.0,"perusahaan":0.5,"business judgment":5.0},
        "sources": ("bpk", "ma"),
        "queries": ("Undang-Undang Perseroan Terbatas tanggung jawab Direksi",),
    },
    {
        "id": "land_property", "label": "Pertanahan / Properti",
        "keywords": {"sertifikat":4.0,"sertipikat":4.0,"shm":5.0,"hgb":5.0,"hak milik":4.0,"bpn":5.0,"kantor pertanahan":5.0,"pendaftaran tanah":5.0,"surat ukur":4.0,"data fisik":3.0,"data yuridis":3.0,"uupa":5.0,"agraria":4.0},
        "sources": ("atr_bpn", "bpk", "ma"),
        "queries": ("UUPA hak milik pendaftaran tanah", "PP pendaftaran tanah sertipikat hak milik"),
    },
    {
        "id": "religious_court", "label": "Peradilan Agama / Kompetensi Absolut",
        "keywords": {"pengadilan agama":5.0,"peradilan agama":5.0,"kompetensi absolut":5.0,"kewenangan absolut":5.0,"pasal 49":3.0,"uu no. 7 tahun 1989":5.0,"uu nomor 3 tahun 2006":5.0,"waris islam":4.0,"wakaf":4.0},
        "sources": ("kemenag", "bpk", "ma"),
        "queries": ("UU Peradilan Agama Pasal 49 kewenangan absolut", "Peradilan Agama kompetensi absolut sengketa waris wakaf"),
    },
    {
        "id": "civil_procedure", "label": "Hukum Acara Perdata",
        "keywords": {"gugatan":2.0,"tergugat":1.5,"penggugat":1.5,"eksepsi":4.0,"obscuur libel":5.0,"plurium litis consortium":5.0,"rekonvensi":4.0,"kompetensi absolut":4.0,"kewenangan absolut":4.0,"rv":3.0,"h.i.r":4.0,"hir":3.0},
        "sources": ("ma", "bpk"),
        "queries": ("hukum acara perdata eksepsi obscuur libel plurium litis consortium", "kompetensi absolut pengadilan gugatan perdata"),
    },
    {
        "id": "constitutional", "label": "Konstitusi / Pengujian Norma",
        "keywords": {"uud 1945":5.0,"konstitusi":4.0,"mahkamah konstitusi":5.0,"uji materi":5.0,"pengujian undang-undang":5.0},
        "sources": ("mk", "jdih_mk", "setneg"),
        "queries": ("UUD 1945 kepastian hukum",),
    },
    {
        "id": "regional_government", "label": "Pemerintahan Daerah / BUMD",
        "keywords": {"perda":3.0,"walikota":3.0,"bupati":3.0,"gubernur":3.0,"pemda":3.0,"pemerintah daerah":3.0,"bumd":5.0,"perumda":5.0},
        "sources": ("kemendagri", "bpk"),
        "queries": ("BUMD Perumda tata kelola Direksi",),
    },
    {
        "id": "consumer", "label": "Perlindungan Konsumen",
        "keywords": {"perlindungan konsumen":5.0,"konsumen":2.0,"pelaku usaha":2.0,"klausula baku":5.0,"badan penyelesaian sengketa konsumen":5.0,"bpsk":5.0},
        "sources": ("bpk", "ma"),
        "queries": ("UU Perlindungan Konsumen klausula baku pelaku usaha",),
    },
    {
        "id": "data_privacy", "label": "Pelindungan Data Pribadi / ITE",
        "keywords": {"data pribadi":5.0,"pelindungan data pribadi":5.0,"uu pdp":5.0,"informasi elektronik":4.0,"transaksi elektronik":4.0,"sistem elektronik":3.0},
        "sources": ("komdigi", "bpk", "mk", "ma"),
        "queries": ("UU Pelindungan Data Pribadi data pribadi", "UU ITE informasi elektronik transaksi elektronik"),
    },
    {
        "id": "bankruptcy", "label": "Kepailitan / PKPU",
        "keywords": {"kepailitan":5.0,"pkpu":5.0,"pailit":5.0,"dua kreditur":4.0,"pengadilan niaga":4.0},
        "sources": ("ma", "bpk"),
        "queries": ("UU Kepailitan PKPU dua kreditur jatuh tempo",),
    },
    {
        "id": "arbitration", "label": "Arbitrase / ADR",
        "keywords": {"arbitrase":5.0,"bani":5.0,"klausul arbitrase":5.0,"alternatif penyelesaian sengketa":4.0},
        "sources": ("bpk", "ma"),
        "queries": ("UU Arbitrase alternatif penyelesaian sengketa",),
    },
    {
        "id": "administrative", "label": "Hukum Administrasi / PTUN",
        "keywords": {"ptun":5.0,"keputusan tata usaha negara":5.0,"upaya administratif":5.0,"aaupb":5.0,"pejabat tata usaha negara":4.0},
        "sources": ("bpk", "ma", "kemendagri", "kemenkum"),
        "queries": ("UU PTUN keputusan tata usaha negara upaya administratif", "UU Administrasi Pemerintahan AUPB keputusan tindakan"),
    },
    {
        "id": "public_information", "label": "Keterbukaan Informasi Publik",
        "keywords": {"keterbukaan informasi publik":5.0,"informasi publik":4.0,"badan publik":4.0,"komisi informasi":5.0},
        "sources": ("bpk", "komdigi", "ma"),
        "queries": ("UU Keterbukaan Informasi Publik badan publik sengketa informasi",),
    },
    {
        "id": "investment", "label": "Penanaman Modal / Investasi",
        "keywords": {"penanaman modal":5.0,"investasi":4.0,"bkpm":5.0,"perizinan berusaha":4.0,"investor":3.0},
        "sources": ("bpk", "kemenkum"),
        "queries": ("UU Penanaman Modal perizinan berusaha investor",),
    },
]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _dedupe(values: Iterable[str], limit: int = 12) -> list[str]:
    out, seen = [], set()
    for value in values:
        v = _clean(value); key = v.lower()
        if not v or key in seen:
            continue
        seen.add(key); out.append(v)
        if len(out) >= limit:
            break
    return out


def _count_signal(low: str, signal: str) -> int:
    if signal.endswith(" "):
        return low.count(signal)
    return len(re.findall(r"(?<!\w)" + re.escape(signal) + r"(?!\w)", low, flags=re.I))


def detect_domains(text: str) -> list[dict]:
    """Return the immutable domain contract produced by Case Posture Classifier."""
    contract=classify_case(text)
    rule_map={r["id"]:r for r in DOMAIN_RULES}
    out=[]
    for d in contract.get('domains',[]):
        rid=d.get('id'); rule=rule_map.get(rid,{})
        out.append({
            'id':rid,'label':d.get('label') or rule.get('label') or rid,
            'confidence':round(float(d.get('confidence',0))/100.0,2),
            'role':d.get('role','SECONDARY'),'signal_score':d.get('score',0),
            'source_ids':list(rule.get('sources',('bpk','ma'))),
            'signals':[],
        })
    return out


def detect_material_year(text: str) -> int | None:
    """Best-effort event year for an initial tempus screen, never final law.

    Uses frequency plus material-context weighting instead of the earliest year;
    this avoids mistaking biography/employment history or old statute years for
    the tempus of the alleged act in long BAP documents.
    """
    raw = text or ""
    matches = list(re.finditer(r"\b(19\d{2}|20\d{2})\b", raw))
    if not matches:
        return None
    material_terms = ("kredit","pencairan","perbuatan","kejadian","transaksi","fasilitas","persetujuan","putusan","phk","kontrak","perjanjian","tempus")
    procedural_terms = ("surat perintah penyidikan","penetapan tersangka","berita acara pemeriksaan","pemeriksaan tersangka")
    scores = {}
    counts = {}
    now_year = datetime.now().year
    for m in matches:
        y = int(m.group(1))
        if y < 1945 or y > now_year:
            continue
        counts[y] = counts.get(y, 0) + 1
        window = raw[max(0,m.start()-140):m.end()+140].lower()
        score = 1.0
        score += 4.0 * sum(1 for t in material_terms if t in window)
        score -= 1.5 * sum(1 for t in procedural_terms if t in window)
        # statute citation years are useful context but weak evidence of tempus
        if re.search(r"(?:uu|undang-undang|pojk|seojk|peraturan)[^\n]{0,50}tahun\s*$", window[:140], re.I):
            score -= 2.0
        scores[y] = scores.get(y, 0.0) + score
    if not scores:
        return None
    # Frequency matters strongly in full documents; weighted context breaks ties.
    return max(scores, key=lambda y: (scores[y] + counts.get(y,0)*0.75, counts.get(y,0), y))



def _normalize_ocr_date_spacing(text: str) -> str:
    """Join OCR-split day digits only when immediately followed by an Indonesian month.
    Example: '2 6 Februari 2026' -> '26 Februari 2026'.
    """
    months = r'Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember'
    def repl(m):
        day = int(m.group(1) + m.group(2))
        return f"{day} {m.group(3)} {m.group(4)}" if 1 <= day <= 31 else m.group(0)
    return re.sub(rf'(?<!\d)([0-3])\s+([0-9])\s+({months})\s+(20\d{{2}})(?!\d)', repl, text or '', flags=re.I)


def detect_case_dates(text: str) -> list[dict]:
    raw = _normalize_ocr_date_spacing(text or '')
    months={'januari':1,'februari':2,'maret':3,'april':4,'mei':5,'juni':6,'juli':7,'agustus':8,'september':9,'oktober':10,'november':11,'desember':12}
    matches=[]
    for m in re.finditer(r'(?<!\d)(\d{1,2})\s*([A-Za-z]+)\s*(20\d{2})(?!\d)', raw, re.I):
        mon=months.get(m.group(2).lower())
        if mon: matches.append((m,int(m.group(1)),mon,int(m.group(3))))
    for m in re.finditer(r'(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](20\d{2})(?!\d)', raw):
        matches.append((m,int(m.group(1)),int(m.group(2)),int(m.group(3))))
    out=[]
    for m,d,mo,y in matches:
        if not (1<=d<=31 and 1<=mo<=12): continue
        before=raw[max(0,m.start()-160):m.start()].lower()
        near_before=raw[max(0,m.start()-90):m.start()].lower()
        near_after=raw[m.end():m.end()+45].lower()
        around=raw[max(0,m.start()-220):m.end()+180].lower()
        role='unknown'; score=0
        # Date role is determined from the immediate grammatical context. A statute
        # mentioned later in the same paragraph must not reclassify a transaction date.
        regulation_near = any(k in near_before for k in ('pojk','seojk','undang-undang','peraturan','uu no.','uu nomor')) or any(k in near_after for k in ('mulai berlaku','berlaku sejak','diundangkan'))
        if regulation_near:
            role='regulation_date'; score -= 20
        elif any(k in near_before for k in ('perjanjian kredit','transaksi','pencairan','persetujuan kredit','jual beli','akta jual beli','kejadian','perbuatan')):
            role='material_event'; score += 18
        elif any(k in near_before for k in ('gugatan','permohonan','surat gugatan','sidang','skpt','surat keterangan pendaftaran tanah','meminta')):
            role='procedural_or_filing'; score += 5
        elif any(k in near_before for k in ('surat ukur','pengumuman data fisik','data yuridis','sertifikat','sertipikat','diterbitkan')):
            role='historical_record'; score += 7
        if any(k in around for k in ('berita acara pemeriksaan','penetapan tersangka','surat perintah penyidikan')):
            if role == 'unknown': role='procedural_or_filing'
            score -= 4
        out.append({'date':f'{y:04d}-{mo:02d}-{d:02d}','role':role,'score':score,'context':_clean(around)[:260]})
    # dedupe date/role and sort strongest first
    seen=set(); unique=[]
    for item in sorted(out,key=lambda x:(x['score'],x['date']),reverse=True):
        key=(item['date'],item['role'])
        if key not in seen: seen.add(key); unique.append(item)
    return unique[:20]


def detect_material_date(text: str) -> str | None:
    """Return only a defensible material-event date, never a filing date by default."""
    candidates=detect_case_dates(text)
    material=[x for x in candidates if x['role']=='material_event' and x['score'] >= 10]
    return material[0]['date'] if material else None

def _qualified_ref(ref: str) -> bool:
    ref = _clean(ref)
    if not ref or re.fullmatch(r"Pasal\s+\d+[A-Za-z]?", ref, re.I):
        return False
    return any(k in ref.lower() for k in ("uu ", "undang-undang", "pojk", "seojk", "peraturan", "kuhp", "kuhap", "kuhperdata", "perma", "sema"))



KNOWN_REGULATION_QUERIES = {
    # Canonical deterministic instrument registry. Keep exact official titles
    # where a clean Indonesian statutory identity exists. civil_procedure is
    # intentionally left empty because its core sources (HIR/RBg) do not map
    # cleanly to the UU Nomor X Tahun Y identity pattern and must not be guessed.
    "financial_services": (
        "Undang-Undang Nomor 7 Tahun 1992 tentang Perbankan",
        "Undang-Undang Nomor 10 Tahun 1998 tentang Perubahan atas Undang-Undang Nomor 7 Tahun 1992 tentang Perbankan",
        "Undang-Undang Nomor 21 Tahun 2011 tentang Otoritas Jasa Keuangan",
        "Undang-Undang Nomor 4 Tahun 2023 tentang Pengembangan dan Penguatan Sektor Keuangan",
    ),
    "employment": (
        "Undang-Undang Nomor 13 Tahun 2003 tentang Ketenagakerjaan",
        "Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-Undang",
    ),
    "corruption": (
        "Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "Undang-Undang Nomor 20 Tahun 2001 tentang Perubahan atas Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
    ),
    "criminal": (
        "Undang-Undang Nomor 20 Tahun 2025 tentang Kitab Undang-Undang Hukum Acara Pidana",
        "Undang-Undang Nomor 1 Tahun 2023 tentang Kitab Undang-Undang Hukum Pidana",
        "Undang-Undang Nomor 1 Tahun 2026 tentang Penyesuaian Pidana",
    ),
    "civil_contract": (
        "Kitab Undang-Undang Hukum Perdata Burgerlijk Wetboek",
    ),
    "corporate": (
        "Undang-Undang Nomor 40 Tahun 2007 tentang Perseroan Terbatas",
    ),
    "land_property": (
        "Undang-Undang Nomor 5 Tahun 1960 tentang Peraturan Dasar Pokok-Pokok Agraria",
        "Peraturan Pemerintah Nomor 24 Tahun 1997 tentang Pendaftaran Tanah",
        "Peraturan Pemerintah Nomor 18 Tahun 2021 tentang Hak Pengelolaan, Hak Atas Tanah, Satuan Rumah Susun, dan Pendaftaran Tanah",
    ),
    "religious_court": (
        "Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama",
        "Undang-Undang Nomor 3 Tahun 2006 tentang Perubahan atas Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama",
        "Undang-Undang Nomor 50 Tahun 2009 tentang Perubahan Kedua atas Undang-Undang Nomor 7 Tahun 1989 tentang Peradilan Agama",
    ),
    "civil_procedure": (),
    "constitutional": (
        "Undang-Undang Nomor 24 Tahun 2003 tentang Mahkamah Konstitusi",
        "Undang-Undang Nomor 7 Tahun 2020 tentang Perubahan Ketiga atas Undang-Undang Nomor 24 Tahun 2003 tentang Mahkamah Konstitusi",
    ),
    "regional_government": (
        "Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah",
        "Undang-Undang Nomor 9 Tahun 2015 tentang Perubahan Kedua atas Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah",
    ),
    "consumer": (
        "Undang-Undang Nomor 8 Tahun 1999 tentang Perlindungan Konsumen",
    ),
    "data_privacy": (
        "Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi",
        "Undang-Undang Nomor 11 Tahun 2008 tentang Informasi dan Transaksi Elektronik",
        "Undang-Undang Nomor 1 Tahun 2024 tentang Perubahan Kedua atas Undang-Undang Nomor 11 Tahun 2008 tentang Informasi dan Transaksi Elektronik",
    ),
    "bankruptcy": (
        "Undang-Undang Nomor 37 Tahun 2004 tentang Kepailitan dan Penundaan Kewajiban Pembayaran Utang",
    ),
    "arbitration": (
        "Undang-Undang Nomor 30 Tahun 1999 tentang Arbitrase dan Alternatif Penyelesaian Sengketa",
    ),
    "administrative": (
        "Undang-Undang Nomor 5 Tahun 1986 tentang Peradilan Tata Usaha Negara",
        "Undang-Undang Nomor 51 Tahun 2009 tentang Perubahan Kedua atas Undang-Undang Nomor 5 Tahun 1986 tentang Peradilan Tata Usaha Negara",
        "Undang-Undang Nomor 30 Tahun 2014 tentang Administrasi Pemerintahan",
    ),
    "public_information": (
        "Undang-Undang Nomor 14 Tahun 2008 tentang Keterbukaan Informasi Publik",
    ),
    "investment": (
        "Undang-Undang Nomor 25 Tahun 2007 tentang Penanaman Modal",
    ),
}


def _known_query_domains(query: str, domains: list[dict]) -> list[str]:
    q=_clean(query).lower()
    active={str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"}
    matched=[]
    for domain_id, rows in KNOWN_REGULATION_QUERIES.items():
        if domain_id not in active:
            continue
        if any(q == _clean(x).lower() for x in rows):
            matched.append(domain_id)
    return matched


def _domain_rule_query_domains(query: str, domains: list[dict]) -> list[str]:
    """Return active domains whose deterministic DOMAIN_RULES emitted *query*.

    RC18 R4 closes a reachability gap where only the small
    KNOWN_REGULATION_QUERIES table could create a promotable deterministic
    route.  DOMAIN_RULES is the canonical domain registry, so a query emitted
    by an active rule carries deterministic case-routing provenance too.
    This does not by itself prove applicability: official instrument identity,
    article text, legal status and tempus remain separate fail-closed gates.
    """
    q=_clean(query).lower()
    if not q:
        return []
    active={str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"}
    matched=[]
    for rule in DOMAIN_RULES:
        domain_id=str(rule.get("id") or "")
        if domain_id not in active:
            continue
        if any(q == _clean(x).lower() for x in (rule.get("queries") or ())):
            matched.append(domain_id)
    return matched


EXACT_QUERY_DOMAIN_MARKERS = {
    "financial_services": ("perbankan", "bank perkreditan rakyat", "bank perekonomian rakyat", "bpr", "otoritas jasa keuangan", "pojk", "seojk"),
    "corruption": ("pemberantasan tindak pidana korupsi", "tindak pidana korupsi", "tipikor", "korupsi"),
    "criminal": ("kitab undang-undang hukum pidana", "kuhp", "kitab undang-undang hukum acara pidana", "kuhap", "penyesuaian pidana"),
    "regional_government": ("pemerintahan daerah", "badan usaha milik daerah", "bumd", "perumda"),
    "land_property": ("pokok-pokok agraria", "pendaftaran tanah", "pertanahan", "agraria"),
    "religious_court": ("peradilan agama", "pengadilan agama"),
    "civil_procedure": ("hukum acara perdata", "perma", "sema"),
    "employment": ("ketenagakerjaan", "pemutusan hubungan kerja", "pkwt", "pkwtt"),
    "administrative": ("peradilan tata usaha negara", "administrasi pemerintahan", "ptun"),
    "public_information": ("keterbukaan informasi publik",),
    "investment": ("penanaman modal",),
    "consumer": ("perlindungan konsumen",),
    "bankruptcy": ("kepailitan", "penundaan kewajiban pembayaran utang", "pkpu"),
    "arbitration": ("arbitrase", "alternatif penyelesaian sengketa"),
    "data_privacy": ("pelindungan data pribadi", "informasi dan transaksi elektronik"),
}

def _exact_case_query_domains(query: str, domains: list[dict]) -> list[str]:
    """Map an exact regulation citation from the case to active domains.

    This is intentionally stricter than treating every regulation-looking query as
    relevant: the query must carry an exact instrument identity and explicit
    subject-matter wording that overlaps an already-active case domain.
    """
    if not regulation_identity(query).get("key"):
        return []
    low=_clean(query).lower()
    active={str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"}
    out=[]
    for domain_id in active:
        if any(marker in low for marker in EXACT_QUERY_DOMAIN_MARKERS.get(domain_id, ())):
            out.append(domain_id)
    return sorted(out)

def _extract_case_regulation_bindings(text: str) -> list[dict]:
    """Extract exact regulation identities and nearby Pasal refs from source text.

    This closes the RC17/RC18 wiring gap where the route generated qualified
    verification queries, but provenance was later discarded and article counters
    stayed at zero.  The extractor works directly on the uploaded case text, so
    system-generated discovery queries can never masquerade as case citations.
    It preserves typos exactly as written; normalization candidates remain review-only.
    """
    raw=re.sub(r"\s+"," ",str(text or "")).strip()
    if not raw:
        return []
    inst_pat=re.compile(
        r"(?:Undang-Undang|Undang undang|UU)(?:\s+Republik(?:\s+Indonesia)?|\s+Republk(?:\s+Indonesia)?)?\s+(?:Nomor|No\.?)\s*\d+[A-Za-z]?\s+Tahun\s+\d{4}"
        r"|(?:Peraturan Pemerintah|PP)(?:\s+Republik Indonesia)?\s+(?:Nomor|No\.?)\s*\d+[A-Za-z]?\s+Tahun\s+\d{4}"
        r"|(?:Peraturan Mahkamah Agung|PERMA)\s+(?:Nomor|No\.?)\s*\d+[A-Za-z]?\s+Tahun\s+\d{4}"
        r"|(?:Surat Edaran Mahkamah Agung|SEMA)\s+(?:Nomor|No\.?)\s*\d+[A-Za-z]?\s+Tahun\s+\d{4}"
        r"|(?:Peraturan Otoritas Jasa Keuangan|POJK)\s+(?:Nomor|No\.?)\s*\d+(?:/POJK\.\d+)?/(?:20\d{2})"
        r"|(?:Surat Edaran Otoritas Jasa Keuangan|SEOJK)\s+(?:Nomor|No\.?)\s*\d+(?:/SEOJK\.\d+)?/(?:20\d{2})"
        r"|(?:Peraturan Otoritas Jasa Keuangan|POJK)\s+(?:Nomor|No\.?)\s*\d+\s+Tahun\s+20\d{2}"
        r"|(?:Surat Edaran Otoritas Jasa Keuangan|SEOJK)\s+(?:Nomor|No\.?)\s*\d+\s+Tahun\s+20\d{2}", re.I)
    provision_pat=re.compile(r"\bPasal\s+\d+[A-Za-z]?(?:\s+ayat\s*\([^)]+\))?(?:\s+huruf\s+[a-z])?",re.I)
    matches=list(inst_pat.finditer(raw))
    out=[]; seen=set()
    for i,m in enumerate(matches):
        ident=regulation_identity(m.group(0))
        if not ident.get('key'):
            continue
        # Title/subject tail helps domain nexus but stops at jo/next Pasal/punctuation.
        tail_end=min(len(raw),m.end()+180)
        tail=raw[m.end():tail_end]
        stop=re.search(r"\bjo\b|\bPasal\s+\d+|[.;]",tail,re.I)
        subject_tail=tail[:stop.start()] if stop else tail[:120]
        query=_clean(m.group(0)+' '+subject_tail).strip(' ,:-')
        # Bind only the closest preceding article in the same clause/window.
        left_start=max(0,m.start()-180)
        left=raw[left_start:m.start()]
        provisions=[]
        prev=list(provision_pat.finditer(left))
        if prev:
            # Keep all Pasal refs after the most recent prior instrument boundary.
            # This correctly binds chains such as "Pasal 3 jo Pasal 18 UU 31/1999"
            # while excluding Pasal 603 that already belonged to an earlier UU.
            last_inst=None
            for prior_inst in inst_pat.finditer(left):
                last_inst=prior_inst
            cutoff=last_inst.end() if last_inst else 0
            for pm in prev:
                if pm.start() < cutoff:
                    continue
                ref=normalize_provision_ref(pm.group(0))
                if ref and ref not in provisions:
                    provisions.append(ref)
        key=(ident.get('key'),tuple(provisions),query.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            'identity':ident,'query':query,'provisions':provisions,
            'source_excerpt':_clean(raw[max(0,m.start()-100):min(len(raw),m.end()+160)]),
            'provenance':'EXACT_CASE_TEXT',
        })
    return out


def _case_exact_regulation_queries(provision_refs, qualified_queries=None, text: str = "") -> set[str]:
    """Return exact case-source regulation citations, never discovery guesses."""
    out=set()
    for binding in _extract_case_regulation_bindings(text):
        q=_clean(binding.get('query') or '')
        if regulation_identity(q).get('key'):
            out.add(q.lower())
    # Keep backward compatibility for legacy payloads where a full instrument was
    # already stored in provision_refs. This does not use generated research text.
    for raw in list(provision_refs or []):
        q=_clean(str(raw))
        if _qualified_ref(q) and regulation_identity(q).get("key"):
            out.add(q.lower())
    return out


def _case_binding_provision_map(text: str) -> dict[str,list[str]]:
    out={}
    for binding in _extract_case_regulation_bindings(text):
        ident=(binding.get('identity') or {}).get('key')
        if not ident:
            continue
        bucket=out.setdefault(ident,[])
        for ref in binding.get('provisions') or []:
            if ref not in bucket:
                bucket.append(ref)
    return out


def build_case_queries(text: str, title: str = "", provision_refs=None, domains=None,
                       qualified_queries=None, legal_issues=None, max_queries: int = 10) -> list[str]:
    provision_refs = provision_refs or []
    domains = domains or detect_domains(text)
    legal_issues = legal_issues or []
    queries: list[str] = []

    # 1) Exact regulation-qualified references from the case are strongest.
    queries.extend([_clean(str(r)) for r in provision_refs if _qualified_ref(str(r))])
    for q in qualified_queries or []:
        if _qualified_ref(str(q)):
            queries.append(_clean(str(q)))

    # 2) Domain/issue-driven routes before generic discovery phrases.
    rule_map = {r["id"]: r for r in DOMAIN_RULES}
    active_domains=[d for d in domains if d.get("role") != "SUPPORTING_ONLY"]
    ids = {d["id"] for d in active_domains[:4]}

    # Critical cross-domain benchmark questions must be emitted before the known
    # instrument expansion.  Once KNOWN_REGULATION_QUERIES covers all major
    # domains, otherwise a max_queries=10 budget can crowd out the tempus query
    # in mixed BPR/Tipikor matters.  This is ordering only: no feature is removed.
    event_year = detect_material_year(text)
    if event_year and ("criminal" in ids or "corruption" in ids):
        queries.append(f"tempus delicti {event_year} asas legalitas ketentuan pidana")
    if "financial_services" in ids:
        if "regional_government" in ids:
            queries.append("Perumda BPR kewenangan Direksi persetujuan kredit tata kelola")
        if "corruption" in ids:
            queries.append("BPR kredit penyalahgunaan kewenangan kerugian negara Tipikor")

    # Known-regulation resolution: exact legal instruments outrank broad
    # discovery so official news/event pages do not consume the verification budget.
    for domain in active_domains[:3]:
        queries.extend(KNOWN_REGULATION_QUERIES.get(domain.get("id"), ())[:3])

    for domain in active_domains[:3]:
        rule = rule_map.get(domain["id"], {})
        queries.extend(rule.get("queries", ())[:2])

    # 3) Legal issues from deterministic/AI issue spotting, but only compact and
    # materially worded; do not let long free text dominate the query budget.
    for issue in legal_issues[:5]:
        if isinstance(issue, dict):
            issue = issue.get("issue") or issue.get("title") or issue.get("statement") or ""
        issue = _clean(str(issue))
        if 8 <= len(issue) <= 160:
            queries.append(issue)

    # 4) Existing qualified discovery queries are supplemental. Filter generic
    # domain labels that caused v1.3.5.1 to over-route to BW/corporate law.
    for q in qualified_queries or []:
        q = _clean(str(q))
        ql = q.lower()
        if not q or _qualified_ref(q) or re.fullmatch(r"Pasal\s+\d+[A-Za-z]?", q, re.I):
            continue
        if ql.startswith(("perdata & perikatan", "perusahaan & komersial")) and "financial_services" in ids:
            continue
        queries.append(q)

    title = _clean(title)
    if title and title.lower() != "case analysis" and len(title) <= 180:
        queries.append(title)
    if not queries:
        tokens = re.findall(r"\b[\w-]{4,}\b", (text or "")[:1800], flags=re.UNICODE)
        queries.append(" ".join(tokens[:10]))
    return _dedupe(queries, max_queries)


def _source_ids_for_domains(domains: list[dict]) -> tuple[str, ...]:
    ids = []
    for d in [x for x in domains if x.get("role") != "SUPPORTING_ONLY"][:4]:
        ids.extend(d.get("source_ids", []))
    if not ids:
        ids = ["bpk", "kemenkum", "ma", "mk"]
    return tuple(_dedupe(ids, 8))


def _terms(value: str) -> set[str]:
    stop = {"yang","dan","atau","dengan","dalam","untuk","tahun","tentang","pasal","undang","peraturan","hukum","pada","bagi","dari","no"}
    return {t for t in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if t not in stop}


def _result_relevance(row: dict, domains: list[dict]) -> float:
    hay = _terms((row.get("title") or "") + " " + (row.get("query") or ""))
    if not hay:
        return 0.0
    domain_terms = set()
    strong_terms = set()
    rule_map = {r["id"]: r for r in DOMAIN_RULES}
    for d in domains[:3]:
        for k, weight in rule_map.get(d["id"], {}).get("keywords", {}).items():
            ts = _terms(k)
            domain_terms |= ts
            if weight >= 3:
                strong_terms |= ts
    overlap = len(hay & domain_terms)
    strong = len(hay & strong_terms)
    query_terms = _terms(row.get("query") or "")
    q_overlap = len(hay & query_terms)
    score = 0.08 * overlap + 0.16 * strong + 0.035 * q_overlap
    if row.get("authoritative"):
        score += 0.08
    return round(min(score, 1.0), 3)


def _temporal_screen(row: dict, event_year: int | None) -> str:
    if not event_year:
        return "TEMPUS_UNKNOWN"
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", row.get("title") or "")]
    if years and min(years) > event_year:
        return "POST_EVENT_REFERENCE"
    if years:
        return "NOT_EXCLUDED_BY_YEAR"
    return "TEMPUS_REQUIRES_VERIFICATION"


def _compact_searches(queries: list[str], domains: list[dict], event_year: int | None, procedural_year: int | None = None, per_source_limit: int = 4, case_exact_queries: set[str] | None = None) -> dict:
    source_ids = _source_ids_for_domains(domains)
    case_exact_queries={_clean(x).lower() for x in (case_exact_queries or set()) if _clean(x)}
    bundles, flat, seen_urls = [], [], set()
    discovered_count = 0
    # v1.3.13.11.1 — execute independent case queries concurrently.
    # The processing loop below still follows the original query order so ranking,
    # deduplication and report semantics remain deterministic.
    # v1.3.13.11.2 — one bounded federation pool for all query/source jobs.
    # Avoid the previous nested query-pool -> source-pool fan-out that could
    # create dozens of simultaneous TLS requests and freeze the local process.
    search_map=federated_search_many(
        queries, direct_ids=source_ids, per_source_limit=per_source_limit,
        max_workers=6, time_budget_seconds=20.0) if queries else {}
    for query in queries:
        searches = search_map.get(query,[])
        compact_sources = []
        for src in searches:
            results = []
            for item in src.get("results", []):
                discovered_count += 1
                url = item.get("url") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                row = {
                    "title": _clean(item.get("title", ""))[:360], "url": url,
                    "source_id": src.get("source_id"), "source_name": src.get("source_name"),
                    "authoritative": bool(src.get("authoritative")), "query": query,
                    "source_score": item.get("score", 0),
                }
                row["relevance_score"] = _result_relevance(row, domains)
                known_domains=_known_query_domains(query, domains)
                domain_rule_domains=_domain_rule_query_domains(query, domains)
                exact_case_domains=_exact_case_query_domains(query, domains) if _clean(query).lower() in case_exact_queries else []
                if exact_case_domains:
                    row["query_origin"] = "EXACT_CASE_REGULATION"
                    row["relevance_score"] = min(1.0, row["relevance_score"] + 0.42)
                elif known_domains:
                    row["query_origin"] = "KNOWN_REGULATION"
                    row["relevance_score"] = min(1.0, row["relevance_score"] + 0.30)
                elif domain_rule_domains:
                    row["query_origin"] = "DOMAIN_RULE_REGULATION"
                    row["relevance_score"] = min(1.0, row["relevance_score"] + 0.24)
                else:
                    row["query_origin"] = "DISCOVERY"
                active_domain_ids=[str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"]
                nexus=evaluate_case_nexus(row, active_domain_ids)
                row["case_nexus_domains"] = list(dict.fromkeys((exact_case_domains or []) + (known_domains or []) + (domain_rule_domains or []) + (nexus.get("matched_domains") or [])))
                row["case_nexus_status"] = nexus.get("status") or "CASE_NEXUS_UNCERTAIN"
                row["case_nexus_reason"] = nexus.get("reason")
                row["document_classification"] = classify_legal_document_candidate(row)
                qlow=(query or "").lower()
                anchor_year = procedural_year if procedural_year and any(k in qlow for k in ("kuhap","praperadilan","upaya paksa","acara pidana","hukum acara","pengadilan")) else event_year
                row["temporal_anchor"] = "PROCEDURAL" if anchor_year==procedural_year and procedural_year else "MATERIAL_EVENT"
                row["temporal_status"] = _temporal_screen(row, anchor_year)
                results.append(row); flat.append(row)
            compact_sources.append({
                "source_id": src.get("source_id"), "source_name": src.get("source_name"),
                "authoritative": bool(src.get("authoritative")), "reachable": bool(src.get("reachable")),
                "http_status": src.get("http_status"), "results": results,
            })
        bundles.append({"query": query, "sources": compact_sources})

    origin_priority={"EXACT_CASE_REGULATION":4,"KNOWN_REGULATION":3,"DOMAIN_RULE_REGULATION":2,"DISCOVERY":1}
    flat.sort(key=lambda r: (origin_priority.get(r.get("query_origin"),0), r.get("relevance_score", 0), bool(r.get("authoritative"))), reverse=True)
    candidates = [r for r in flat if r.get("relevance_score", 0) >= 0.20]
    material = [r for r in candidates if r.get("relevance_score", 0) >= 0.38]
    temporal_not_excluded = [r for r in material if r.get("temporal_status") != "POST_EVENT_REFERENCE"]
    authoritative_located = [r for r in temporal_not_excluded if r.get("authoritative")]
    legal_document_candidates=[r for r in temporal_not_excluded if (r.get("document_classification") or {}).get("legal_instrument_candidate")]
    rejected_non_legal=[r for r in temporal_not_excluded if not (r.get("document_classification") or {}).get("legal_instrument_candidate")]
    return {
        "bundles": bundles, "results": material[:24], "source_ids": list(source_ids),
        "funnel": {
            "discovered": discovered_count,
            "unique_discovered": len(flat),
            "candidate": len(candidates),
            "materially_relevant": len(material),
            "temporal_not_excluded": len(temporal_not_excluded),
            "authoritative_source_located": len(authoritative_located),
            "legal_document_candidates": len(legal_document_candidates),
            "rejected_non_legal_content": len(rejected_non_legal),
            "positive_law_verified": 0,
            "tempus_verified": 0,
            "verified_applicable": 0,
            "temporal_verified_applicable": 0,
            "provision_requested": 0,
            "provision_verified": 0,
            "provision_documents_verified": 0,
        },
    }



def _qualified_provisions_by_identity(qualified_queries) -> dict[str,list[str]]:
    """Bind article references to the exact instrument named in a qualified query."""
    out={}
    for raw in qualified_queries or []:
        text=_clean(str(raw))
        ident=regulation_identity(text)
        if not ident.get('key'):
            continue
        refs=[]
        for m in re.finditer(r"\bPasal\s+\d+[A-Za-z]?(?:\s+ayat\s*\([^)]+\))?(?:\s+huruf\s+[a-z])?",text,re.I):
            ref=normalize_provision_ref(m.group(0))
            if ref and ref not in refs:
                refs.append(ref)
        if refs:
            bucket=out.setdefault(ident['key'],[])
            for ref in refs:
                if ref not in bucket:
                    bucket.append(ref)
    return out


def _attach_requested_provisions(results: list[dict], provision_refs, local_database_matches, qualified_queries=None, case_exact_queries=None, case_binding_map=None) -> list[dict]:
    """Attach article-level candidates without inventing Pasal numbers.

    Sources are the case's explicit provision refs and matched local-corpus
    articles whose regulation identity/subject aligns with an official result.
    The official verifier still has to find the exact provision in retrieved
    official text before it can be marked verified.
    """
    explicit=[]
    for raw in provision_refs or []:
        ref=normalize_provision_ref(str(raw))
        if ref and ref not in explicit:
            explicit.append(ref)

    # RC18 R11: generated verification queries are research routing inputs, not
    # case-source provenance.  Only bindings extracted from the uploaded source
    # text may create case-bound article demand.  This prevents a generated
    # qualified query from attaching Pasal numbers across neighbouring statutes.
    qualified_map=_qualified_provisions_by_identity(qualified_queries)
    case_binding_map={str(k):list(v or []) for k,v in (case_binding_map or {}).items()}
    exact_ids={regulation_identity(q).get('key') for q in (case_exact_queries or set()) if regulation_identity(q).get('key')}

    local=[]
    for match in local_database_matches or []:
        if not isinstance(match,dict):
            continue
        reg=match.get('regulation') or {}
        reg_id=regulation_identity(reg.get('nomor') or '')
        subject=_clean(reg.get('tentang') or '').lower()
        refs=[]
        for art in match.get('matched_articles') or []:
            if not isinstance(art,dict):
                continue
            for key in ('qualified_citation','pasal'):
                ref=normalize_provision_ref(art.get(key))
                if ref and ref not in refs:
                    refs.append(ref)
        if refs:
            local.append({'identity':reg_id,'subject':subject,'refs':refs})

    out=[]
    for row in results or []:
        item=dict(row)
        hay=_clean((item.get('title') or '')+' '+(item.get('query') or '')).lower()
        cid=regulation_identity(item.get('query') or '')
        if not cid.get('key'):
            cid=regulation_identity(item.get('title') or '')
        case_bound_refs=list(case_binding_map.get(cid.get('key'),[])) if cid.get('key') else []
        generated_qualified_refs=list(qualified_map.get(cid.get('key'),[])) if cid.get('key') else []
        # Legacy callers may provide only qualified citations and no source-text
        # binding map.  Preserve that compatibility, but when source bindings
        # exist (normal Case Analysis route) generated research queries can never
        # create case provenance.
        qualified_bound_refs=(list(generated_qualified_refs) if not case_binding_map else [])
        refs=list(case_bound_refs)
        for ref in qualified_bound_refs:
            if ref not in refs:
                refs.append(ref)
        # Global orphan article refs are safe only when the case contains a single
        # exact instrument identity; otherwise they remain unresolved rather than
        # being attached to every statute candidate.
        if not refs and len(exact_ids) == 1 and cid.get('key') in exact_ids:
            refs=list(explicit)
        for entry in local:
            same_identity=bool(cid.get('key') and entry['identity'].get('key') == cid.get('key'))
            # Article requests must stay instrument-bound.  Do not propagate a
            # local-corpus Pasal merely because an amendment/referencing title
            # shares the same subject.  That behaviour inflated one case into
            # dozens of synthetic provision checks and made the telemetry look
            # active while the legal binding was wrong.
            if same_identity:
                for ref in entry['refs']:
                    if ref not in refs:
                        refs.append(ref)
        # A result that is not tied to an exact/qualified case instrument should
        # not receive orphan article numbers.  Keep the request set small,
        # deterministic and auditable per instrument.
        item['requested_provisions']=refs[:8]
        # Preserve why an article request is attached to this instrument.  A
        # case-bound provision is stronger nexus evidence than the search-query
        # origin: it came from the uploaded case text (or an already qualified
        # citation) and was bound to this exact regulation identity before web
        # retrieval.  This provenance lets the verifier close the nexus gate
        # after official identity confirmation without trusting a DISCOVERY hit.
        item['provision_binding_provenance']={
            'exact_case_text': [r for r in item['requested_provisions'] if r in case_bound_refs],
            'qualified_case_citation': [r for r in item['requested_provisions'] if r in qualified_bound_refs],
            'generated_research_refs': [r for r in generated_qualified_refs if r not in case_bound_refs and r not in qualified_bound_refs],
            'case_bound': bool(case_bound_refs or qualified_bound_refs),
            'instrument_key': cid.get('key'),
        }
        out.append(item)
    return out


def _verification_candidate_priority(row: dict) -> tuple:
    """Rank official candidates for the scarce full-text verification budget.

    Search federation can return several URLs for the same instrument and exact
    case citations can contain typos.  A malformed exact citation must not crowd
    out a correctly identified official instrument merely because EXACT_CASE has
    a higher discovery rank.  Verification therefore prefers deterministic
    identity alignment and actual case-bound article demand.
    """
    qid=regulation_identity(row.get('query') or '')
    tid=regulation_identity(row.get('title') or '')
    same_identity=bool(qid.get('key') and tid.get('key') == qid.get('key'))
    requested=len([x for x in (row.get('requested_provisions') or []) if normalize_provision_ref(x)])
    origin={'EXACT_CASE_REGULATION':4,'KNOWN_REGULATION':3,'DOMAIN_RULE_REGULATION':2,'DISCOVERY':1}.get(row.get('query_origin'),0)
    nexus=0 if row.get('case_nexus_status') == 'NO_CASE_NEXUS' else 1
    return (1 if same_identity else 0, 1 if requested else 0, nexus, origin, float(row.get('relevance_score') or 0.0))


def _verification_identity_key(row: dict) -> str:
    qid=regulation_identity(row.get('query') or '')
    if qid.get('key'):
        return str(qid['key'])
    tid=regulation_identity(row.get('title') or '')
    if tid.get('key'):
        return str(tid['key'])
    return str(row.get('url') or '')


def _expected_identity_key_for_fulltext(row: dict) -> str | None:
    binding=row.get('provision_binding_provenance') or {}
    bound=str(binding.get('instrument_key') or '').strip()
    if re.fullmatch(r'(?:UU|PP|PERMA|SEMA|PERPRES|POJK|SEOJK):[0-9]+[A-Za-z]?:(?:19|20)\d{2}', bound, re.I):
        return bound.upper().replace(':', ':', 1) if not bound.startswith(('UU:','PP:','PERMA:','SEMA:','PERPRES:','POJK:','SEOJK:')) else bound
    qid=regulation_identity(row.get('query') or '')
    if qid.get('key'):
        return str(qid['key'])
    tid=regulation_identity(row.get('title') or '')
    if tid.get('key'):
        return str(tid['key'])
    return None


def _identity_query_from_key(identity_key: str | None) -> str | None:
    m=re.fullmatch(r'(UU|PP|PERMA|SEMA|PERPRES|POJK|SEOJK):([0-9]+[A-Za-z]?):((?:19|20)\d{2})', str(identity_key or ''), re.I)
    if not m:
        return None
    kind=m.group(1).upper(); number=m.group(2); year=m.group(3)
    label={
        'UU':'Undang-Undang', 'PP':'Peraturan Pemerintah',
        'PERMA':'Peraturan Mahkamah Agung', 'SEMA':'Surat Edaran Mahkamah Agung',
        'PERPRES':'Peraturan Presiden', 'POJK':'Peraturan Otoritas Jasa Keuangan',
        'SEOJK':'Surat Edaran Otoritas Jasa Keuangan',
    }[kind]
    return f'{label} Nomor {number} Tahun {year}'




def _rebind_resolved_instrument_metadata(item: dict, resolved: dict) -> None:
    """Bind lawyer-facing metadata to the exact resolved official instrument.

    Discovery metadata is preserved separately for audit, but once an official
    fulltext is identity-aligned the displayed/verified instrument must follow
    that resolved identity rather than the search-result title that led to it.
    """
    key=str((resolved or {}).get('resolved_identity_key') or '').strip()
    if not key:
        return
    canonical_title=_identity_query_from_key(key)
    if not canonical_title:
        return
    if 'discovery_title' not in item:
        item['discovery_title']=item.get('title')
    if 'discovery_url' not in item:
        item['discovery_url']=item.get('url')
    item['canonical_instrument_key']=key
    item['canonical_title']=canonical_title
    item['title']=canonical_title
    if (resolved or {}).get('source_url'):
        item['resolved_source_url']=resolved.get('source_url')
        item['url']=resolved.get('source_url')
    item['document_classification']=classify_legal_document_candidate(item)
def _recover_expected_official_fulltext(expected_identity_key: str | None, requested_provisions, preferred_source_id: str | None = None, timeout: int = 5) -> dict:
    """Bounded exact-identity recovery after a mismatched official hit.

    The search-result URL is not evidence of instrument identity.  If an official
    result resolves to another statute, retry with an exact canonical instrument
    query and accept only a fulltext whose own text contains the expected key.
    This is retrieval recovery only; all legal gates remain in the verifier.
    """
    query=_identity_query_from_key(expected_identity_key)
    if not query:
        return {'resolved':False,'resolver_status':'RECOVERY_IDENTITY_UNAVAILABLE','attempted_urls':[]}
    kind=str(expected_identity_key or '').split(':',1)[0].upper()
    if kind in {'POJK','SEOJK'}:
        ids=['ojk','bpk','kemenkum']
    elif kind in {'PERMA','SEMA'}:
        ids=['ma','bpk','kemenkum']
    else:
        ids=['bpk','kemenkum','dpr','setneg']
    if preferred_source_id and preferred_source_id not in ids:
        ids.insert(0, preferred_source_id)
    try:
        bundles=federated_search(query, direct_ids=tuple(ids), per_source_limit=5)
    except Exception as exc:
        return {'resolved':False,'resolver_status':'RECOVERY_SEARCH_ERROR','error':str(exc)[:240],'attempted_urls':[]}
    rows=[]
    seen=set()
    for src in bundles or []:
        for row in src.get('results') or []:
            url=row.get('url') or ''
            if not url or url in seen:
                continue
            seen.add(url); rows.append((src.get('source_id'), row))
    attempted=[]
    for source_id,row in rows[:12]:
        url=row.get('url') or ''
        attempted.append(url)
        fetched=fetch_official_document(url, timeout=timeout)
        if not (fetched.get('reachable') and fetched.get('official_host')):
            continue
        resolved=resolve_official_fulltext(
            fetched.get('final_url') or url, fetched.get('body') or b'', fetched.get('content_type') or '',
            requested_provisions=requested_provisions or [], timeout=timeout, max_candidates=8,
            expected_identity_key=expected_identity_key)
        if resolved.get('resolved') and resolved.get('identity_aligned'):
            resolved=dict(resolved)
            resolved['resolver_status']='RECOVERED_EXACT_IDENTITY_'+str(resolved.get('resolver_status') or 'FULLTEXT')
            resolved['recovery_query']=query
            resolved['recovery_source_id']=source_id
            resolved['recovery_attempted_urls']=attempted
            return resolved
    return {
        'resolved':False,'resolver_status':'EXPECTED_IDENTITY_RECOVERY_FAILED',
        'expected_identity_key':expected_identity_key,'recovery_query':query,
        'attempted_urls':attempted,
    }


def _verify_positive_law_results(results: list[dict], snapshot: dict, max_documents: int = 10) -> list[dict]:
    """Verify only deterministic legal-instrument candidates.

    Official news, event, profile, and unidentified landing pages remain visible
    to diagnostics but do not consume the positive-law verification budget.
    The budget is selected per instrument identity, not per search hit, so
    duplicate URLs and malformed exact citations cannot starve valid statutes.
    """
    enriched=[]
    verified_budget=0
    fetch_map={}
    fetch_candidates=[]

    eligible=[]
    for idx,row in enumerate(results):
        classification=row.get('document_classification') or classify_legal_document_candidate(row)
        url=row.get('url') or ''
        if classification.get('legal_instrument_candidate') and row.get('authoritative') and url:
            eligible.append((idx,row))
    eligible.sort(key=lambda pair: _verification_candidate_priority(pair[1]), reverse=True)

    # Verification budget is per legal instrument identity, but one instrument can
    # have several official representations (detail page, preview, direct PDF).
    # Keeping only the first URL per identity can discard the one representation
    # that actually carries machine-readable full text.  Select a small, bounded
    # fallback set per identity while keeping the overall legal-instrument budget.
    grouped={}
    identity_order=[]
    for _idx,row in eligible:
        identity_key=_verification_identity_key(row)
        if identity_key not in grouped:
            grouped[identity_key]=[]
            identity_order.append(identity_key)
        grouped[identity_key].append(row)

    def _access_priority(row):
        url=str(row.get('url') or '').lower()
        title=str(row.get('title') or '').lower()
        direct_pdf=1 if url.split('?',1)[0].endswith('.pdf') else 0
        downloadish=1 if any(k in url for k in ('/download/','download?','/file/','/files/','attachment','lampiran')) else 0
        title_pdf=1 if '.pdf' in title or 'download' in title or 'unduh' in title else 0
        return (direct_pdf, downloadish, title_pdf, *_verification_candidate_priority(row))

    selected_urls=set(); selected_identities=set()
    max_urls_per_identity=3
    for identity_key in identity_order:
        if len(selected_identities) >= max_documents:
            break
        rows=sorted(grouped.get(identity_key) or [], key=_access_priority, reverse=True)
        if not rows:
            continue
        selected_identities.add(identity_key)
        for row in rows:
            if sum(1 for u in selected_urls if any((r.get('url') or '') == u for r in grouped.get(identity_key,[]))) >= max_urls_per_identity:
                break
            url=row.get('url') or ''
            if not url or url in selected_urls:
                continue
            selected_urls.add(url)
            fetch_candidates.append(url)
    if fetch_candidates:
        with ThreadPoolExecutor(max_workers=min(4,len(fetch_candidates))) as ex:
            futs={ex.submit(fetch_official_document,url,5):url for url in fetch_candidates}
            for fut in as_completed(futs):
                url=futs[fut]
                try: fetch_map[url]=fut.result()
                except Exception as exc:
                    fetch_map[url]={"url":url,"reachable":False,"official_host":True,"body":b"",
                                    "content_type":"","error":str(exc)[:240],"connectivity_status":"FETCH_ERROR"}
    for row in results:
        item=dict(row)
        classification=item.get('document_classification') or classify_legal_document_candidate(item)
        item['document_classification']=classification
        item['positive_law_verification']={
            'official_source_confirmed':bool(item.get('authoritative')),
            'text_retrieved':False,'identity_confirmed':False,
            'legal_status':'UNVERIFIED','tempus_status':'TEMPUS_UNVERIFIED',
            'case_nexus_status':item.get('case_nexus_status') or 'CASE_NEXUS_UNCERTAIN',
            'final_status':'UNVERIFIED','professional_verification':'PENDING',
        }
        if not classification.get('legal_instrument_candidate'):
            item['positive_law_verification'].update({
                'final_status':'REJECTED_NON_LEGAL_CONTENT',
                'diagnostic':classification.get('reason') or 'not a deterministic legal instrument candidate',
            })
            enriched.append(item)
            continue

        url=item.get('url') or ''
        if url in selected_urls and item.get('authoritative'):
            verified_budget += 1
            fetched=fetch_map.get(url) or fetch_official_document(url, timeout=5)
            item['document_fetch']={k:v for k,v in fetched.items() if k!='body'}
            if fetched.get('reachable') and fetched.get('official_host'):
                ctype=(fetched.get('content_type') or '').lower()
                body=fetched.get('body') or b''
                if 'html' in ctype:
                    text=html_to_text(body)
                    item['positive_law_verification']=verify_document_candidate(
                        item, source_text=text, snapshot=snapshot)
                    # Official search results frequently land on metadata/detail
                    # pages.  Identity, lifecycle status and the requested Pasal
                    # may exist only in the linked official PDF.  Resolve the
                    # full text BEFORE treating identity failure as final, then
                    # rerun the complete verifier on that authoritative text.
                    pv=item['positive_law_verification'].get('provision_verification') or {}
                    deterministic_route=item.get('query_origin') in {
                        'KNOWN_REGULATION','EXACT_CASE_REGULATION','DOMAIN_RULE_REGULATION'
                    } and bool(item.get('case_nexus_domains'))
                    needs_fulltext=(
                        (item['positive_law_verification'].get('case_nexus_status') != 'NO_CASE_NEXUS' or deterministic_route)
                        and (
                            item['positive_law_verification'].get('identity_confirmed') is not True
                            or (int(pv.get('requested_count') or 0) > int(pv.get('verified_count') or 0))
                        )
                    )
                    if needs_fulltext:
                        expected_identity_key=_expected_identity_key_for_fulltext(item)
                        resolved=resolve_official_fulltext(
                            fetched.get('final_url') or url, body, fetched.get('content_type') or '',
                            requested_provisions=item.get('requested_provisions') or [], timeout=5, max_candidates=2,
                            expected_identity_key=expected_identity_key)
                        if expected_identity_key and not (resolved.get('resolved') and resolved.get('identity_aligned')):
                            recovered=_recover_expected_official_fulltext(
                                expected_identity_key, item.get('requested_provisions') or [],
                                preferred_source_id=item.get('source_id'), timeout=5)
                            if recovered.get('resolved'):
                                resolved=recovered
                        item['fulltext_resolution']={k:v for k,v in resolved.items() if k!='text'}
                        if resolved.get('resolved') and resolved.get('text'):
                            resolved_candidate=dict(item)
                            if resolved.get('source_url'):
                                resolved_candidate['url']=resolved.get('source_url')
                            full_verified=verify_document_candidate(
                                resolved_candidate, source_text=resolved.get('text') or '', snapshot=snapshot)
                            full_verified['provision_source_url']=resolved.get('source_url')
                            full_verified['provision_source_status']=resolved.get('resolver_status')
                            full_verified['fulltext_reconciliation']={
                                'source_instrument_key': expected_identity_key,
                                'resolved_instrument_key': resolved.get('resolved_identity_key'),
                                'identity_aligned': bool(resolved.get('identity_aligned')),
                                'provision_binding_preserved': bool(item.get('provision_binding_provenance')),
                                'resolver_status': resolved.get('resolver_status'),
                            }
                            full_verified['legal_status_source_url']=resolved.get('source_url')
                            _rebind_resolved_instrument_metadata(item, resolved)
                            item['positive_law_verification']=full_verified
                    # Post-fulltext identity is the final legal-document gate.
                    if not item['positive_law_verification'].get('identity_confirmed'):
                        if item['positive_law_verification'].get('case_nexus_status') == 'NO_CASE_NEXUS':
                            item['positive_law_verification']['final_status']='VERIFIED_NOT_RELEVANT'
                            item['positive_law_verification']['diagnostic']='official legal content retrieved but rejected by the case-nexus gate; identity mismatch retained as a diagnostic, not as the final semantic state'
                        else:
                            item['positive_law_verification']['final_status']='UNVERIFIED_IDENTITY_MISMATCH'
                            item['positive_law_verification']['diagnostic']='official page retrieved, but regulation identity does not match the requested instrument'
                elif 'pdf' in ctype or str(fetched.get('final_url') or url).lower().split('?',1)[0].endswith('.pdf'):
                    expected_identity_key=_expected_identity_key_for_fulltext(item)
                    resolved=resolve_official_fulltext(
                        fetched.get('final_url') or url, body, fetched.get('content_type') or '',
                        requested_provisions=item.get('requested_provisions') or [], timeout=5, max_candidates=2,
                        expected_identity_key=expected_identity_key)
                    if expected_identity_key and not (resolved.get('resolved') and resolved.get('identity_aligned')):
                        recovered=_recover_expected_official_fulltext(
                            expected_identity_key, item.get('requested_provisions') or [],
                            preferred_source_id=item.get('source_id'), timeout=5)
                        if recovered.get('resolved'):
                            resolved=recovered
                    item['fulltext_resolution']={k:v for k,v in resolved.items() if k!='text'}
                    if resolved.get('resolved') and resolved.get('text'):
                        item['positive_law_verification']=verify_document_candidate(
                            item, source_text=resolved.get('text') or '', snapshot=snapshot)
                        item['positive_law_verification']['fulltext_reconciliation']={
                            'source_instrument_key': expected_identity_key,
                            'resolved_instrument_key': resolved.get('resolved_identity_key'),
                            'identity_aligned': bool(resolved.get('identity_aligned')),
                            'provision_binding_preserved': bool(item.get('provision_binding_provenance')),
                            'resolver_status': resolved.get('resolver_status'),
                        }
                        item['positive_law_verification']['legal_status_source_url']=resolved.get('source_url')
                        _rebind_resolved_instrument_metadata(item, resolved)
                        pv=item['positive_law_verification'].get('provision_verification') or {}
                        if pv.get('verified_count'):
                            item['positive_law_verification']['provision_source_url']=resolved.get('source_url')
                            item['positive_law_verification']['provision_source_status']=resolved.get('resolver_status')
                    else:
                        item['positive_law_verification'].update({
                            'text_retrieved':bool(body),'legal_status':'STATUS_UNCERTAIN',
                            'tempus_status':'TEMPUS_UNVERIFIED','final_status':'UNVERIFIED_IDENTITY_MISMATCH' if expected_identity_key else 'STATUS_UNCERTAIN',
                            'diagnostic':('official PDF retrieved but expected instrument identity was not confirmed' if expected_identity_key else 'official PDF retrieved but text extraction failed'),
                        })
                else:
                    item['positive_law_verification'].update({
                        'text_retrieved':bool(body),
                        'legal_status':'STATUS_UNCERTAIN',
                        'tempus_status':'TEMPUS_UNVERIFIED',
                        'final_status':'STATUS_UNCERTAIN',
                        'diagnostic':'official document retrieved but content type is unsupported for deterministic full-text verification',
                    })
            else:
                item['positive_law_verification'].update({
                    'transport_status':fetched.get('connectivity_status'),
                    'diagnostic':fetched.get('error') or 'official document fetch failed',
                })
        enriched.append(item)
    return enriched



def _summarize_positive_law_verification(results: list[dict]) -> dict:
    status_verified=0
    tempus_verified=0
    verified_applicable=0
    provision_requested=0
    provision_located=0
    provision_verified=0
    provision_documents_verified=0
    requested_pairs=set()
    located_pairs=set()
    verified_pairs=set()
    verified_documents=set()
    for r in results or []:
        if not isinstance(r,dict):
            continue
        v=r.get("positive_law_verification") or {}
        # Provision demand is a wiring/attempt metric, not a legal-status result.
        # Count exact case-bound provisions even when the official page could not
        # yet confirm instrument identity.  This keeps "Pasal yang diperiksa"
        # truthful about whether the provision pipeline received work, while the
        # verified counter remains fail-closed.
        pv=v.get("provision_verification") or {}
        ptv=v.get("provision_text_verification") or {}
        ptl=v.get("provision_text_location") or {}
        identity_key=_verification_identity_key(r)
        requested_refs=list(pv.get("requested") or r.get("requested_provisions") or [])
        for raw in requested_refs:
            ref=normalize_provision_ref(raw)
            if ref:
                requested_pairs.add((identity_key, ref.lower()))
        for raw in ptl.get("located") or []:
            ref=normalize_provision_ref(raw)
            if ref:
                located_pairs.add((identity_key, ref.lower()))
        for raw in ptv.get("verified") or []:
            ref=normalize_provision_ref(raw)
            if ref:
                verified_pairs.add((identity_key, ref.lower()))
        if ptv.get("status") in {"PROVISION_VERIFIED","PROVISION_PARTIALLY_VERIFIED"} and int(ptv.get("verified_count") or 0) > 0:
            verified_documents.add(identity_key)

        # Legal-status/tempus/applicability remain strict: no identity confirmation,
        # no promotion. Secondary research (including Hukumonline) never changes
        # these counters.
        if not v.get("identity_confirmed"):
            continue
        if v.get("legal_status") in {"IN_FORCE","AMENDED_IN_FORCE","REVOKED"}:
            status_verified += 1
        if v.get("tempus_status") in {"TEMPUS_VERIFIED","NOT_YET_EFFECTIVE","REVOKED_AT_TEMPUS"}:
            tempus_verified += 1
        if v.get("final_status") == "VERIFIED_APPLICABLE":
            verified_applicable += 1
    provision_requested=len(requested_pairs)
    provision_located=len(located_pairs)
    provision_verified=len(verified_pairs)
    provision_documents_verified=len(verified_documents)
    return {
        "positive_law_verified": status_verified,
        "tempus_verified": tempus_verified,
        "verified_applicable": verified_applicable,
        "temporal_verified_applicable": verified_applicable,
        "provision_requested": provision_requested,
        "provision_located": provision_located,
        "provision_verified": provision_verified,
        "provision_documents_verified": provision_documents_verified,
    }



def _collect_identity_verification_diagnostics(results: list[dict], limit: int = 8) -> list[dict]:
    """Return bounded diagnostics for located-but-unverified provisions.

    This is telemetry only. It must not promote identity, nexus, provision,
    legal-status, tempus, or applicability gates.
    """
    out=[]
    seen=set()
    for r in results or []:
        if not isinstance(r, dict):
            continue
        v=r.get("positive_law_verification") or {}
        ptl=v.get("provision_text_location") or {}
        pv=v.get("provision_verification") or {}
        located=[normalize_provision_ref(x) for x in (ptl.get("located") or [])]
        located=[x for x in located if x]
        if not located or int(pv.get("verified_count") or 0) > 0:
            continue
        identity=v.get("identity") or {}
        recon=v.get("fulltext_reconciliation") or {}
        binding=r.get("provision_binding_provenance") or {}
        expected_key=(identity.get("expected_key") or recon.get("source_instrument_key") or _verification_identity_key(r))
        resolved_key=(recon.get("resolved_instrument_key") or identity.get("key"))
        dedupe=(str(expected_key), tuple(x.lower() for x in located), str(r.get("url") or ""))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append({
            "expected_instrument_key": expected_key,
            "resolved_instrument_key": resolved_key,
            "identity_candidates": list(identity.get("actual_identity_candidates") or [])[:8],
            "identity_confirmed": bool(v.get("identity_confirmed")),
            "identity_match_reason": identity.get("match_reason"),
            "expected_identity_source": identity.get("expected_identity_source"),
            "case_nexus_status": v.get("case_nexus_status"),
            "requested_provisions": list(pv.get("requested") or r.get("requested_provisions") or []),
            "located_provisions": located,
            "provision_binding_preserved": bool(recon.get("provision_binding_preserved") or binding),
            "provision_binding_provenance": binding,
            "query_origin": r.get("query_origin"),
            "source_url": v.get("provision_source_url") or r.get("url"),
            "resolver_status": recon.get("resolver_status") or v.get("provision_source_status"),
            "final_status": v.get("final_status"),
        })
        if len(out) >= max(1, int(limit or 8)):
            break
    return out

def filter_regulatory_matches_for_domains(matches: list[dict], domains: list[dict]) -> list[dict]:
    """Hard-prune local seed matches that do not belong to active case domains."""
    active={d.get('id') for d in (domains or []) if isinstance(d,dict) and d.get('role') != 'SUPPORTING_ONLY'}
    if not active:
        return []
    vocab={
        'financial_services': ('bank','bpr','pojk','seojk','kredit','ojk'),
        'corruption': ('tipikor','korupsi','603','penyalahgunaan kewenangan'),
        'criminal': ('kuhp','kuhap','pidana','praperadilan','tersangka'),
        'civil_contract': ('kuhperdata','kitab undang-undang hukum perdata','hukum perdata','burgerlijk','bw','perikatan','perjanjian','wanprestasi','1365'),
        'employment': ('ketenagakerjaan','pkwt','phk','pesangon','pp 35'),
        'corporate': ('perseroan','direksi','komisaris','uu no. 40 tahun 2007'),
        'land_property': ('uupa','agraria','pertanahan','pendaftaran tanah','sertipikat','sertifikat','bpn'),
        'religious_court': ('peradilan agama','pengadilan agama','uu no. 7 tahun 1989','uu nomor 3 tahun 2006','pasal 49'),
        'civil_procedure': ('hir','rbg','rv','acara perdata','obscuur','plurium','kompetensi absolut'),
        'regional_government': ('bumd','perumda','pemerintah daerah'),
        'constitutional': ('uud 1945','konstitusi','mahkamah konstitusi'),
        'data_privacy': ('data pribadi','pelindungan data pribadi','ite','informasi elektronik','transaksi elektronik'),
        'bankruptcy': ('kepailitan','pkpu','pailit','pengadilan niaga'),
        'arbitration': ('arbitrase','bani','alternatif penyelesaian sengketa'),
        'consumer': ('perlindungan konsumen','klausula baku','pelaku usaha'),
        'administrative': ('ptun','tata usaha negara','administrasi pemerintahan','aaupb','upaya administratif'),
        'public_information': ('keterbukaan informasi publik','informasi publik','komisi informasi'),
        'investment': ('penanaman modal','investasi','bkpm','perizinan berusaha'),
    }
    allowed=tuple(k for domain in active for k in vocab.get(domain,()))
    exclusive={
        'financial_services':('pojk','seojk','perbankan','bank perkreditan rakyat','bank perekonomian rakyat','bpr'),
        'corruption':('tipikor','pemberantasan tindak pidana korupsi'),
        'criminal':('kuhp','kuhap','kitab undang-undang hukum pidana','acara pidana'),
        'employment':('ketenagakerjaan','pkwt','pemutusan hubungan kerja','hubungan industrial'),
        'land_property':('uupa','pendaftaran tanah','hak tanggungan','pertanahan','agraria'),
        'religious_court':('peradilan agama','pengadilan agama'),
        'bankruptcy':('kepailitan','pkpu'),
        'arbitration':('arbitrase','bani'),
        'data_privacy':('pelindungan data pribadi','informasi dan transaksi elektronik'),
        'administrative':('peradilan tata usaha negara','administrasi pemerintahan'),
        'public_information':('keterbukaan informasi publik',),
        'investment':('penanaman modal',),
    }
    out=[]
    for row in matches or []:
        if not isinstance(row,dict): continue
        reg=row.get('regulation') or {}
        tags=' '.join(reg.get('domain_tags') or []).lower()
        hay=' '.join(str(reg.get(k) or '') for k in ('id','nomor','tentang','qualified_citation')).lower()+' '+tags
        hay += ' ' + ' '.join(str(a.get('pasal') or a.get('topic') or '') for a in (row.get('matched_articles') or []) if isinstance(a,dict)).lower()
        blocked=False
        for required,markers in exclusive.items():
            if required not in active and any(m in hay for m in markers):
                blocked=True; break
        if blocked: continue
        if allowed and any(k in hay for k in allowed):
            out.append(row)
    return out[:8]



def _database_matches_for_domains(text: str, domains: list[dict], limit: int = 10) -> list[dict]:
    """Retrieve the persisted SQLite corpus, constrained by the immutable domain contract."""
    rule_map={r['id']:r for r in DOMAIN_RULES}
    active=[d for d in (domains or []) if isinstance(d,dict) and d.get('role') != 'SUPPORTING_ONLY']
    merged={}
    for d in active[:4]:
        queries=list(rule_map.get(d.get('id'),{}).get('queries',()))[:2]
        if not queries: queries=[d.get('label') or d.get('id')]
        for q in queries:
            try:
                db_rows=RegulatoryCorpusManager.search(q,limit=max(limit,12))
            except Exception:
                # Direct unit use may occur before Flask startup initialized schema.
                # App startup normally creates/syncs the persistent corpus; fall back
                # to legacy seed matches rather than failing the Case Analysis.
                return []
            for reg in db_rows:
                rid=reg.get('id')
                if not rid: continue
                # Article relevance is computed only inside the already domain-gated regulation.
                terms=[t for t in re.findall(r'[\w-]+',(q or '').lower(),flags=re.UNICODE) if len(t)>2]
                arts=[]
                for a in reg.get('articles',[]) or []:
                    if not isinstance(a,dict): continue
                    hay=' '.join(str(a.get(k) or '') for k in ('pasal','topic','content')).lower()+' '+' '.join(a.get('keywords',[]) or []).lower()
                    score=sum(1 for t in terms if t in hay)
                    if score: arts.append((score,a))
                arts=[a for _,a in sorted(arts,key=lambda x:x[0],reverse=True)[:4]]
                row={'regulation':reg,'matched_articles':arts,'score':max(1,len(arts)*3),'source':'SQLITE_REGULATORY_CORPUS',
                     'verification_status':'LOCAL_DATABASE_MATCH — OFFICIAL SOURCE VERIFICATION REQUIRED','professional_verification':'PENDING'}
                if rid not in merged or row['score']>merged[rid]['score']: merged[rid]=row
    rows=filter_regulatory_matches_for_domains(list(merged.values()),active)
    return rows[:limit]


def retrieve_for_case_dynamic(*, text: str, title: str, provision_refs=None, qualified_queries=None,
                              local_seed_matches=None, legal_issues=None, online: bool = True,
                              retrieval_mode: str | None = None, domain_classification: dict | None = None) -> dict:
    mode_requested=(retrieval_mode or ('hybrid' if online else 'offline')).strip().lower()
    if mode_requested not in ('offline','online','hybrid'):
        mode_requested='hybrid'
    online = mode_requested in ('online','hybrid')
    if domain_classification:
        rule_map={r['id']:r for r in DOMAIN_RULES}
        domains=[]
        for d in domain_classification.get('domains',[]) or []:
            rid=d.get('id'); rule=rule_map.get(rid,{})
            domains.append({'id':rid,'label':d.get('label') or rule.get('label') or rid,'confidence':round(float(d.get('confidence',0))/100.0,2),'role':d.get('role','SECONDARY'),'signal_score':d.get('score',0),'source_ids':list(rule.get('sources',('bpk','ma'))),'signals':[]})
    else:
        domains = detect_domains(text)
    local_database_matches = _database_matches_for_domains(text, domains, limit=10) if mode_requested in ('offline','hybrid') else []
    event_year = detect_material_year(text)
    event_date = detect_material_date(text)
    date_candidates = detect_case_dates(text)
    procedural_dates=sorted([x.get('date') for x in date_candidates if x.get('role')=='procedural_or_filing' and x.get('date')])
    procedural_date = procedural_dates[0] if procedural_dates else None
    procedural_year = int(procedural_date[:4]) if procedural_date else None
    source_bindings=_extract_case_regulation_bindings(text)
    source_exact_queries=[_clean(x.get('query') or '') for x in source_bindings if _clean(x.get('query') or '')]
    queries = _dedupe(source_exact_queries + build_case_queries(text, title, provision_refs, domains, qualified_queries, legal_issues), 10)
    case_exact_queries = _case_exact_regulation_queries(provision_refs, qualified_queries, text=text)
    case_binding_map = _case_binding_provision_map(text)
    legacy_seed = filter_regulatory_matches_for_domains(list(local_seed_matches or []), domains)[:4]
    local_seed_matches = local_database_matches or legacy_seed
    official = {"bundles": [], "results": [], "source_ids": _source_ids_for_domains(domains),
                "funnel": {"discovered":0,"unique_discovered":0,"candidate":0,"materially_relevant":0,"temporal_not_excluded":0,"authoritative_source_located":0,"legal_document_candidates":0,"rejected_non_legal_content":0,"positive_law_verified":0,"tempus_verified":0,"verified_applicable":0,"temporal_verified_applicable":0,"provision_requested":0,"provision_located":0,"provision_verified":0,"provision_documents_verified":0}}
    error = None
    supplementary={"provider":"Hukumonline","authoritative":False,"results":[],"bundles":[],"reference_url":"https://www.hukumonline.com/pusatdata/","error":None}
    if online:
        try:
            official = _compact_searches(queries, domains, event_year, procedural_year, case_exact_queries=case_exact_queries)
        except Exception as exc:
            error = str(exc)[:300]
        # Secondary research is deferred until AFTER positive-law verification.
        # Official identity/provision verification is the critical path and must
        # not lose the request time budget to optional corroboration.

    results = official.get("results", [])
    results = _attach_requested_provisions(results, provision_refs, local_database_matches, qualified_queries=qualified_queries, case_exact_queries=case_exact_queries, case_binding_map=case_binding_map)
    verification_snapshot = {
        "event_year_candidate": event_year,
        "event_date_candidate": event_date,
        "procedural_date_candidate": procedural_date,
    }
    if online and results:
        results = _verify_positive_law_results(results, verification_snapshot, max_documents=10)
        official["results"] = results
        funnel = official.get("funnel") or {}
        funnel.update(_summarize_positive_law_verification(results))
        official["verification_diagnostics"] = _collect_identity_verification_diagnostics(results, limit=8)
    if online:
        # Optional corroboration runs last and with a small bounded budget.
        # A timeout/failure here never blocks the completed official-law result.
        try:
            secondary_queries=_dedupe(source_exact_queries + queries[:2], 3)
            secondary_map=supplementary_search_many(secondary_queries, per_source_limit=3, max_workers=2, time_budget_seconds=4.0)
            sec_results=[]; sec_bundles=[]; seen_sec=set()
            for q in secondary_queries:
                rows=secondary_map.get(q,[])
                sec_bundles.append({'query':q,'sources':rows})
                for src in rows:
                    for sec_item in src.get('results') or []:
                        sec_url=sec_item.get('url') or ''
                        if not sec_url or sec_url in seen_sec: continue
                        seen_sec.add(sec_url)
                        sec_results.append({'title':_clean(sec_item.get('title') or '')[:360],'url':sec_url,'query':q,
                                            'source_id':src.get('source_id'),'source_name':src.get('source_name'),
                                            'authoritative':False,'secondary_only':True,'use':'CORROBORATION_OR_RESEARCH_ONLY'})
            supplementary.update({'results':sec_results[:12],'bundles':sec_bundles,
                                  'reachable':any(src.get('reachable') for b in sec_bundles for src in b.get('sources',[]))})
        except Exception as exc:
            supplementary['error']=str(exc)[:300]
    mode = {"offline":"LOCAL_DATABASE_ONLY","online":"OFFICIAL_ONLINE_ONLY","hybrid":"HYBRID_LOCAL_OFFICIAL"}.get(mode_requested,"HYBRID_LOCAL_OFFICIAL")
    if online and not results:
        mode = mode + "_NO_MATERIAL_ONLINE_MATCH"
    payload = {
        "mode": mode, "retrieval_mode": mode_requested, "domains": domains, "queries": queries,
        "event_year_candidate": event_year, "event_date_candidate": event_date, "procedural_date_candidate": procedural_date, "date_candidates": date_candidates,
        "official_results": results, "search_bundles": official.get("bundles", []),
        "official_source_ids": list(official.get("source_ids", [])),
        "case_regulation_bindings": source_bindings,
        "secondary_legal_research": supplementary,
        "retrieval_funnel": official.get("funnel", {}),
        "verification_diagnostics": official.get("verification_diagnostics", []),
        "local_seed_matches": local_seed_matches, "local_database_results": local_database_matches,
        "official_results_count": len(results), "local_seed_count": len(local_seed_matches), "local_database_count": len(local_database_matches),
        "fetched_at": datetime.now(timezone.utc).isoformat(), "professional_verification": "PENDING",
        "cache_policy": "CASE_SCOPED_METADATA_ONLY", "error": error,
        "temporal_disclaimer": "Filter tempus ini adalah screening awal. Berlaku/tidak berlakunya norma wajib diverifikasi pada naskah resmi dan ketentuan peralihan.",
        "secondary_source_disclaimer": "Hukumonline digunakan hanya sebagai sumber riset sekunder/corroboration. Ia tidak menggantikan JDIH atau repository resmi dan tidak dapat sendiri menaikkan status norma menjadi VERIFIED_APPLICABLE.",
    }
    material = json.dumps({k: payload[k] for k in ("domains", "queries", "event_year_candidate", "event_date_candidate", "official_results", "retrieval_funnel")}, ensure_ascii=False, sort_keys=True)
    payload["content_hash"] = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return payload
