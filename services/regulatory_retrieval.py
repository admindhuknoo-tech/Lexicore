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
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Iterable

from legal_sources import federated_search, federated_search_many, supplementary_search_many, fetch_official_document, resolve_official_fulltext
from services.positive_law_verification import html_to_text, verify_document_candidate, verify_provisions, locate_provisions, classify_legal_document_candidate, regulation_identity, evaluate_case_nexus, normalize_provision_ref, apply_post_verification_status_semantics
from services.case_domain_classifier import classify_case
from services.official_identity_resolver import exact_query_variants, rank_candidates
from services.instrument_identity_contract import evaluate_instrument_identity_contract
from services.material_tempus_extractor import extract_material_tempus_candidates, select_material_tempus
from database import RegulatoryCorpusManager
from retrieval.search_router import LexiCoreLawRetrievalRouter

logger=logging.getLogger(__name__)


def _law_weight_config_path():
    return Path(__file__).resolve().parent.parent / "retrieval" / "law_weight_config.json"


def load_law_weight_config() -> dict:
    """Load the bounded retrieval-weight contract. Fail closed to neutral weights."""
    try:
        data=json.loads(_law_weight_config_path().read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except Exception as exc:
        logger.warning("law weight config unavailable: %s", exc)
        return {}


def _candidate_text_for_weighting(row: dict) -> str:
    # Deliberately exclude the query string: a broad/correct query must not
    # launder an unrelated search hit into a materially relevant law candidate.
    return _clean(" ".join(str(row.get(k) or "") for k in ("title","description","snippet"))).lower()


def evaluate_law_weight_policy(row: dict, domains: list[dict], config: dict | None = None) -> dict:
    """Apply the retrieval-only positive-allow policy.

    This function is intentionally a compatibility facade for callers in the
    regulatory retrieval service.  The policy itself lives in
    ``retrieval/search_router.py`` and has no authority to mark a norm
    applicable, temporally valid, or governing.
    """
    if config is None:
        router=LexiCoreLawRetrievalRouter(_law_weight_config_path())
    else:
        # Avoid mutating the frozen config file merely to test/inject a policy.
        router=LexiCoreLawRetrievalRouter.__new__(LexiCoreLawRetrievalRouter)
        router.config_path=_law_weight_config_path()
        router.config=config
    decision=router.evaluate_candidate(row,domains)
    # Backwards-compatible diagnostic aliases used by existing report/tests.
    decision.setdefault("strong_positive_hits", [h for h in decision.get("positive_hits",[]) if ":strong:" in h])
    decision.setdefault("disqualifying_hits", list(decision.get("hard_drop_reasons",[])) + list(decision.get("degraded_reasons",[])))
    decision.setdefault("exact_identity_match", False)
    return decision

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
        "queries": ("UU Ketenagakerjaan PHK pesangon", "PP 35 Tahun 2021 PKWT PHK", "UU Penyelesaian Perselisihan Hubungan Industrial bipartit mediasi PHK"),
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
        "queries": ("KUHPerdata Pasal 1238 1243 wanprestasi somasi", "KUHPerdata Pasal 1320 1338 syarat sah perjanjian itikad baik", "KUHPerdata Pasal 1365 perbuatan melawan hukum ganti rugi"),
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
        "id": "electoral_ethics", "label": "Pemilu / Pilkada / Etik Penyelenggara",
        "keywords": {"dkpp":6.0,"dewan kehormatan penyelenggara pemilu":6.0,"kode etik":5.0,"pelanggaran kode etik":6.0,"kpu":4.0,"bawaslu":4.0,"pemilihan umum":5.0,"pemilu":5.0,"pilkada":5.0,"pengadu":3.0,"teradu":3.0},
        "sources": ("bpk", "kemenkum", "kemendagri"),
        "queries": ("UU 7 Tahun 2017 Pemilihan Umum penyelenggara pemilu kode etik DKPP", "UU 1 Tahun 2015 Pemilihan Gubernur Bupati Walikota", "Peraturan DKPP Nomor 2 Tahun 2019 Kode Etik Pedoman Perilaku Penyelenggara Pemilu"),
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
    """Return one defensible material-event year, or ``None``.

    R30 delegates candidate extraction to the dedicated fail-closed tempus
    extractor. Discovery never means verified applicability.
    """
    selected=select_material_tempus(text)
    if selected.get('status') != 'MATERIAL_TEMPUS_CANDIDATE':
        return None
    value=str(selected.get('value') or '')
    m=re.match(r"(19\d{2}|20\d{2})",value)
    return int(m.group(1)) if m else None


def material_tempus_candidates(text: str) -> list[dict]:
    """Public diagnostic accessor for ranked material-tempus candidates."""
    return extract_material_tempus_candidates(text)



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
    """Return a defensible exact material-event date, never filing/process dates."""
    selected=select_material_tempus(text)
    if selected.get('status') == 'MATERIAL_TEMPUS_CANDIDATE' and selected.get('precision') == 'date':
        return str(selected.get('value'))
    return None


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
        "Peraturan Pemerintah Nomor 35 Tahun 2021 tentang Perjanjian Kerja Waktu Tertentu Alih Daya Waktu Kerja dan Waktu Istirahat dan Pemutusan Hubungan Kerja",
        "Undang-Undang Nomor 2 Tahun 2004 tentang Penyelesaian Perselisihan Hubungan Industrial",
        "Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-Undang",
    ),
    "corruption": (
        "Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "Undang-Undang Nomor 20 Tahun 2001 tentang Perubahan atas Undang-Undang Nomor 31 Tahun 1999 tentang Pemberantasan Tindak Pidana Korupsi",
        "Undang-Undang Nomor 30 Tahun 2002 tentang Komisi Pemberantasan Tindak Pidana Korupsi",
    ),
    "criminal": (
        "Undang-Undang Nomor 20 Tahun 2025 tentang Kitab Undang-Undang Hukum Acara Pidana",
        "Undang-Undang Nomor 1 Tahun 2023 tentang Kitab Undang-Undang Hukum Pidana",
        "Undang-Undang Nomor 1 Tahun 2026 tentang Penyesuaian Pidana",
    ),
    "civil_contract": (
        "Kitab Undang-Undang Hukum Perdata Burgerlijk Wetboek",
        "KUHPerdata Pasal 1238 Pasal 1243 wanprestasi dan ganti rugi",
        "KUHPerdata Pasal 1365 perbuatan melawan hukum dan ganti rugi",
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
    "electoral_ethics": (
        "Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum",
        "Undang-Undang Nomor 1 Tahun 2015 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 1 Tahun 2014 tentang Pemilihan Gubernur, Bupati, dan Walikota Menjadi Undang-Undang",
        "Undang-Undang Nomor 10 Tahun 2016 tentang Perubahan Kedua atas Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota",
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
    "civil_contract": ("kitab undang-undang hukum perdata", "kuhperdata", "burgerlijk wetboek", "wanprestasi", "perbuatan melawan hukum"),
    "land_property": ("pokok-pokok agraria", "pendaftaran tanah", "pertanahan", "agraria"),
    "religious_court": ("peradilan agama", "pengadilan agama"),
    "civil_procedure": ("hukum acara perdata", "perma", "sema"),
    "employment": ("ketenagakerjaan", "pemutusan hubungan kerja", "pkwt", "pkwtt"),
    "electoral_ethics": ("pemilihan umum", "pemilihan gubernur", "pilkada", "dkpp", "kode etik", "penyelenggara pemilu"),
    "administrative": ("peradilan tata usaha negara", "administrasi pemerintahan", "ptun"),
    "public_information": ("keterbukaan informasi publik",),
    "investment": ("penanaman modal",),
    "consumer": ("perlindungan konsumen",),
    "bankruptcy": ("kepailitan", "penundaan kewajiban pembayaran utang", "pkpu"),
    "arbitration": ("arbitrase", "alternatif penyelesaian sengketa"),
    "data_privacy": ("pelindungan data pribadi", "informasi dan transaksi elektronik"),
}

SUBJECT_FAMILY_MARKERS = {
    "electoral_ethics": ("pemilihan umum", "pemilu", "pilkada", "pemilihan gubernur", "pemilihan bupati", "pemilihan walikota", "kpu", "bawaslu", "dkpp", "kode etik penyelenggara"),
    "corruption": ("pemberantasan tindak pidana korupsi", "komisi pemberantasan tindak pidana korupsi", "kpk", "tipikor"),
    "financial_services": ("perbankan", "bank perkreditan rakyat", "bank perekonomian rakyat", "otoritas jasa keuangan"),
    "employment": ("ketenagakerjaan", "hubungan industrial", "pemutusan hubungan kerja", "pkwt"),
    "land_property": ("agraria", "pendaftaran tanah", "hak atas tanah", "pertanahan"),
    "corporate": ("perseroan terbatas",),
    "consumer": ("perlindungan konsumen",),
    "data_privacy": ("pelindungan data pribadi", "informasi dan transaksi elektronik"),
}

def _instrument_subject_families(value: str) -> set[str]:
    low=_clean(value).lower()
    return {family for family,markers in SUBJECT_FAMILY_MARKERS.items() if any(m in low for m in markers)}

def _exact_subject_family_consistent(query: str, candidate_title: str) -> bool:
    """Fail closed only on a strong cross-family contradiction.

    Identity number/year is still verified separately.  This guard prevents an
    exact case citation in one legal family (e.g. Pilkada) from being promoted
    through a search result whose title clearly belongs to another family (e.g.
    KPK) merely because it references the same regulation number/year.
    Ambiguous titles are retained for the normal identity/fulltext verifier.
    """
    qf=_instrument_subject_families(query)
    tf=_instrument_subject_families(candidate_title)
    if not qf or not tf:
        return True
    return bool(qf & tf)

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
        r"|(?:Peraturan Pemerintah Pengganti Undang-Undang|Peraturan Pemerintah Pengganti Undang undang|PERPPU|PERPU)\s+(?:Nomor|No\.?)\s*\d+[A-Za-z]?\s+Tahun\s+\d{4}"
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



def _build_exact_case_verification_rows(source_bindings: list[dict], domains: list[dict], event_year: int | None) -> list[dict]:
    """Build first-class deterministic verification rows from case citations.

    Exact case-bound instruments must not depend on federated discovery recall.
    A canonical official-registry URL is used as a fetch seed only; all normal
    official-host, identity, status, tempus, nexus and provision gates still run.
    If no canonical seed is available the binding is left to the existing
    recovery/discovery path rather than inventing an authoritative URL.
    """
    rows=[]
    seen=set()
    active_domain_ids=[str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"]
    for binding in source_bindings or []:
        ident=(binding.get("identity") or {}).get("key")
        provisions=[normalize_provision_ref(x) for x in (binding.get("provisions") or [])]
        provisions=[x for x in provisions if x]
        if not ident or not provisions or ident in seen:
            continue
        seen.add(ident)
        seeds=[]
        try:
            seeds=_canonical_official_seed_candidates(ident)
        except Exception:
            seeds=[]
        if not seeds:
            continue
        seed_source_id,seed=seeds[0]
        query=_clean(binding.get("query") or seed.get("query") or _identity_query_from_key(ident))
        row={
            "title":_clean(seed.get("title") or query)[:360],
            "description":_clean(seed.get("description") or "")[:700],
            "url":seed.get("url") or "",
            "source_id":seed_source_id or "local_corpus",
            "source_name":seed.get("source_name") or "Canonical official registry exact-job seed",
            "authoritative":True,
            "query":query,
            "source_score":100.0,
            "relevance_score":1.0,
            "query_origin":"EXACT_CASE_REGULATION",
            "exact_verification_job":True,
            "expected_identity_key":ident,
            "requested_provisions":provisions[:8],
            "provision_binding_provenance":{
                "exact_case_text":provisions[:8],
                "qualified_case_citation":[],
                "generated_research_refs":[],
                "case_bound":True,
                "instrument_key":ident,
                "expected_query_identity_key":ident,
                "actual_candidate_identity_key":None,
                "identity_alignment":"UNVERIFIED",
                "eligible_for_identity_verification":True,
                "verification_job":"DETERMINISTIC_EXACT_CASE_CITATION",
            },
        }
        exact_domains=_exact_case_query_domains(query,domains)
        row["case_nexus_domains"]=list(dict.fromkeys(exact_domains or active_domain_ids))
        row["case_nexus_status"]="CASE_NEXUS_VERIFIED" if row["case_nexus_domains"] else "CASE_NEXUS_UNCERTAIN"
        row["case_nexus_reason"]="first-class deterministic exact case citation verification job"
        row["document_classification"]=classify_legal_document_candidate(row)
        row["temporal_anchor"]="MATERIAL_EVENT"
        row["temporal_status"]=_temporal_screen(row,event_year)
        rows.append(row)
    return rows

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
    # Feed the bounded lexical/vector-like relevance computed above into the
    # separate router. The router may rank/degrade/drop only; it cannot verify
    # legal applicability.
    policy=evaluate_law_weight_policy({**row,"initial_vector_score":max(0.0,min(score,1.0))}, domains)
    if policy.get("status") == "POSITIVE_NEXUS_VERIFIED":
        score=max(score,float(policy.get("final_retrieval_score") or 0.0))
    else:
        score=min(score,float(policy.get("final_retrieval_score") or score))
    return round(max(0.0,min(score, 1.0)), 3)


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
                if _clean(query).lower() in case_exact_queries:
                    # R32: exact-case discovery must satisfy the metadata identity
                    # contract before it can become a verification candidate.
                    # Ambiguous metadata is retained; explicit type/number-year/
                    # subject-family/domain contradictions are rejected.
                    active_domain_ids=[str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"]
                    expected_key=regulation_identity(query).get("key")
                    contract=evaluate_instrument_identity_contract(
                        expected_key, row, expected_text=query, active_domains=active_domain_ids, phase="PREFETCH")
                    row["instrument_identity_contract"]=contract
                    if not contract.get("passed"):
                        continue
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
                row["law_weight_policy"] = evaluate_law_weight_policy(row, domains)
                # Backlog B: positive-allow candidate admission. Exact case-bound
                # citations are preserved for identity verification; other discovery
                # hits must prove subject-matter relevance from their own title/text.
                if row["query_origin"] != "EXACT_CASE_REGULATION" and row["law_weight_policy"].get("status") != "POSITIVE_NEXUS_VERIFIED":
                    continue
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
        # R35 recall guard: every exact case-bound instrument with a canonical
        # official URL in the verified local registry gets one deterministic
        # seed candidate.  This is generic and prevents search-engine recall
        # variance from dropping the exact statute (for example when a same-
        # number PKPU ranks ahead of a UU).  The seed still goes through all
        # normal fetch, full-text identity, status, tempus and provision gates.
        if _clean(query).lower() in case_exact_queries:
            expected_key=regulation_identity(query).get("key")
            seed_rows=[]
            try:
                seed_rows=_canonical_official_seed_candidates(expected_key)
            except Exception:
                seed_rows=[]
            for seed_source_id, seed in seed_rows[:1]:
                seed_url=seed.get("url") or ""
                if not seed_url or seed_url in seen_urls:
                    continue
                seen_urls.add(seed_url)
                row={
                    "title":_clean(seed.get("title", ""))[:360],
                    "description":_clean(seed.get("description", ""))[:700],
                    "url":seed_url,
                    "source_id":seed_source_id or "local_corpus",
                    "source_name":seed.get("source_name") or "Canonical official registry seed",
                    "authoritative":True,
                    "query":query,
                    "source_score":99.0,
                    "query_origin":"EXACT_CASE_REGULATION",
                }
                active_domain_ids=[str(d.get("id")) for d in (domains or []) if isinstance(d,dict) and d.get("role") != "SUPPORTING_ONLY"]
                contract=evaluate_instrument_identity_contract(
                    expected_key,row,expected_text=query,active_domains=active_domain_ids,phase="PREFETCH")
                row["instrument_identity_contract"]=contract
                if not contract.get("passed"):
                    continue
                row["relevance_score"]=1.0
                exact_case_domains=_exact_case_query_domains(query,domains)
                row["case_nexus_domains"]=list(dict.fromkeys(exact_case_domains or active_domain_ids))
                row["case_nexus_status"]="CASE_NEXUS_VERIFIED" if row["case_nexus_domains"] else "CASE_NEXUS_UNCERTAIN"
                row["case_nexus_reason"]="canonical official seed for exact case-bound regulation"
                row["document_classification"]=classify_legal_document_candidate(row)
                row["temporal_anchor"]="MATERIAL_EVENT"
                row["temporal_status"]=_temporal_screen(row,event_year)
                flat.append(row)
                compact_sources.append({
                    "source_id":row["source_id"],"source_name":row["source_name"],
                    "authoritative":True,"reachable":True,"http_status":None,"results":[row],
                })
        bundles.append({"query": query, "sources": compact_sources})

    origin_priority={"EXACT_CASE_REGULATION":4,"KNOWN_REGULATION":3,"DOMAIN_RULE_REGULATION":2,"DISCOVERY":1}
    flat.sort(key=lambda r: (origin_priority.get(r.get("query_origin"),0), r.get("relevance_score", 0), bool(r.get("authoritative"))), reverse=True)
    candidates = [r for r in flat if r.get("relevance_score", 0) >= 0.20]
    _law_cfg=load_law_weight_config()
    _material_threshold=float(((_law_cfg.get("thresholds") or {}).get("generic_material_min_score",0.38)) or 0.38)
    material = [r for r in candidates if r.get("relevance_score", 0) >= _material_threshold]
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
        query_identity=regulation_identity(item.get('query') or '')
        actual_key=_candidate_actual_identity_key(item)
        candidate_key=actual_key or query_identity.get('key')
        # R41: source-text provision bindings follow the candidate's actual
        # identity whenever that identity is knowable.  A neighbouring statute
        # returned by search must not inherit Pasal demand from the query.
        case_bound_refs=list(case_binding_map.get(candidate_key,[])) if candidate_key else []
        generated_qualified_refs=list(qualified_map.get(candidate_key,[])) if candidate_key else []
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
        if not refs and len(exact_ids) == 1 and candidate_key in exact_ids:
            refs=list(explicit)
        for entry in local:
            same_identity=bool(candidate_key and entry['identity'].get('key') == candidate_key)
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
            'instrument_key': candidate_key,
            'expected_query_identity_key': query_identity.get('key'),
            'actual_candidate_identity_key': actual_key,
            'identity_alignment': (
                'DIRECT_MATCH' if actual_key and query_identity.get('key') == actual_key
                else 'MISMATCH' if actual_key and query_identity.get('key') and query_identity.get('key') != actual_key
                else 'UNVERIFIED'
            ),
            'eligible_for_identity_verification': bool(
                str(item.get('query_origin') or '').upper() == 'EXACT_CASE_REGULATION'
                and query_identity.get('key')
                and not actual_key
                and (case_bound_refs or qualified_bound_refs)
            ),
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


def _candidate_actual_identity_key(row: dict) -> str | None:
    """Return the identity carried by the discovery result itself.

    R41 keeps query expectation separate from candidate identity.  A search hit
    for another regulation must not inherit the case-bound identity merely
    because it was returned for an exact-regulation query.
    """
    canonical=str(row.get('canonical_instrument_key') or '').strip()
    if canonical:
        return canonical
    for raw in (row.get('title'), row.get('discovery_title')):
        rid=regulation_identity(raw or '')
        if rid.get('key'):
            return str(rid['key'])
    # Official detail URLs often expose a deterministic slug even when a search
    # result title is truncated or generic.  Normalizing punctuation makes the
    # same public identity parser usable without site-specific statute numbers.
    url=str(row.get('url') or '')
    if url:
        slug=re.sub(r'[-_/%]+',' ',url)
        rid=regulation_identity(slug)
        if rid.get('key'):
            return str(rid['key'])
    return None


def _query_expected_identity_key(row: dict) -> str | None:
    qid=regulation_identity(row.get('query') or '')
    return str(qid['key']) if qid.get('key') else None


def _identity_alignment_state(row: dict) -> str:
    """R42 tri-state identity alignment for prefetch candidate handling.

    UNVERIFIED is materially different from MISMATCH: an exact case-bound
    candidate whose actual identity has not yet been established must survive
    long enough to reach official fetch/fulltext verification.
    """
    expected=_query_expected_identity_key(row)
    actual=_candidate_actual_identity_key(row)
    if not actual:
        return 'UNVERIFIED'
    if expected and actual == expected:
        return 'DIRECT_MATCH'
    if expected and actual != expected:
        return 'MISMATCH'
    return 'DIRECT_MATCH'


def _prefetch_identity_decision(row: dict, contract: dict | None = None) -> dict:
    """Single prefetch identity decision used by selection and processing.

    Exact case-bound candidates with unknown actual identity are preserved long
    enough to reach official fetch/fulltext verification.  Only a proven
    mismatch is rejected.  General discovery rows continue to follow the
    existing instrument-identity contract.
    """
    alignment=_identity_alignment_state(row)
    exact_case=_is_exact_case_verification_row(row)
    contract=contract or {}
    contract_passed=bool(contract.get('passed'))

    if alignment == 'MISMATCH' and str(row.get('query_origin') or '').upper() == 'EXACT_CASE_REGULATION':
        return {
            'alignment':alignment,
            'eligible':False,
            'preserved_unverified_exact':False,
            'reason':'PROVEN_EXACT_CASE_IDENTITY_MISMATCH',
        }

    if alignment == 'UNVERIFIED' and exact_case:
        binding=row.get('provision_binding_provenance') or {}
        expected=_query_expected_identity_key(row) or str(binding.get('instrument_key') or '').strip()
        # UNVERIFIED preservation requires provenance from the case text.
        # Query origin alone is insufficient because a wrong-type search hit
        # (for example a PKPU returned for an expected UU) may also inherit the
        # exact query label while its actual identity parser remains unknown.
        if expected and binding.get('case_bound'):
            return {
                'alignment':alignment,
                'eligible':True,
                'preserved_unverified_exact':True,
                'reason':'CASE_BOUND_EXACT_IDENTITY_PENDING_OFFICIAL_FETCH',
            }

    return {
        'alignment':alignment,
        'eligible':contract_passed,
        'preserved_unverified_exact':False,
        'reason':('IDENTITY_CONTRACT_PASSED' if contract_passed else 'IDENTITY_CONTRACT_REJECTED'),
    }


def _verification_identity_key(row: dict) -> str:
    # Verification grouping is keyed by the candidate's actual identity first.
    # An explicit query/title mismatch receives its own non-canonical budget key
    # so it cannot consume fallback URL slots reserved for an aligned candidate.
    actual=_candidate_actual_identity_key(row)
    expected=_query_expected_identity_key(row)
    alignment=_identity_alignment_state(row)
    if alignment == 'MISMATCH':
        return f'MISMATCH:{actual}<-{expected}:{row.get("url") or ""}'
    if alignment == 'UNVERIFIED' and expected and _is_exact_case_verification_row(row):
        # Preserve the exact case-bound slot until official identity verification.
        return expected
    if actual:
        return actual
    if expected:
        return expected
    return str(row.get('url') or '')


def _expected_identity_key_for_fulltext(row: dict) -> str | None:
    binding=row.get('provision_binding_provenance') or {}
    bound=str(binding.get('instrument_key') or '').strip()
    if binding.get('case_bound') and re.fullmatch(r'(?:UU|PP|PERMA|SEMA|PERPRES|POJK|SEOJK):[0-9]+[A-Za-z]?:(?:19|20)\d{2}', bound, re.I):
        return bound.upper().replace(':', ':', 1) if not bound.startswith(('UU:','PP:','PERMA:','SEMA:','PERPRES:','POJK:','SEOJK:')) else bound
    actual=_candidate_actual_identity_key(row)
    if actual:
        return actual
    return _query_expected_identity_key(row)


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
def _canonical_official_seed_candidates(expected_identity_key: str | None) -> list[tuple[str, dict]]:
    """Return exact local-corpus official URLs as fetch seeds, never as proof.

    The local URL is metadata only. It still has to be fetched from an official
    host and pass primary fulltext identity verification before use.
    """
    expected=str(expected_identity_key or '').strip().upper()
    if not expected:
        return []
    try:
        from regulatory_db import get_all_regulations
    except Exception:
        return []
    seeds=[]
    for reg in get_all_regulations() or []:
        title=' '.join(str(reg.get(k) or '') for k in ('nomor','tentang')).strip()
        rid=regulation_identity(title).get('key')
        if str(rid or '').upper() != expected:
            continue
        url=str(reg.get('official_url') or '').strip()
        if not url.startswith('http'):
            continue
        seeds.append(('local_corpus',{
            'title':str(reg.get('nomor') or title),
            'description':str(reg.get('tentang') or ''),
            'url':url,
            'query':_identity_query_from_key(expected),
            'relevance_score':99.0,
            'source_name':str(reg.get('jdih_source') or 'Local official metadata'),
        }))
    return seeds


def _recovery_candidate_metadata_rank(row: dict, expected_identity_key: str | None) -> tuple:
    """Compatibility rank: exact=3, auxiliary=2, ambiguous=1, wrong=-1."""
    ranked=rank_candidates(expected_identity_key, [(str((row or {}).get('source_id') or ''), row or {})])
    relevance=float((row or {}).get('relevance_score') or 0.0)
    if not ranked:
        return (-1, relevance)
    reason=ranked[0].reason
    return ({'EXACT_TITLE_IDENTITY':3,'AUX_EXPECTED_IDENTITY':2,'AMBIGUOUS_METADATA':1}.get(reason,1), relevance)


def _recover_expected_official_fulltext(expected_identity_key: str | None, requested_provisions, preferred_source_id: str | None = None, timeout: int = 4, time_budget_seconds: float = 4.0) -> dict:
    """Tightly bounded exact-identity recovery after a mismatched official hit.

    R19: seed the exact official URL already carried by the local corpus, then
    search a small set of exact-identity query variants. Metadata can rank a
    candidate, but only primary fulltext identity can verify it.
    """
    queries=exact_query_variants(expected_identity_key)
    if not queries:
        return {'resolved':False,'resolver_status':'RECOVERY_IDENTITY_UNAVAILABLE','attempted_urls':[]}
    query=queries[0]
    kind=str(expected_identity_key or '').split(':',1)[0].upper()
    if kind in {'POJK','SEOJK'}:
        ids=['ojk','bpk','kemenkum']
    elif kind in {'PERMA','SEMA'}:
        ids=['ma','bpk','kemenkum']
    else:
        ids=['bpk','kemenkum','dpr','setneg']
    if preferred_source_id and preferred_source_id not in ids:
        ids.insert(0, preferred_source_id)
    deadline=time.monotonic()+max(0.5,float(time_budget_seconds or 4.0))

    rows=_canonical_official_seed_candidates(expected_identity_key)
    seen={row.get('url') for _,row in rows if row.get('url')}
    # Search exact variants inside one bounded federation call. The canonical
    # corpus URL remains first-class but never bypasses official/fulltext gates.
    try:
        search_budget=min(2.5, max(0.5, deadline-time.monotonic()))
        sm=federated_search_many(queries, direct_ids=tuple(ids), per_source_limit=3, max_workers=4,
                                 time_budget_seconds=search_budget)
        for q in queries:
            for src in sm.get(q,[]) or []:
                for row in src.get('results') or []:
                    url=row.get('url') or ''
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    row=dict(row); row['query']=row.get('query') or q
                    rows.append((src.get('source_id'), row))
    except Exception as exc:
        if not rows:
            return {'resolved':False,'resolver_status':'RECOVERY_SEARCH_ERROR','error':str(exc)[:240],'attempted_urls':[]}

    ranked=rank_candidates(expected_identity_key, rows)

    # R20 invariant: once an exact-title identity candidate exists, legacy or
    # ambiguous candidates are not eligible to run ahead of it (or replace it)
    # inside the same recovery pass.  If the exact candidates cannot be fetched
    # or their PRIMARY fulltext identity fails, recovery fails closed instead of
    # silently falling back to a different instrument that merely references the
    # expected law in metadata/snippets.
    exact_ranked=[
        cand for cand in ranked
        if cand.reason == 'EXACT_TITLE_IDENTITY'
        and str(cand.title_identity or '').upper() == str(expected_identity_key or '').upper()
    ]
    recovery_pool=exact_ranked if exact_ranked else ranked
    exact_lock=bool(exact_ranked)
    logger.info(
        'official recovery expected=%s total_ranked=%s exact=%s exact_lock=%s',
        expected_identity_key, len(ranked), len(exact_ranked), exact_lock)
    candidate_trace=[{
        'rank':idx,
        'source_id':cand.source_id,
        'reason':cand.reason,
        'title_identity':cand.title_identity,
        'title':str((cand.row or {}).get('title') or '')[:180],
        'url':str((cand.row or {}).get('url') or '')[:260],
        'score':cand.score,
    } for idx,cand in enumerate(recovery_pool[:6])]

    attempted=[]
    # Preserve the performance contract: normal/fulltext hot path remains
    # max_candidates=2.  Recovery examines at most two exact candidates when
    # exact metadata is available; otherwise the legacy bounded pool remains
    # capped at four.
    recovery_fetch_cap=2 if exact_lock else 4
    for idx,cand in enumerate(recovery_pool[:recovery_fetch_cap]):
        logger.info(
            'official recovery candidate[%s] expected=%s reason=%s title_identity=%s title=%s url=%s',
            idx, expected_identity_key, cand.reason, cand.title_identity,
            str((cand.row or {}).get('title') or '')[:100],
            str((cand.row or {}).get('url') or '')[:180])
        remaining=deadline-time.monotonic()
        if remaining <= 0.75:
            break
        row=cand.row; source_id=cand.source_id
        url=row.get('url') or ''
        if not url:
            continue
        attempted.append(url)
        call_timeout=max(1,min(int(timeout or 4), int(max(1,remaining))))
        fetched=fetch_official_document(url, timeout=call_timeout)
        if not (fetched.get('reachable') and fetched.get('official_host')):
            continue
        remaining=deadline-time.monotonic()
        if remaining <= 0.75:
            break
        resolved=resolve_official_fulltext(
            fetched.get('final_url') or url, fetched.get('body') or b'', fetched.get('content_type') or '',
            requested_provisions=requested_provisions or [], timeout=max(1,min(call_timeout,int(max(1,remaining)))), max_candidates=2,
            expected_identity_key=expected_identity_key)
        if _resolved_fulltext_satisfies_provision_contract(resolved, requested_provisions):
            resolved=dict(resolved)
            resolved['resolver_status']='RECOVERED_EXACT_IDENTITY_'+str(resolved.get('resolver_status') or 'FULLTEXT')
            resolved['recovery_query']=query
            resolved['recovery_query_variants']=queries
            resolved['recovery_source_id']=source_id
            resolved['recovery_rank_reason']=cand.reason
            resolved['recovery_attempted_urls']=attempted
            resolved['recovery_exact_lock']=exact_lock
            resolved['recovery_exact_candidate_count']=len(exact_ranked)
            resolved['recovery_candidate_trace']=candidate_trace
            return resolved
    return {
        'resolved':False,
        'resolver_status':('EXPECTED_IDENTITY_EXACT_CANDIDATE_FAILED' if exact_lock else 'EXPECTED_IDENTITY_RECOVERY_FAILED'),
        'expected_identity_key':expected_identity_key,'recovery_query':query,
        'recovery_query_variants':queries,'attempted_urls':attempted,
        'recovery_exact_lock':exact_lock,
        'recovery_exact_candidate_count':len(exact_ranked),
        'recovery_candidate_trace':candidate_trace,
        'recovery_budget_exhausted': time.monotonic() >= deadline,
    }



def _resolved_fulltext_satisfies_provision_contract(resolved: dict | None, requested_provisions) -> bool:
    """Return True only when a resolved official text is provision-capable.

    Identity-aligned detail HTML is useful for metadata/status, but it is not
    sufficient to close a requested article gate when the article is absent.
    In that situation exact recovery must still be allowed to seek the linked
    official PDF/fulltext.
    """
    resolved=resolved or {}
    if not (resolved.get('resolved') and resolved.get('identity_aligned') and resolved.get('text')):
        return False
    requested=[normalize_provision_ref(x) for x in (requested_provisions or []) if normalize_provision_ref(x)]
    if not requested:
        return True
    located=locate_provisions(requested, resolved.get('text') or '', resolved.get('source_url'))
    located_set={normalize_provision_ref(x) for x in (located.get('located') or []) if normalize_provision_ref(x)}
    return all(ref in located_set for ref in requested)

def _recovery_result_should_replace_legacy(recovered: dict | None, legacy_resolved: dict | None = None) -> bool:
    """R21 propagation invariant for exact-identity recovery.

    A successful recovery always replaces the legacy result. If exact-lock is
    active, a fail-closed recovery also replaces a legacy result that is either
    unresolved or explicitly identity-misaligned. This prevents a stale wrong
    instrument (e.g. UU:5:2017) from surviving after an exact UU:31:1999
    candidate has been locked, while preserving compatibility with older
    resolver results that predate the explicit ``identity_aligned`` field.
    """
    recovered=recovered or {}
    legacy_resolved=legacy_resolved or {}
    if recovered.get('resolved'):
        return True
    if not recovered.get('recovery_exact_lock'):
        return False
    if not legacy_resolved.get('resolved'):
        return True
    return legacy_resolved.get('identity_aligned') is False



EXACT_CASE_RECOVERY_RESERVE_SECONDS = 4.0


def _is_exact_case_verification_row(row: dict) -> bool:
    """Return True only for regulations deterministically bound to the case.

    This is deliberately generic: no statute number is hard-coded.  A row is
    exact-case when it came from the exact-case route or carries case-bound
    provision provenance produced from the uploaded document.
    """
    if str(row.get('query_origin') or '').upper() == 'EXACT_CASE_REGULATION':
        alignment=_identity_alignment_state(row)
        # R42: only a proven mismatch is rejected.  UNVERIFIED candidates remain
        # eligible for official identity verification instead of being treated
        # as if a contradiction had already been established.
        if alignment == 'MISMATCH':
            return False
        if alignment == 'UNVERIFIED':
            binding=row.get('provision_binding_provenance') or {}
            return bool(
                _query_expected_identity_key(row)
                and (binding.get('case_bound') or row.get('query_origin') == 'EXACT_CASE_REGULATION')
            )
        return True
    binding=row.get('provision_binding_provenance') or {}
    return bool(binding.get('case_bound') and binding.get('instrument_key'))


class _VerificationScheduler:
    """Bounded scheduler that prevents exact-case regulations from starvation.

    The global wall-clock deadline is unchanged.  Exact-case rows are executed
    first, and while any exact-case identity is still pending, non-exact
    full-text/recovery work may not consume the final reserved slice.
    """
    def __init__(self, remaining_fn, exact_identity_keys, reserve_seconds: float = EXACT_CASE_RECOVERY_RESERVE_SECONDS):
        self._remaining_fn=remaining_fn
        self._pending_exact={str(x) for x in (exact_identity_keys or []) if x}
        self.reserve_seconds=max(0.0,float(reserve_seconds or 0.0))

    def remaining(self) -> float:
        return max(0.0,float(self._remaining_fn()))

    def is_exact(self, row: dict) -> bool:
        return _is_exact_case_verification_row(row)

    def can_run_fulltext(self, row: dict) -> bool:
        rem=self.remaining()
        if self.is_exact(row):
            return rem > 0.35
        floor=(self.reserve_seconds if self._pending_exact else 0.0) + 1.25
        return rem > floor

    def can_run_recovery(self, row: dict) -> bool:
        rem=self.remaining()
        if self.is_exact(row):
            return rem > 0.35
        floor=(self.reserve_seconds if self._pending_exact else 0.0) + 1.25
        return rem > floor

    def recovery_budget(self, row: dict) -> float:
        rem=self.remaining()
        if self.is_exact(row):
            # Use the reserved slice first, but never extend the global deadline.
            return min(self.reserve_seconds, max(0.35, rem - 0.10))
        return min(3.5, max(0.75, rem))

    def mark_exact_processed(self, row: dict) -> None:
        if not self.is_exact(row):
            return
        key=_verification_identity_key(row)
        self._pending_exact.discard(str(key or ''))


DEFAULT_VERIFICATION_DOCUMENT_BUDGET = 10
DEFAULT_VERIFICATION_TIME_BUDGET_SECONDS = 18.0


def _positive_law_row_strength(row: dict) -> tuple:
    """Monotonic ranking for duplicate representations of one instrument.

    A row that reached verified official fulltext/provision state must never be
    replaced by a stale detail-page representation of the same instrument.
    """
    pv=row.get('positive_law_verification') or {}
    prov=pv.get('provision_verification') or {}
    return (
        int(bool(pv.get('identity_confirmed'))),
        int(pv.get('case_nexus_status') == 'CASE_NEXUS_VERIFIED'),
        int(prov.get('verified_count') or 0),
        int(bool((row.get('fulltext_resolution') or {}).get('resolved'))),
        int(bool(pv.get('text_retrieved'))),
        float(row.get('relevance_score') or 0.0),
    )


def _consolidate_exact_case_rows(rows: list[dict]) -> list[dict]:
    """Keep one strongest canonical row per exact case-bound instrument.

    Discovery hits that carry a different actual identity are intentionally not
    folded into the expected instrument.  Only rows still qualifying as exact
    case rows participate in this consolidation.
    """
    out=[]
    slot_by_key={}
    for row in rows or []:
        if not _is_exact_case_verification_row(row):
            out.append(row)
            continue
        key=(
            str(row.get('canonical_instrument_key') or '').strip()
            or _candidate_actual_identity_key(row)
            or _expected_identity_key_for_fulltext(row)
        )
        if not key:
            out.append(row)
            continue
        if key not in slot_by_key:
            slot_by_key[key]=len(out)
            out.append(row)
            continue
        idx=slot_by_key[key]
        current=out[idx]
        if _positive_law_row_strength(row) > _positive_law_row_strength(current):
            winner=dict(row); loser=current
        else:
            winner=dict(current); loser=row
        alt=[]
        for source in (current,row):
            for url in [source.get('discovery_url'), source.get('url'), source.get('resolved_source_url')]:
                if url and url != winner.get('url') and url not in alt:
                    alt.append(url)
            for url in source.get('alternate_source_urls') or []:
                if url and url != winner.get('url') and url not in alt:
                    alt.append(url)
        if alt:
            winner['alternate_source_urls']=alt[:8]
        winner['canonical_instrument_key']=key
        winner['canonical_merge_strength']=_positive_law_row_strength(winner)
        winner['canonical_merge_applied']=True
        out[idx]=winner
    return out


def _verify_positive_law_results(results: list[dict], snapshot: dict, max_documents: int = DEFAULT_VERIFICATION_DOCUMENT_BUDGET, time_budget_seconds: float = DEFAULT_VERIFICATION_TIME_BUDGET_SECONDS) -> list[dict]:
    """Verify only deterministic legal-instrument candidates.

    Official news, event, profile, and unidentified landing pages remain visible
    to diagnostics but do not consume the positive-law verification budget.
    The budget is selected per instrument identity, not per search hit, so
    duplicate URLs and malformed exact citations cannot starve valid statutes.
    """
    enriched=[]
    enriched_by_index={}
    verified_budget=0
    fetch_map={}
    fetch_candidates=[]
    verification_started=time.monotonic()
    verification_deadline=verification_started+max(2.0,float(time_budget_seconds or DEFAULT_VERIFICATION_TIME_BUDGET_SECONDS))

    def _remaining() -> float:
        return max(0.0, verification_deadline-time.monotonic())

    def _apply_incorporated_provision_resolution(item: dict, base_verification: dict, resolved: dict) -> dict:
        """Verify article text in an expressly incorporated official attachment.

        R38 deliberately does not re-run parent status/tempus extraction against
        the child instrument text.  The parent official detail page remains the
        source of instrument identity/lifecycle metadata; the incorporated text
        supplies provision evidence only after the parent-child relationship has
        been verified by the fulltext resolver.
        """
        base=dict(base_verification or {})
        expected_key=_expected_identity_key_for_fulltext(item)
        if not (
            base.get('identity_confirmed') is True
            and resolved.get('resolved')
            and resolved.get('identity_aligned')
            and resolved.get('relationship_verified')
            and resolved.get('legal_role') == 'INCORPORATED_INSTRUMENT'
            and resolved.get('incorporation_parent_identity_key') == expected_key
            and resolved.get('incorporated_identity_key')
            and resolved.get('text')
        ):
            return base
        text=resolved.get('text') or ''
        requested=item.get('requested_provisions') or []
        base['text_retrieved']=True
        base['provision_text_location']=locate_provisions(requested,text,resolved.get('source_url'))
        text_verified=verify_provisions(requested,text,resolved.get('source_url'))
        base['provision_text_verification']=text_verified
        if base.get('case_nexus_status') == 'CASE_NEXUS_VERIFIED':
            base['provision_verification']=text_verified
        elif requested:
            base['provision_verification']={
                'status':'PROVISION_BLOCKED_BY_CASE_NEXUS',
                'requested':list(text_verified.get('requested') or []),
                'verified':[],'unverified':list(text_verified.get('requested') or []),
                'citations':[],'verified_count':0,
                'requested_count':int(text_verified.get('requested_count') or 0),
                'gate_reason':'CASE_NEXUS_VERIFIED is required before case-bound article verification',
            }
        base['provision_source_url']=resolved.get('source_url')
        base['provision_source_status']=resolved.get('resolver_status')
        base['fulltext_reconciliation']={
            'source_instrument_key': expected_key,
            'resolved_instrument_key': expected_key,
            'text_instrument_key': resolved.get('text_identity_key'),
            'incorporated_instrument_key': resolved.get('incorporated_identity_key'),
            'legal_role':'INCORPORATED_INSTRUMENT',
            'relationship_verified':True,
            'identity_aligned':True,
            'provision_binding_preserved': bool(item.get('provision_binding_provenance')),
            'resolver_status': resolved.get('resolver_status'),
        }
        base['fetch_attempted']=True
        base['fetch_reachable']=True
        return base

    def _apply_postfetch_contract(item: dict, verification: dict, official_text: str) -> dict:
        """Apply semantic family/domain checks only after official identity is confirmed."""
        if not isinstance(verification,dict) or verification.get('identity_confirmed') is not True:
            return verification
        expected_key=_expected_identity_key_for_fulltext(item)
        post_contract=evaluate_instrument_identity_contract(
            expected_key,item,expected_text=item.get('query') or '',
            active_domains=item.get('case_nexus_domains') or [],phase="POSTFETCH",
            official_text=official_text)
        item['instrument_identity_contract_postfetch']=post_contract
        if post_contract.get('passed'):
            return verification
        out=dict(verification)
        out.update({
            'case_nexus_status':'CASE_NEXUS_UNCERTAIN',
            'final_status':'REJECTED_POSTFETCH_SUBJECT_DOMAIN_CONTRACT',
            'diagnostic':post_contract.get('reason') or 'post-fetch semantic identity contract rejected official text',
            'semantic_contract_rejected':True,
        })
        # A semantic rejection must not leave article verification looking valid.
        pv=out.get('provision_verification') or {}
        if pv.get('requested_count'):
            out['provision_verification']={
                **pv,'status':'PROVISION_BLOCKED_BY_POSTFETCH_SEMANTIC_CONTRACT',
                'verified':[],'verified_count':0,
                'unverified':list(pv.get('requested') or []),
                'citations':[],
                'gate_reason':'official text subject/domain conflicts with the expected case-bound instrument family',
            }
        return out

    eligible=[]
    for idx,row in enumerate(results):
        classification=row.get('document_classification') or classify_legal_document_candidate(row)
        url=row.get('url') or ''
        expected_key=_expected_identity_key_for_fulltext(row)
        active_domains=row.get('case_nexus_domains') or []
        alignment=_identity_alignment_state(row)
        row['identity_alignment']=alignment
        contract=evaluate_instrument_identity_contract(
            expected_key, row, expected_text=row.get('query') or '', active_domains=active_domains, phase="PREFETCH")
        row['instrument_identity_contract']=contract
        decision=_prefetch_identity_decision(row, contract)
        row['eligible_for_identity_verification']=bool(decision.get('eligible'))
        row['prefetch_identity_decision']=decision
        if classification.get('legal_instrument_candidate') and row.get('authoritative') and url and decision.get('eligible'):
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
    max_urls_per_identity=2
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
    if fetch_candidates and _remaining() > 1.0:
        # Reserve part of the verification wall-clock for identity/fulltext work.
        # Fetch discovery must not consume the complete budget.
        batch_budget=min(7.0, max(1.0, _remaining()*0.45))
        per_fetch_timeout=max(1,min(4,int(batch_budget)))
        ex=ThreadPoolExecutor(max_workers=min(4,len(fetch_candidates)), thread_name_prefix="lexicore-verify")
        futs={ex.submit(fetch_official_document,url,per_fetch_timeout):url for url in fetch_candidates}
        done,pending=wait(set(futs), timeout=batch_budget)
        for fut in done:
            url=futs[fut]
            try: fetch_map[url]=fut.result()
            except Exception as exc:
                fetch_map[url]={"url":url,"reachable":False,"official_host":True,"body":b"",
                                "content_type":"","error":str(exc)[:240],"connectivity_status":"FETCH_ERROR"}
        for fut in pending:
            url=futs[fut]
            fut.cancel()
            fetch_map[url]={"url":url,"reachable":False,"official_host":True,"body":b"",
                            "content_type":"","error":"VERIFICATION_FETCH_TIME_BUDGET_EXCEEDED",
                            "connectivity_status":"TIME_BUDGET_EXCEEDED"}
        ex.shutdown(wait=False, cancel_futures=True)
    exact_identity_keys=[
        _verification_identity_key(row) for row in results
        if _is_exact_case_verification_row(row) and _verification_identity_key(row)
    ]
    scheduler=_VerificationScheduler(_remaining, exact_identity_keys)

    # Execute exact-case verification first so general discovery cannot starve
    # the regulation actually cited/bound in the case. Output order is restored
    # before returning, so this changes scheduling only, not report ordering.
    processing_rows=sorted(
        enumerate(results),
        key=lambda pair: (
            1 if _is_exact_case_verification_row(pair[1]) else 0,
            _verification_candidate_priority(pair[1]),
        ),
        reverse=True,
    )
    for original_idx,row in processing_rows:
        item=dict(row)
        classification=item.get('document_classification') or classify_legal_document_candidate(item)
        item['document_classification']=classification
        item['positive_law_verification']={
            'official_source_confirmed':bool(item.get('authoritative')),
            'text_retrieved':False,'identity_confirmed':False,
            'legal_status':'UNVERIFIED','tempus_status':'TEMPUS_UNVERIFIED',
            'case_nexus_status':item.get('case_nexus_status') or 'CASE_NEXUS_UNCERTAIN',
            'final_status':'UNVERIFIED','professional_verification':'PENDING',
            'fetch_attempted':False,'fetch_reachable':False,'verification_budget_exceeded':False,
        }
        if not classification.get('legal_instrument_candidate'):
            item['positive_law_verification'].update({
                'final_status':'REJECTED_NON_LEGAL_CONTENT',
                'diagnostic':classification.get('reason') or 'not a deterministic legal instrument candidate',
            })
            enriched_by_index[original_idx]=item
            scheduler.mark_exact_processed(item)
            continue

        expected_key=_expected_identity_key_for_fulltext(item)
        contract=item.get('instrument_identity_contract') or evaluate_instrument_identity_contract(
            expected_key, item, expected_text=item.get('query') or '', active_domains=item.get('case_nexus_domains') or [], phase="PREFETCH")
        item['instrument_identity_contract']=contract
        decision=_prefetch_identity_decision(item, contract)
        item['identity_alignment']=decision.get('alignment')
        item['eligible_for_identity_verification']=bool(decision.get('eligible'))
        item['prefetch_identity_decision']=decision
        if not decision.get('eligible'):
            item['positive_law_verification'].update({
                'final_status':'REJECTED_INSTRUMENT_IDENTITY_CONTRACT',
                'diagnostic':decision.get('reason') or contract.get('reason') or 'instrument identity contract rejected candidate metadata',
                'identity_contract_rejected':True,
            })
            enriched_by_index[original_idx]=item
            scheduler.mark_exact_processed(item)
            continue

        url=item.get('url') or ''
        identity_key=_verification_identity_key(item)
        if item.get('authoritative') and classification.get('legal_instrument_candidate') and url not in selected_urls:
            if identity_key not in selected_identities:
                item['positive_law_verification'].update({
                    'final_status':'NOT_ATTEMPTED_BUDGET_EXCEEDED',
                    'verification_budget_exceeded':True,
                    'diagnostic':f'positive-law verification identity budget exhausted ({max_documents}); candidate was discovered but not fetched',
                })
            else:
                item['positive_law_verification'].update({
                    'final_status':'NOT_ATTEMPTED_URL_FALLBACK_LIMIT',
                    'diagnostic':'alternate URL for an already-selected instrument was not fetched because the per-identity URL cap was reached',
                })
        if url in selected_urls and item.get('authoritative'):
            verified_budget += 1
            item['positive_law_verification']['fetch_attempted']=True
            fetched=fetch_map.get(url) or {'url':url,'reachable':False,'official_host':True,'body':b'',
                                           'content_type':'','error':'VERIFICATION_FETCH_NOT_COMPLETED_WITHIN_BUDGET',
                                           'connectivity_status':'TIME_BUDGET_EXCEEDED'}
            item['document_fetch']={k:v for k,v in fetched.items() if k!='body'}
            if fetched.get('reachable') and fetched.get('official_host'):
                item['positive_law_verification']['fetch_reachable']=True
                ctype=(fetched.get('content_type') or '').lower()
                body=fetched.get('body') or b''
                if 'html' in ctype:
                    text=html_to_text(body)
                    item['positive_law_verification']=verify_document_candidate(
                        item, source_text=text, snapshot=snapshot)
                    item['positive_law_verification']=_apply_postfetch_contract(item,item['positive_law_verification'],text)
                    item['positive_law_verification']['fetch_attempted']=True
                    item['positive_law_verification']['fetch_reachable']=True
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
                            requested_provisions=item.get('requested_provisions') or [], timeout=max(1,min(3,int(max(1,scheduler.remaining())))), max_candidates=2,
                            expected_identity_key=expected_identity_key) if scheduler.can_run_fulltext(item) else {'resolved':False,'resolver_status':'VERIFICATION_TIME_BUDGET_EXCEEDED','attempted_urls':[]}
                        if expected_identity_key and not _resolved_fulltext_satisfies_provision_contract(resolved, item.get('requested_provisions') or []):
                            recovered=_recover_expected_official_fulltext(
                                expected_identity_key, item.get('requested_provisions') or [],
                                preferred_source_id=item.get('source_id'), timeout=3, time_budget_seconds=scheduler.recovery_budget(item)) if scheduler.can_run_recovery(item) else {'resolved':False,'recovery_exact_lock':False,'resolver_status':'RECOVERY_SKIPPED_TIME_BUDGET','attempted_urls':[]}
                            if _recovery_result_should_replace_legacy(recovered, resolved):
                                resolved=recovered
                        item['fulltext_resolution']={k:v for k,v in resolved.items() if k!='text'}
                        if resolved.get('resolved') and resolved.get('text'):
                            if resolved.get('legal_role') == 'INCORPORATED_INSTRUMENT':
                                full_verified=_apply_incorporated_provision_resolution(
                                    item,item['positive_law_verification'],resolved)
                                full_verified=_apply_postfetch_contract(
                                    item,full_verified,resolved.get('text') or '')
                                # Parent detail remains authoritative for lifecycle
                                # status/tempus; the attachment is evidence for the
                                # requested provision text only.
                                full_verified['legal_status_source_url']=fetched.get('final_url') or url
                            else:
                                resolved_candidate=dict(item)
                                if resolved.get('source_url'):
                                    resolved_candidate['url']=resolved.get('source_url')
                                full_verified=verify_document_candidate(
                                    resolved_candidate, source_text=resolved.get('text') or '', snapshot=snapshot)
                                full_verified=apply_post_verification_status_semantics(full_verified, resolved_candidate)
                                full_verified=_apply_postfetch_contract(item,full_verified,resolved.get('text') or '')
                                full_verified['provision_source_url']=resolved.get('source_url')
                                full_verified['provision_source_status']=resolved.get('resolver_status')
                                full_verified['fulltext_reconciliation']={
                                    'source_instrument_key': expected_identity_key,
                                    'resolved_instrument_key': resolved.get('resolved_identity_key'),
                                    'text_instrument_key': resolved.get('text_identity_key'),
                                    'legal_role': resolved.get('legal_role'),
                                    'identity_aligned': bool(resolved.get('identity_aligned')),
                                    'provision_binding_preserved': bool(item.get('provision_binding_provenance')),
                                    'resolver_status': resolved.get('resolver_status'),
                                }
                                full_verified['legal_status_source_url']=resolved.get('source_url')
                                full_verified['fetch_attempted']=True
                                full_verified['fetch_reachable']=True
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
                        requested_provisions=item.get('requested_provisions') or [], timeout=max(1,min(3,int(max(1,scheduler.remaining())))), max_candidates=2,
                        expected_identity_key=expected_identity_key) if scheduler.can_run_fulltext(item) else {'resolved':False,'resolver_status':'VERIFICATION_TIME_BUDGET_EXCEEDED','attempted_urls':[]}
                    if expected_identity_key and not _resolved_fulltext_satisfies_provision_contract(resolved, item.get('requested_provisions') or []):
                        recovered=_recover_expected_official_fulltext(
                            expected_identity_key, item.get('requested_provisions') or [],
                            preferred_source_id=item.get('source_id'), timeout=3, time_budget_seconds=scheduler.recovery_budget(item)) if scheduler.can_run_recovery(item) else {'resolved':False,'recovery_exact_lock':False,'resolver_status':'RECOVERY_SKIPPED_TIME_BUDGET','attempted_urls':[]}
                        if _recovery_result_should_replace_legacy(recovered, resolved):
                            resolved=recovered
                    item['fulltext_resolution']={k:v for k,v in resolved.items() if k!='text'}
                    if resolved.get('resolved') and resolved.get('text'):
                        item['positive_law_verification']=verify_document_candidate(
                            item, source_text=resolved.get('text') or '', snapshot=snapshot)
                        item['positive_law_verification']=apply_post_verification_status_semantics(
                            item['positive_law_verification'], item)
                        item['positive_law_verification']=_apply_postfetch_contract(
                            item,item['positive_law_verification'],resolved.get('text') or '')
                        item['positive_law_verification']['fetch_attempted']=True
                        item['positive_law_verification']['fetch_reachable']=True
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
        enriched_by_index[original_idx]=item
        scheduler.mark_exact_processed(item)
    enriched=[enriched_by_index[i] for i in range(len(results)) if i in enriched_by_index]
    # R41: exact-case duplicate representations collapse only after all fetch,
    # identity, status and fulltext gates have run.  This preserves the strongest
    # verified canonical state and prevents a stale 0/1 detail row from surviving
    # beside a 1/1 fulltext row for the same instrument.
    return _consolidate_exact_case_rows(enriched)



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
    fetch_attempted=0
    fetch_reachable=0
    text_located=0
    instrument_identity_verified=0
    provision_text_verified=0
    not_attempted_budget_exceeded=0
    for r in results or []:
        if not isinstance(r,dict):
            continue
        v=r.get("positive_law_verification") or {}
        fetch_attempted += 1 if v.get('fetch_attempted') else 0
        fetch_reachable += 1 if v.get('fetch_reachable') else 0
        text_located += 1 if (v.get('text_retrieved') or v.get('fetch_reachable')) else 0
        instrument_identity_verified += 1 if v.get('identity_confirmed') else 0
        if v.get('final_status') == 'NOT_ATTEMPTED_BUDGET_EXCEEDED':
            not_attempted_budget_exceeded += 1
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
            provision_text_verified += 1

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
        "fetch_attempted": fetch_attempted,
        "fetch_reachable": fetch_reachable,
        "text_located": text_located,
        "instrument_identity_verified": instrument_identity_verified,
        "provision_text_verified": provision_text_verified,
        "not_attempted_budget_exceeded": not_attempted_budget_exceeded,
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
        fulltext_resolution=r.get("fulltext_resolution") or {}
        binding=r.get("provision_binding_provenance") or {}
        expected_key=(
            fulltext_resolution.get("expected_identity_key")
            or identity.get("expected_key")
            or recon.get("source_instrument_key")
            or _verification_identity_key(r)
        )

        # R22 report-state invariant: diagnostics must serialize the canonical
        # post-recovery state.  Once exact-lock is active, a stale pre-recovery
        # mismatch (for example UU:5:2017) must never leak into Section 14.
        exact_lock=bool(fulltext_resolution.get("recovery_exact_lock"))
        exact_success=bool(
            exact_lock
            and fulltext_resolution.get("resolved")
            and fulltext_resolution.get("identity_aligned")
        )
        if exact_lock:
            resolved_key=(fulltext_resolution.get("resolved_identity_key") or expected_key) if exact_success else ""
            identity_confirmed=exact_success
            identity_reason=(
                fulltext_resolution.get("resolver_status")
                or ("RECOVERED_EXACT_IDENTITY" if exact_success else "EXPECTED_IDENTITY_EXACT_CANDIDATE_FAILED")
            )
            trace=fulltext_resolution.get("recovery_candidate_trace") or []
            identity_candidates=[
                str(x.get("title_identity")) for x in trace
                if isinstance(x,dict) and x.get("title_identity")
            ][:8]
        else:
            resolved_key=(recon.get("resolved_instrument_key") or identity.get("key"))
            identity_confirmed=bool(v.get("identity_confirmed"))
            identity_reason=identity.get("match_reason")
            identity_candidates=list(identity.get("actual_identity_candidates") or [])[:8]

        dedupe=(str(expected_key), tuple(x.lower() for x in located), str(r.get("url") or ""), exact_lock, str(resolved_key))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append({
            "expected_instrument_key": expected_key,
            "resolved_instrument_key": resolved_key,
            "identity_candidates": identity_candidates,
            "identity_confirmed": identity_confirmed,
            "identity_match_reason": identity_reason,
            "exact_lock_active": exact_lock,
            "post_recovery_status": fulltext_resolution.get("resolver_status") if exact_lock else None,
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
        'electoral_ethics': ('pemilihan umum','pemilu','pilkada','kpu','bawaslu','dkpp','kode etik','penyelenggara pemilu'),
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
        'electoral_ethics':('pemilihan umum','pemilihan gubernur','pemilihan bupati','pemilihan walikota','dkpp','kode etik penyelenggara pemilu'),
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
                              retrieval_mode: str | None = None, domain_classification: dict | None = None,
                              material_tempus_selection: dict | None = None) -> dict:
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
    # Canonical material-tempus selection is computed once upstream when available
    # and reused here.  This preserves the exact-verification architecture while
    # preventing procedural dates from becoming the positive-law temporal anchor.
    material_tempus_selection = dict(material_tempus_selection or select_material_tempus(text))
    if material_tempus_selection.get('status') == 'MATERIAL_TEMPUS_CANDIDATE':
        material_value = str(material_tempus_selection.get('value') or '')
        material_precision = material_tempus_selection.get('precision')
        event_date = material_value if material_precision == 'date' else None
        m = re.match(r'(19\d{2}|20\d{2})', material_value)
        event_year = int(m.group(1)) if m else None
    else:
        event_date = None
        event_year = None
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

    # Integrated Closure: exact case citations are first-class deterministic
    # verification jobs.  They are created from the case text itself and are
    # prepended before discovery rows, so search recall/ranking can never decide
    # whether an expressly cited instrument receives a verification attempt.
    exact_job_rows=_build_exact_case_verification_rows(source_bindings, domains, event_year)
    if exact_job_rows:
        existing={(str(r.get("url") or ""), str(_verification_identity_key(r) or "")) for r in results}
        merged_exact=[]
        for job_row in exact_job_rows:
            key=(str(job_row.get("url") or ""), str(_verification_identity_key(job_row) or ""))
            if key not in existing:
                merged_exact.append(job_row)
                existing.add(key)
            else:
                # If discovery already returned the same exact URL, upgrade that
                # row with deterministic case-bound job provenance rather than
                # creating a duplicate representation.
                for r in results:
                    if (str(r.get("url") or ""), str(_verification_identity_key(r) or "")) == key:
                        r.update({
                            "query_origin":"EXACT_CASE_REGULATION",
                            "exact_verification_job":True,
                            "expected_identity_key":job_row.get("expected_identity_key"),
                            "requested_provisions":job_row.get("requested_provisions") or r.get("requested_provisions") or [],
                            "provision_binding_provenance":job_row.get("provision_binding_provenance"),
                            "case_nexus_domains":job_row.get("case_nexus_domains") or r.get("case_nexus_domains") or [],
                            "case_nexus_status":job_row.get("case_nexus_status") or r.get("case_nexus_status"),
                            "case_nexus_reason":job_row.get("case_nexus_reason"),
                        })
                        break
        results=merged_exact+results

    # Final retrieval lock: every row entering positive-law verification must
    # carry an explicit candidate-law relevance decision.  This closes paths
    # where exact-job merging or legacy/reconstructed rows could bypass the
    # initial compact-search filter.  Exact case citations may still be kept for
    # identity/provision audit, but a hard institutional mismatch is explicitly
    # barred from the downstream Candidate Law pool.
    locked_results=[]
    for row in results:
        if not isinstance(row,dict):
            continue
        decision=evaluate_law_weight_policy(row, domains)
        row=dict(row)
        row["law_weight_policy"]=decision
        exact_case=str(row.get("query_origin") or "").upper()=="EXACT_CASE_REGULATION"
        hard_drop=bool(decision.get("hard_drop_reasons"))
        if hard_drop:
            row["candidate_law_eligible"]=False
            row["candidate_law_rejection_reason"]=(decision.get("hard_drop_reasons") or ["INSTITUTIONAL_MISMATCH"])[0]
            # Preserve an exact source citation only for audit/identity checking.
            # It must not later become a governing-law candidate.
            if exact_case:
                locked_results.append(row)
            continue
        if exact_case:
            row["candidate_law_eligible"]=True
            locked_results.append(row)
            continue
        if decision.get("status") != "POSITIVE_NEXUS_VERIFIED":
            continue
        row["candidate_law_eligible"]=True
        locked_results.append(row)
    results=locked_results

    verification_snapshot = {
        "event_year_candidate": event_year,
        "event_date_candidate": event_date,
        "procedural_date_candidate": procedural_date,
        "material_tempus_status": material_tempus_selection.get("status"),
        "material_tempus_selection_basis": material_tempus_selection.get("selection_basis"),
    }
    if online and results:
        results = _verify_positive_law_results(results, verification_snapshot, max_documents=DEFAULT_VERIFICATION_DOCUMENT_BUDGET, time_budget_seconds=DEFAULT_VERIFICATION_TIME_BUDGET_SECONDS)
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
        "material_tempus": material_tempus_selection,
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
