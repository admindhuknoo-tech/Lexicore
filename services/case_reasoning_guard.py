"""Case Analysis Legal Reasoning Guard.

Fail-closed legal synthesis for LexiCore.

The guard does not decide the merits.  It prevents a domain classifier or an
AI narrative from silently escalating keyword hits into a legal conclusion.
Specific modules are emitted only when the source text contains the required
keterkaitan perkara.  Tempus, citation identity, forum/merits and attribution problems
are surfaced as explicit verification gates.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple


def _uniq(values: Iterable[str], limit: int = 20) -> List[str]:
    out=[]; seen=set()
    for value in values:
        value=re.sub(r"\s+"," ",str(value or "")).strip()
        key=value.lower()
        if not value or key in seen: continue
        seen.add(key); out.append(value)
        if len(out)>=limit: break
    return out


def _sentences(text: str) -> List[str]:
    text=re.sub(r"\s+"," ",str(text or "")).strip()
    if not text: return []
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+",text) if s.strip()]


def _has(text: str, terms: Iterable[str]) -> bool:
    low=str(text or "").lower()
    return any(str(t).lower() in low for t in terms)


def _count(text: str, terms: Iterable[str]) -> int:
    low=str(text or "").lower()
    return sum(1 for t in terms if str(t).lower() in low)


def _context_flags(text: str, domain_contract: Dict | None = None) -> Dict[str,bool]:
    low=str(text or "").lower()
    active=set((domain_contract or {}).get("domain_contract") or [])
    primary=str((domain_contract or {}).get("primary_domain") or "")
    strong_criminal=_count(low,["surat dakwaan","dakwaan","terdakwa","tersangka","jaksa penuntut umum","penyidikan","penuntutan"])>=2
    noncriminal_posture=primary in {"electoral_ethics","administrative","civil_contract","employment","religious_court","public_information"}
    criminal = ("criminal" in active or "corruption" in active or (strong_criminal and not noncriminal_posture))
    corruption_markers=_count(low,["tindak pidana korupsi","tipikor","kerugian keuangan negara","kerugian keuangan daerah","pasal 603","pasal 604"])
    corruption = ("corruption" in active or (strong_criminal and corruption_markers>=1 and not noncriminal_posture))
    electoral = ("electoral_ethics" in active)
    banking = ("financial_services" in active or _count(low,["bpr","bank perkreditan rakyat","bank perekonomian rakyat","pemberian kredit","fasilitas kredit","debitur","agunan","plafon kredit"])>=2)
    governance = _count(low,["sop","prosedur","tata kelola","kewenangan","komite kredit","pemutus kredit","survei","survey","analisa 5c"])>=2
    prosecution = _count(low,["jaksa","penuntut umum","jpu","dakwaan","penuntutan"])>=1 and criminal
    fiduciary = _count(low,["fidusia","fiduci","sertifikat fidusia","sertipikat fidusia","bpkb","barang jaminan","objek jaminan"])>=2
    objection = _count(low,["eksepsi","keberatan","perlawanan","dakwaan tidak jelas","cermat dan lengkap"])>=1
    forum_tipikor = _count(low,["pengadilan tipikor","pengadilan tindak pidana korupsi","tidak berwenang mengadili","kewenangan mengadili"])>=1
    error_persona = "error in persona" in low or "salah orang" in low
    return {
        "criminal_nexus":criminal,
        "corruption_nexus":corruption,
        "electoral_nexus":electoral,
        "banking_nexus":banking,
        "governance_nexus":governance,
        "prosecution_context":prosecution,
        "fiduciary_nexus":fiduciary,
        "objection_context":objection,
        "tipikor_forum_dispute":forum_tipikor,
        "error_in_persona_claim":error_persona,
    }


# These are *candidate normalisations*, never silent corrections.  The source
# text remains authoritative until checked against the original charging paper.
_CITATION_ANOMALIES: Tuple[Tuple[str,str,str], ...] = (
    (r"\b(?:UU|Undang[- ]Undang|Undng[- ]Undang)?(?:\s+Republik Indonesia)?\s*(?:Nomor\s+)?1\s+Tahun\s+2003(?!\d)", "UU Nomor 1 Tahun 2003", "Kandidat: UU Nomor 1 Tahun 2023"),
    (r"\b(?:UU|Undang[- ]Undang|Undng[- ]Undang)?(?:\s+Republik Indonesia)?\s*(?:Nomor\s+)?31\s+Tahun\s+2099(?!\d)", "UU Nomor 31 Tahun 2099", "Kandidat: UU Nomor 31 Tahun 1999"),
    (r"\b(?:UU|Undang[- ]Undang|Undng[- ]Undang)?(?:\s+Republik Indonesia)?\s*(?:Nomor\s+)?20\s+Tahun\s+2021(?!\d)", "UU Nomor 20 Tahun 2021", "Kandidat: UU Nomor 20 Tahun 2001"),
)


def detect_citation_anomalies(text: str) -> List[Dict]:
    out=[]
    for pattern, source, candidate in _CITATION_ANOMALIES:
        if re.search(pattern,str(text or ""),re.I):
            out.append({
                "source_text":source,
                "candidate_normalization":candidate,
                "status":"POTENTIAL_TYPO_OR_OCR",
                "instruction":"Jangan koreksi diam-diam. Cocokkan dengan surat dakwaan/dokumen asli dan sumber resmi sebelum dipakai sebagai dasar hukum.",
            })
    return out


def _event_year_candidates(text: str) -> List[int]:
    """Years tied to alleged conduct, not statute years or object/model years.

    A year is accepted only when the nearby text carries an event-time cue.  A
    vehicle/model year inside a credit sentence must not become tempus delicti.
    """
    event_markers=("perbuatan","pemberian kredit","fasilitas kredit","pencairan","transaksi","kejadian","terjadi","melakukan","menyetujui","persetujuan kredit","kredit diberikan","kredit dicairkan")
    statute_markers=("undang-undang"," uu ","pasal ","nomor perkara","pid.sus","tanggal persidangan","surat kuasa","kepaniteraan")
    time_cues=("tanggal","pada tahun","pada tanggal","bulan","periode","sejak","antara tahun","sekitar tahun")
    object_year_cues=("mobil","kendaraan","honda","jazz","nomor polisi","tahun produksi","model kendaraan","barang jaminan","agunan")
    years=[]
    for sentence in _sentences(text):
        low=f" {sentence.lower()} "
        if not any(m in low for m in event_markers): continue
        if sum(1 for m in statute_markers if m in low)>=2: continue
        for match in re.finditer(r"\b(19\d{2}|20\d{2})\b",sentence):
            near=sentence[max(0,match.start()-90):min(len(sentence),match.end()+90)].lower()
            if any(c in near for c in object_year_cues):
                continue
            if not any(c in near for c in time_cues):
                continue
            years.append(int(match.group(1)))
    return sorted(set(years))


def assess_tempus(text: str, flags: Dict[str,bool]) -> Dict:
    years=_event_year_candidates(text)
    modern_refs=_has(text,["pasal 603","pasal 604","uu nomor 1 tahun 2023","uu 1 tahun 2023","uu nomor 1 tahun 2026","uu 1 tahun 2026"])
    pre_2026=any(y<2026 for y in years)
    if flags.get("criminal_nexus") and modern_refs:
        if not years:
            status="TEMPUS_INSUFFICIENT"
            note="Norma pidana 2023/2026 disebut, tetapi tahun/tanggal perbuatan yang didakwakan belum teridentifikasi secara cukup dari dokumen ini. Norma materiil tidak boleh dinyatakan applicable sebelum tempus delicti dan ketentuan peralihannya diverifikasi."
        elif pre_2026:
            status="TEMPUS_TRANSITION_REVIEW_REQUIRED"
            note="Terdapat kandidat tahun perbuatan sebelum 2026 bersamaan dengan rujukan norma 2023/2026. Lakukan uji tempus, ketentuan peralihan, dan hukum yang dapat diterapkan sebelum menarik kesimpulan materiil."
        else:
            status="TEMPUS_CANDIDATE_2026_PLUS"
            note="Kandidat tahun perbuatan berada pada 2026 atau sesudahnya, tetapi tanggal perbuatan dan status norma tetap harus dicocokkan dengan dakwaan asli/sumber resmi."
    elif flags.get("criminal_nexus"):
        status="TEMPUS_REQUIRES_EVENT_DATE"
        note="Perkara pidana terdeteksi. Tempus delicti harus dipastikan sebelum memilih norma materiil yang berlaku."
    else:
        status="TEMPUS_NOT_TRIGGERED"
        note="Tidak ada pemicu khusus tempus pidana pada dokumen ini."
    return {"status":status,"event_year_candidates":years,"modern_penal_references_detected":modern_refs,"note":note}


def _boundary_checks(text: str, flags: Dict[str,bool]) -> List[Dict]:
    low=str(text or "").lower(); out=[]
    if flags.get("objection_context") and flags.get("tipikor_forum_dispute") and flags.get("corruption_nexus"):
        if _has(low,["penggelapan","fidusia","penadahan","bukan tindak pidana korupsi"]):
            out.append({
                "code":"FORUM_VS_MERITS",
                "level":"INFERENCE",
                "finding":"Argumen bahwa peristiwa lebih tepat dikualifikasikan sebagai fidusia/penggelapan tidak otomatis identik dengan tidak adanya kompetensi Pengadilan Tipikor ketika dakwaan memang dibingkai sebagai Tipikor.",
                "required_check":"Pisahkan cacat kompetensi/forum dari bantahan mengenai terpenuhi atau tidaknya unsur tindak pidana (pokok perkara). Uji terhadap dakwaan asli dan hukum acara yang berlaku.",
            })
    if flags.get("error_in_persona_claim"):
        other_party=_has(low,["yang seharusnya bertanggung jawab","mestinya yang dimintai pertanggungjawaban","salah orang","orang yang dititipi"])
        if other_party:
            out.append({
                "code":"ERROR_IN_PERSONA_VS_ATTRIBUTION",
                "level":"INFERENCE",
                "finding":"Dalil bahwa pihak lain lebih bertanggung jawab belum dengan sendirinya membuktikan error in persona apabila identitas terdakwa dalam dakwaan memang jelas dan penuntut sengaja mengatribusikan perbuatan kepadanya.",
                "required_check":"Bedakan salah identitas subjek, tidak terbuktinya atribusi perbuatan, dan keberadaan pelaku/pihak lain yang turut bertanggung jawab.",
            })
    if flags.get("fiduciary_nexus") and flags.get("corruption_nexus"):
        out.append({
            "code":"FIDUCIARY_NON_DISPOSITIVE",
            "level":"LEGAL_CONCLUSION_GUARD",
            "finding":"Keberadaan agunan/fidusia relevan terhadap exposure, recovery dan kausalitas, tetapi tidak boleh dipakai sebagai kesimpulan otomatis bahwa unsur Tipikor ada atau tidak ada.",
            "required_check":"Verifikasi proses pemberian kredit, kewenangan, nilai/outstanding, recovery, status agunan, audit kerugian, causal chain, dan atribusi individual.",
        })
    return out


def build_reasoning_guard(text: str, domain_contract: Dict | None = None) -> Dict:
    flags=_context_flags(text,domain_contract)
    tempus=assess_tempus(text,flags)
    anomalies=detect_citation_anomalies(text)
    boundaries=_boundary_checks(text,flags)

    modules=[]
    modules.append("Dokumen harus dianalisis dari fakta dan bukti yang benar-benar terdapat di sumber; klasifikasi domain hanya merupakan alat penyaringan dan bukan kesimpulan hukum.")
    if flags["objection_context"]:
        modules.append("Karena dokumen memuat eksepsi/keberatan, pisahkan keberatan formil terhadap dakwaan atau forum dari pembelaan yang sebenarnya memasuki pembuktian pokok perkara.")
    if flags.get("electoral_nexus"):
        modules.append("Keterkaitan dengan Pemilu/Pilkada atau etik penyelenggara terdeteksi. Pisahkan pemeriksaan etik/administratif dari proses pidana; rujukan terhadap undang-undang pidana atau lembaga penegak hukum tidak mengubah posture perkara tanpa bukti proses pidana yang independen.")
    if flags["criminal_nexus"]:
        modules.append("Keterkaitan dengan perkara pidana terdeteksi. Setiap kesimpulan pidana harus diuji unsur demi unsur dan tidak boleh diturunkan hanya dari pelanggaran prosedur, jabatan, atau hasil akhir yang merugikan.")
    if flags["corruption_nexus"]:
        modules.append("Keterkaitan dengan tindak pidana korupsi terdeteksi dari dokumen. Kerugian, sifat melawan hukum/penyalahgunaan kewenangan, kausalitas, keadaan batin dan atribusi pertanggungjawaban individual tetap merupakan isu pembuktian; tidak ada yang boleh diasumsikan hanya dari label perkara.")
    if flags["banking_nexus"]:
        modules.append("Keterkaitan dengan perbankan/kredit terdeteksi. Pisahkan kualitas keputusan kredit, kepatuhan SOP, status agunan/fidusia, pembayaran/outstanding dan recovery dari pertanyaan apakah unsur pidana tertentu terbukti.")
    if tempus["status"]!="TEMPUS_NOT_TRIGGERED":
        modules.append(tempus["note"])
    if anomalies:
        modules.append("Terdapat identitas peraturan yang berpotensi salah ketik/OCR. LexiCore tidak mengoreksi rujukan tersebut secara diam-diam; seluruh kandidat normalisasi harus diverifikasi terhadap dokumen asli dan sumber resmi.")
    if boundaries:
        modules.extend(x["finding"] for x in boundaries)

    gates=[]
    if flags["criminal_nexus"]: gates.append({"gate":"CASE_NEXUS","status":"TRIGGERED","reason":"Konteks pidana ditemukan dalam sumber."})
    if flags["corruption_nexus"]: gates.append({"gate":"CORRUPTION_NEXUS","status":"TRIGGERED_NOT_PROVEN","reason":"Label/dakwaan Tipikor ditemukan; pemenuhan unsur belum ditetapkan."})
    if tempus["status"] in ("TEMPUS_INSUFFICIENT","TEMPUS_TRANSITION_REVIEW_REQUIRED","TEMPUS_REQUIRES_EVENT_DATE"):
        gates.append({"gate":"TEMPUS","status":"BLOCKS_DEFINITIVE_APPLICABLE_LAW","reason":tempus["note"]})
    else:
        gates.append({"gate":"TEMPUS","status":"REQUIRES_VERIFICATION" if flags["criminal_nexus"] else "NOT_TRIGGERED","reason":tempus["note"]})
    if anomalies:
        gates.append({"gate":"INSTRUMENT_IDENTITY","status":"BLOCKS_SILENT_NORMALIZATION","reason":"Ada rujukan peraturan yang berpotensi salah identitas/tahun."})
    if boundaries:
        gates.append({"gate":"ARGUMENT_CLASSIFICATION","status":"REQUIRES_BOUNDARY_REVIEW","reason":"Terdapat dalil yang harus dipisahkan antara forum, merits, atribusi, atau efek jaminan."})

    level_notes=[
        {"level":"FACT","rule":"Hanya pernyataan yang langsung didukung dokumen/bukti sumber."},
        {"level":"INFERENCE","rule":"Kesimpulan analitis harus menunjukkan fakta yang menjadi dasar dan tetap dapat dibantah."},
        {"level":"LEGAL_CONCLUSION","rule":"Hanya setelah norma, identitas instrumen, status berlaku, tempus, keterkaitan perkara, dan unsur yang relevan cukup terverifikasi."},
    ]
    return {
        "policy":"FAIL_CLOSED_EVIDENCE_DRIVEN",
        "flags":flags,
        "tempus":tempus,
        "citation_anomalies":anomalies,
        "boundary_checks":boundaries,
        "gates":gates,
        "reasoning_levels":level_notes,
        "guarded_synthesis":" ".join(_uniq(modules,20)),
        "professional_verification":"PENDING",
    }


def apply_reasoning_guard(result: Dict, text: str) -> Dict:
    """Apply the guard after deterministic/AI synthesis without deleting source facts."""
    result=dict(result or {})
    domain=result.get("domain_contract") or result.get("domain_classification") or {}
    guard=build_reasoning_guard(text,domain)
    prior=str(result.get("legal_analysis") or "").strip()
    if prior and prior != guard["guarded_synthesis"]:
        result["unguarded_legal_analysis"] = prior
    result["reasoning_guard"] = guard
    result["legal_analysis"] = guard["guarded_synthesis"]

    issues=list(result.get("legal_issues") or [])
    t=guard.get("tempus") or {}
    if t.get("status") in ("TEMPUS_INSUFFICIENT","TEMPUS_TRANSITION_REVIEW_REQUIRED","TEMPUS_REQUIRES_EVENT_DATE"):
        issues.insert(0,"Tempus delicti dan ketentuan peralihan harus diverifikasi sebelum menetapkan norma pidana materiil yang berlaku.")
    for b in guard.get("boundary_checks") or []:
        if b.get("code")=="FORUM_VS_MERITS": issues.append("Apakah dalil ketidakwenangan forum benar-benar isu kompetensi, atau sebenarnya bantahan terhadap terpenuhinya unsur/pokok perkara?")
        elif b.get("code")=="ERROR_IN_PERSONA_VS_ATTRIBUTION": issues.append("Apakah dalil error in persona merupakan salah identitas terdakwa, atau hanya sengketa atribusi pertanggungjawaban kepada pihak lain?")
    if guard.get("citation_anomalies"):
        issues.append("Verifikasi identitas/tahun peraturan yang dikutip terhadap surat dakwaan asli; jangan melakukan koreksi otomatis.")
    result["legal_issues"]=_uniq(issues,18)

    recs=list(result.get("recommendations") or [])
    if guard.get("citation_anomalies"):
        recs.insert(0,"Cocokkan seluruh nomor/tahun undang-undang dengan surat dakwaan asli dan sumber resmi sebelum menggunakan rujukan tersebut dalam eksepsi atau analisis merits.")
    if t.get("status") in ("TEMPUS_INSUFFICIENT","TEMPUS_TRANSITION_REVIEW_REQUIRED","TEMPUS_REQUIRES_EVENT_DATE"):
        recs.insert(0,"Kunci tanggal/tahun setiap perbuatan yang didakwakan dan lakukan matriks Tempus → Norma saat perbuatan → Perubahan/peralihan → Norma yang dapat diterapkan.")
    result["recommendations"]=_uniq(recs,18)
    return result
