"""Deterministic case-law/doctrine summarisation for Legal Research.

No external AI is used.  The extractor prefers explicit headings and source
language.  Missing parts remain explicitly unverified rather than invented.
"""
from __future__ import annotations

import re
from typing import Dict, List

CASE_TYPES={"putusan_ma","putusan_mk","putusan_pengadilan","case"}
DOCTRINE_TYPES={"legal_opinion","doctrine","memo"}


def _clean(text:str)->str:
    return re.sub(r"[ \t]+"," ",re.sub(r"\r\n?","\n",text or "")).strip()


def _sentences(text:str)->List[str]:
    t=re.sub(r"\s+"," ",_clean(text))
    if not t:return []
    parts=re.split(r"(?<=[.!?;:])\s+(?=[A-Z0-9(\[])",t)
    return [p.strip() for p in parts if len(p.strip())>20]


def _section(text:str,start_patterns:List[str],end_patterns:List[str],max_chars:int=2200)->str:
    src=_clean(text)
    low=src.lower()
    starts=[]
    for p in start_patterns:
        m=re.search(p,src,re.I|re.M)
        if m: starts.append((m.start(),m.end()))
    if not starts:return ""
    start=min(starts,key=lambda x:x[0])[1]
    end=len(src)
    tail=src[start:]
    for p in end_patterns:
        m=re.search(p,tail,re.I|re.M)
        if m and m.start()>10:
            end=min(end,start+m.start())
    return re.sub(r"\s+"," ",src[start:end]).strip()[:max_chars]


def _select_sentences(text:str,keywords:List[str],limit:int=5,max_chars:int=2000)->str:
    ss=_sentences(text); out=[]
    for s in ss:
        lo=s.lower()
        if any(k in lo for k in keywords):
            out.append(s)
            if len(out)>=limit:break
    return " ".join(out)[:max_chars]


def _chronology(text:str)->str:
    explicit=_section(text,[r"\b(?:kronologi|duduk perkara|tentang duduk perkara|riwayat perkara)\b\s*:?"],
                      [r"\b(?:pertimbangan hukum|menimbang|tentang pertimbangan|amar putusan|mengadili)\b"],2200)
    if explicit:return explicit
    ss=_sentences(text); selected=[]
    date_re=re.compile(r"\b(?:\d{1,2}[\-/ ](?:\d{1,2}|[A-Za-z]+)[\-/ ]\d{2,4}|(?:19|20)\d{2})\b")
    verbs=("mengajukan","menggugat","memohon","didakwa","dituntut","memeriksa","mengadili","banding","kasasi","peninjauan kembali","terjadi","berdasarkan")
    for s in ss[:30]:
        lo=s.lower()
        if date_re.search(s) or any(v in lo for v in verbs):
            selected.append(s)
            if len(selected)>=6:break
    if not selected:selected=ss[:4]
    return " ".join(selected)[:2200] if selected else "TIDAK TERIDENTIFIKASI SECARA EKSPLISIT DARI TEKS SUMBER."


def _ratio(text:str)->str:
    explicit=_section(text,[r"\b(?:pertimbangan hukum|ratio decidendi)\b\s*:?",r"\bmenimbang\b\s*:?"] ,
                      [r"\b(?:amar putusan|mengadili|memutuskan|menetapkan)\b\s*:?"] ,2600)
    if explicit:return explicit
    found=_select_sentences(text,["menurut mahkamah","menurut majelis","oleh karena itu","oleh sebab itu","judex facti","judex juris","pertimbangan","berpendapat","beralasan hukum"],7,2600)
    return found or "TIDAK TERIDENTIFIKASI SECARA EKSPLISIT DARI TEKS SUMBER."


def _amar(text:str)->str:
    explicit=_section(text,[r"\bamar putusan\b\s*:?",r"\bm\s*e\s*n\s*g\s*a\s*d\s*i\s*l\s*i\b\s*:?",r"\bmengadili\b\s*:?",r"\bmemutuskan\b\s*:?",r"\bmenetapkan\b\s*:?"] ,
                      [r"\b(?:demikian diputus|diputuskan dalam|ditetapkan dalam|hakim anggota|panitera)\b"],2200)
    if explicit:return explicit
    found=_select_sentences(text,["mengadili","mengabulkan","menolak","menyatakan","menghukum","menetapkan","membatalkan","tidak dapat diterima"],6,2200)
    return found or "TIDAK TERIDENTIFIKASI SECARA EKSPLISIT DARI TEKS SUMBER."


def _explicit_rule(text:str)->str:
    return _section(text,[r"\bkaidah hukum\b\s*:?",r"\bkaidah\b\s*:?"] ,
                    [r"\b(?:amar putusan|mengadili|catatan|sumber|referensi)\b"],1800)


def _infer_rule(ratio:str,amar:str)->tuple[str,str]:
    explicit_candidates=[]
    for s in _sentences(ratio):
        lo=s.lower()
        if any(k in lo for k in ("apabila","harus","tidak dapat","dapat","wajib","berwenang","tidak berwenang","merupakan")):
            explicit_candidates.append(s)
    if explicit_candidates:
        return explicit_candidates[0][:1400],"INFERRED_FROM_RATIO — PROFESSIONAL VERIFICATION REQUIRED"
    if ratio and not ratio.startswith("TIDAK TERIDENTIFIKASI"):
        return ratio[:1200],"INFERRED_FROM_RATIO — PROFESSIONAL VERIFICATION REQUIRED"
    return "TIDAK DAPAT DIRUMUSKAN SECARA ANDAL DARI TEKS SUMBER YANG TERSEDIA.","UNVERIFIED"


def summarize_case_source(text:str)->Dict:
    chronology=_chronology(text)
    ratio=_ratio(text)
    amar=_amar(text)
    explicit=_explicit_rule(text)
    if explicit:
        rule,status=explicit,"EXPLICIT_IN_SOURCE"
    else:
        rule,status=_infer_rule(ratio,amar)
    return {
        "chronology":chronology,
        "ratio_decidendi":ratio,
        "disposition":amar,
        "legal_rule":rule,
        "legal_rule_status":status,
        "professional_verification":"PENDING",
    }


def summarize_doctrine_source(text:str)->Dict:
    ss=_sentences(text)
    topic=ss[0] if ss else "TIDAK TERIDENTIFIKASI SECARA EKSPLISIT DARI TEKS SUMBER."
    thesis=_select_sentences(text,["berpendapat","menurut","doktrin","teori","asas","menjelaskan","menyatakan"],5,2200)
    analysis=" ".join(ss[1:7])[:2400] if len(ss)>1 else topic
    implications=_select_sentences(text,["implikasi","akibat","sehingga","oleh karena","dengan demikian","penerapan"],4,1800)
    return {
        "doctrine_topic":topic,
        "doctrine_thesis":thesis or analysis,
        "doctrine_analysis":analysis,
        "doctrine_implication":implications or "IMPLIKASI PRAKTIS MEMERLUKAN PEMETAAN TERHADAP FAKTA PERKARA.",
        "professional_verification":"PENDING",
    }
