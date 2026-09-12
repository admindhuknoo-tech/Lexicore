"""Element-based legal reasoning gate for Case Analysis.

Turns issue spotting into an auditable matrix: element -> factual support -> evidence
support -> applicable-law gate -> counter-evidence -> status. This is deliberately
conservative: it can downgrade an AI conclusion, never manufacture proof.
"""
from __future__ import annotations
import re
from typing import Any, Dict, Iterable, List


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _uniq(items: Iterable[str], limit: int = 20) -> List[str]:
    out=[]; seen=set()
    for x in items or []:
        s=_clean(x); k=s.lower()
        if not s or k in seen: continue
        seen.add(k); out.append(s)
        if len(out)>=limit: break
    return out


def _terms(name: str) -> List[str]:
    n=_clean(name).lower()
    groups={
      "authority":["kewenangan","otoritas","jabatan","wewenang","pemutus","menyetujui","memutus"],
      "act":["perbuatan","menyimpang","penyalahgunaan","melakukan","persetujuan","pencairan","pemberian kredit"],
      "intent":["mens rea","niat","tujuan menguntungkan","keuntungan","fee","kickback","afiliasi","aliran dana","menerima"],
      "loss":["kerugian","actual loss","kerugian negara","kerugian keuangan","outstanding","pemulihan","agunan"],
      "causation":["kausalitas","causal","sebab","hubungan langsung","intervening","akibat"],
      "responsibility":["personal responsibility","tanggung jawab","atribusi","peran","individual"],
      "procedure":["prosedur","sop","tata kelola","perkreditan","5c","survei","survey","analisa"],
      "tempus":["tempus","tanggal","waktu","berlaku"],
      "forum":["kompetensi","forum","berwenang mengadili"],
    }
    out=[]
    for key, vals in groups.items():
        if any(v in n for v in vals): out.append(key)
    return out or ["general"]


def _evidence_texts(result: Dict[str,Any]) -> List[str]:
    rows=result.get("evidence_map") or result.get("evidence_rows") or []
    out=[]
    for r in rows:
        if isinstance(r,dict):
            out.append(_clean(" ".join(str(r.get(k) or "") for k in ("fact_proved","statement","evidence","formal_strength"))))
    if not out:
        for r in result.get("material_source_ledger") or result.get("source_ledger") or []:
            if isinstance(r,dict): out.append(_clean(r.get("statement") or r.get("text") or ""))
    return _uniq(out, 120)


def _support(element: str, texts: List[str]) -> Dict[str,Any]:
    ts=_terms(element)
    hits=[]
    for i,t in enumerate(texts):
        low=t.lower()
        if any((term in low) for term in ts for _ in [0]):
            hits.append((i,t))
    # Require more than generic role words for high status.
    strong=0
    for _,t in hits:
        low=t.lower()
        if any(x in low for x in ("dokumen", "bukti", "notulen", "rekening", "audit", "bap", "surat", "perjanjian", "laporan", "berita acara")):
            strong += 1
    return {"hits":hits[:8],"count":len(hits),"strong_count":strong}


def _law_gate(result: Dict[str,Any]) -> Dict[str,Any]:
    snap=result.get("case_regulatory_snapshot") or {}
    rows=snap.get("official_results") or []
    coherent=0; provisions=0
    for row in rows:
        if not isinstance(row,dict): continue
        v=row.get("positive_law_verification") or {}
        if (v.get("final_status") == "VERIFIED_APPLICABLE" and v.get("identity_confirmed") is True
            and v.get("case_nexus_status") == "CASE_NEXUS_VERIFIED" and v.get("tempus_status") == "TEMPUS_VERIFIED"
            and v.get("tempus_applicable") is True):
            coherent += 1
            pv=v.get("provision_verification") or {}
            provisions += int(pv.get("verified_count") or 0) if pv.get("status") in ("PROVISION_VERIFIED","PROVISION_PARTIALLY_VERIFIED") else 0
    return {"coherent_instruments":coherent,"verified_provisions":provisions,"verified":coherent>0 and provisions>0}


def build_element_reasoning(result: Dict[str,Any]) -> Dict[str,Any]:
    elements=result.get("element_matrix") or []
    if not elements:
        return {"status":"NOT_ASSESSED","elements":[],"overall_status":"INSUFFICIENT_RECORD","release_rule":"No element matrix available."}
    texts=_evidence_texts(result); law=_law_gate(result)
    out=[]; proved=0; disputed=0; gaps=0
    for raw in elements:
        if not isinstance(raw,dict): continue
        name=_clean(raw.get("element") or "Unspecified element")
        sup=_support(name,texts)
        opposition=_clean(raw.get("defense_focus") or raw.get("opposition") or "Belum ada counter-evidence terpetakan secara eksplisit.")
        original=_clean(raw.get("status") or "NEEDS_EVIDENCE").upper()
        if sup["count"] == 0:
            status="NOT_ESTABLISHED"; gaps += 1
        elif sup["strong_count"] >= 2 and law["verified"] and original in {"SUPPORTED","PROVED"}:
            status="SUPPORTED"; proved += 1
        elif sup["strong_count"] >= 1 and original == "SUPPORTED" and law["verified"]:
            status="SUPPORTED"; proved += 1
        else:
            status="DISPUTED" if original in {"DISPUTED","MUST_BE_PROVEN"} or sup["count"]>0 else "NEEDS_EVIDENCE"
            disputed += 1
        out.append({
          "element":name,
          "status":status,
          "source_status":original,
          "supporting_source_count":sup["count"],
          "strong_evidence_source_count":sup["strong_count"],
          "supporting_sources":[t[:700] for _,t in sup["hits"]],
          "issue": _clean(raw.get("issue") or raw.get("legal_issue") or name),
          "applicable_law": _clean(raw.get("applicable_law") or raw.get("rule") or raw.get("norm") or "Norma/pasal belum terkunci secara terverifikasi."),
          "alleged_act": _clean(raw.get("alleged_act") or raw.get("prosecution_support") or raw.get("support") or "Perbuatan yang didalilkan belum dipetakan secara individual."),
          "evidence": [t[:700] for _,t in sup["hits"]],
          "counter_evidence": _uniq([opposition, _clean(raw.get("counter_evidence") or "")], 8),
          "element_test": ("PASS_WITH_VERIFIED_SUPPORT" if status=="SUPPORTED" else "FAIL_OR_INCOMPLETE"),
          "causation": _clean(raw.get("causation") or "Hubungan kausal belum dapat dianggap terbukti hanya dari nexus semantik."),
          "risk": _clean(raw.get("risk") or ("Risk tinggi: unsur belum established atau norma belum verified." if status != "SUPPORTED" else "Risk residual: admissibility, counter-evidence, dan judicial assessment.")),
          "procedural_merits": _clean(raw.get("procedural_merits") or raw.get("classification") or "MERITS"),
          "prosecution_theory":_clean(raw.get("prosecution_support") or raw.get("support") or ""),
          "defense_counterpoint":opposition,
          "legal_gate":"VERIFIED" if law["verified"] else "NOT_VERIFIED",
          "release_explanation":("Dapat dipertimbangkan sebagai supported hanya bila bukti material dan norma terverifikasi." if status=="SUPPORTED" else "Belum cukup untuk legal conclusion final; perlu bukti, counter-evidence, atau verifikasi norma.")
        })
    n=len(out)
    if not law["verified"]:
        overall="PROVISIONAL_LEGAL_ANALYSIS"
    elif gaps:
        overall="INSUFFICIENT_RECORD"
    elif proved==n and n:
        overall="SUPPORTED_WITH_VERIFIED_NORMS"
    elif disputed:
        overall="CONTESTED_ELEMENTS"
    else:
        overall="INSUFFICIENT_RECORD"
    established=[x["element"] for x in out if x["status"]=="SUPPORTED"]
    not_est=[x["element"] for x in out if x["status"] in {"NOT_ESTABLISHED","NEEDS_EVIDENCE"}]
    contested=[x["element"] for x in out if x["status"]=="DISPUTED"]
    conclusion=(
      "Tidak ada dasar untuk legal conclusion final karena verifikasi norma positif belum lengkap."
      if not law["verified"] else
      ("Sebagian unsur telah didukung, tetapi masih ada unsur yang belum established sehingga kesimpulan final harus ditahan."
       if not_est or contested else
       "Seluruh unsur yang dipetakan memiliki dukungan record dan norma terverifikasi; tetap tunduk pada professional verification dan admissibility."))
    return {
      "status":"COMPLETED","overall_status":overall,
      "law_gate":law,"elements":out,
      "decision_summary":{"already_established":established,"not_yet_established":not_est,"contested":contested,"must_be_verified":[] if law["verified"] else ["Identitas, status berlaku, tempus, case nexus, dan pasal yang diterapkan"]},
      "legal_conclusion":conclusion,
      "method":"ISSUE_LAW_ELEMENT_ACT_EVIDENCE_COUNTER_TEST_CAUSATION_RISK_ACTION_V2",
      "disclaimer":"Status ini adalah analisis berbasis record dan gate verifikasi, bukan putusan pengadilan atau jaminan hasil perkara."
    }
