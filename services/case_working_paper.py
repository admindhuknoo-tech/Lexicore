"""Structured working-paper layer for Menu 6 Case Analysis.

Builds four sequential components:
1) case-analysis readiness/completeness score with positive/negative variables,
2) evidence correlation matrix,
3) legal construction linking fact -> evidence -> rule -> causal effect,
4) tactical step-by-step action plan.

The percentage is a readiness/completeness indicator for the current record, not a
prediction of a court's future decision. Professional verification remains required.
"""
from __future__ import annotations

import re
from typing import Dict, List, Any

from services.case_consistency_guard import evidence_rows, ranked_support_for_issue


def _text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return " ".join(_text(x) for x in v.values())
    if isinstance(v, (list, tuple, set)):
        return " ".join(_text(x) for x in v)
    return str(v)


def _uniq(items, limit=20):
    out=[]; seen=set()
    for item in items or []:
        s=re.sub(r"\s+", " ", str(item or "")).strip()
        if not s: continue
        k=re.sub(r"\W+", " ", s.lower()).strip()
        if k in seen: continue
        seen.add(k); out.append(s)
        if len(out)>=limit: break
    return out


def _verified_regulation_counts(result: Dict) -> tuple[int, int, int]:
    """Count only legally coherent verification states.

    Provision verification contributes to the merits score only when the same
    instrument is identity-confirmed, case-nexus verified, tempus verified and
    finally VERIFIED_APPLICABLE.  A matching article number in an irrelevant or
    identity-mismatched instrument must never create a legal-verification bonus.
    """
    snap=result.get("case_regulatory_snapshot") or {}
    rows=snap.get("official_results") or []
    verified=0; applicable=0; provision=0
    for row in rows:
        if not isinstance(row, dict): continue
        v=row.get("positive_law_verification") or {}
        if v.get("legal_status") in ("IN_FORCE","AMENDED_IN_FORCE") and v.get("identity_confirmed"):
            verified += 1
        coherent=(v.get("final_status") == "VERIFIED_APPLICABLE"
                  and v.get("identity_confirmed") is True
                  and v.get("case_nexus_status") == "CASE_NEXUS_VERIFIED"
                  and v.get("tempus_status") == "TEMPUS_VERIFIED"
                  and v.get("tempus_applicable") is True)
        if coherent:
            applicable += 1
            pv=v.get("provision_verification") or {}
            if pv.get("status") in ("PROVISION_VERIFIED","PROVISION_PARTIALLY_VERIFIED"):
                provision += int(pv.get("verified_count") or 0)
    return verified, applicable, provision


def _analysis_readiness(result: Dict) -> Dict:
    readiness=result.get("case_readiness") or {}
    comp=readiness.get("components") or {}
    evidence_pct=float((comp.get("evidence_map") or {}).get("percentage") or 0)
    legal_pct=float((comp.get("legal_analysis") or {}).get("percentage") or 0)
    gaps=len(result.get("evidentiary_gaps") or [])
    pros=_uniq(result.get("arguments_for") or [], 8)
    cons=_uniq(result.get("arguments_against") or [], 8)
    verified, applicable, provision=_verified_regulation_counts(result)

    variables_plus=[]; variables_minus=[]
    score=50.0

    # Evidence contribution is deliberately bounded. It measures support in the
    # present record, not truth or final admissibility.
    ev_delta=max(-12.0, min(12.0, (evidence_pct-50.0)*0.24))
    score += ev_delta
    if ev_delta >= 0:
        variables_plus.append({"variable":"Kelengkapan bukti terpetakan","impact":round(ev_delta,1),"basis":f"Pemetaan Bukti {evidence_pct:.0f}%"})
    else:
        variables_minus.append({"variable":"Kelengkapan bukti belum memadai","impact":round(ev_delta,1),"basis":f"Pemetaan Bukti {evidence_pct:.0f}%"})

    legal_delta=max(-7.0, min(7.0, (legal_pct-50.0)*0.14))
    score += legal_delta
    target=variables_plus if legal_delta>=0 else variables_minus
    target.append({"variable":"Kematangan konstruksi hukum" if legal_delta>=0 else "Konstruksi hukum belum lengkap","impact":round(legal_delta,1),"basis":f"Analisis Hukum {legal_pct:.0f}%"})

    arg_delta=max(-8.0, min(8.0, (len(pros)-len(cons))*1.5))
    score += arg_delta
    if pros:
        variables_plus.append({"variable":"Faktor yang mendukung posisi klien","impact":round(max(0,arg_delta),1),"basis":"; ".join(pros[:3])})
    if cons:
        variables_minus.append({"variable":"Bantahan / eksposur pihak lawan","impact":round(min(0,arg_delta),1),"basis":"; ".join(cons[:3])})

    gap_penalty=min(15.0, gaps*2.5)
    score -= gap_penalty
    if gaps:
        variables_minus.append({"variable":"Celah pembuktian material","impact":round(-gap_penalty,1),"basis":"; ".join(_uniq(result.get("evidentiary_gaps") or [],3))})

    law_bonus=min(10.0, applicable*2.0 + provision*2.0)
    score += law_bonus
    if law_bonus:
        variables_plus.append({"variable":"Dasar hukum resmi yang telah lolos verifikasi","impact":round(law_bonus,1),"basis":f"Regulasi terverifikasi relevan dan berlaku={applicable}; pasal terverifikasi={provision}"})
    elif applicable == 0 and provision == 0:
        # Instrument identity/status alone is not enough to improve case readiness.
        # Readiness may rise only after a regulation survives the case-nexus,
        # tempus and applicability gates.  This prevents transient or false-positive
        # source verification from inflating the working-paper score.
        score -= 4.0
        variables_minus.append({
            "variable":"Dasar hukum positif belum terverifikasi memadai",
            "impact":-4.0,
            "basis":"Belum ada regulasi resmi yang lolos seluruh gate identitas, keterkaitan perkara, tempus, dan keberlakuan pada perkara."
        })

    # Keep a legal working-paper estimate away from artificial 0/100 certainty.
    score=int(round(max(15.0, min(85.0, score))))
    evidence_required=int((comp.get("evidence_map") or {}).get("required") or 0)
    evidence_fulfilled=int((comp.get("evidence_map") or {}).get("fulfilled") or 0)
    confidence="LOW"
    if evidence_required and evidence_fulfilled/evidence_required >= .65 and applicable >= 1:
        confidence="MEDIUM"
    if evidence_required and evidence_fulfilled/evidence_required >= .85 and applicable >= 2 and provision >= 1:
        confidence="MEDIUM-HIGH"
    return {
        "metric":"CASE_ANALYSIS_READINESS",
        "label":"Case Readiness / Analysis Completeness",
        "percentage":score,
        "confidence":confidence,
        "variables_increasing":variables_plus,
        "variables_decreasing":variables_minus,
        "disclaimer":"Persentase ini mengukur kesiapan dan kelengkapan analisis berdasarkan record yang tersedia; bukan peluang menang/kalah, bukan prediksi putusan, dan wajib diperbarui bila bukti, dalil lawan, forum, atau hukum positif berubah."
    }


def _evidence_basis(result: Dict) -> Dict:
    domains=set((result.get("domain_classification") or {}).get("domain_contract") or [])
    posture=str(result.get("case_posture") or "").upper()
    criminal=("criminal" in domains or "corruption" in domains or "PIDANA" in posture or "PENYIDIKAN" in posture)
    if criminal:
        return {
            "system":"CRIMINAL",
            "citation":"KUHAP yang berlaku pada tanggal proses — verifikasi pasal alat bukti melalui tempus engine",
            "note":"Pasal 184 KUHAP lama tidak di-hard-code sebagai dasar final karena nomor/struktur pasal harus mengikuti KUHAP yang berlaku pada tanggal prosedural."
        }
    return {
        "system":"CIVIL",
        "citation":"Pasal 1866 KUHPerdata — kandidat dasar klasifikasi alat bukti perdata; verifikasi bunyi/status pasal pada sumber resmi sebelum penggunaan final",
        "note":"Klasifikasi formal tetap bergantung pada jenis dokumen asli, autentikasi, relevansi, dan aturan pembuktian khusus yang berlaku."
    }


def _classify_evidence(item: Dict, system: str) -> tuple[str,str]:
    label=str(item.get("label") or "SOURCE FACT").upper()
    s=(str(item.get("statement") or "")+" "+str(item.get("evidence") or "")).lower()
    if any(k in s for k in ("akta","sertipikat","sertifikat","surat ","perjanjian","kwitansi","rekening","dokumen","relaas","buku tanah","skpt")) or label in ("DOCUMENT","LEGAL_REFERENCE"):
        return "Bukti surat/dokumen", "SEDANG — jenis dokumen teridentifikasi; keaslian, originalitas, hubungan dengan fakta, dan admissibility belum diverifikasi."
    if "saksi" in s or "keterangan saksi" in s:
        return "Keterangan saksi", "SEDANG — relevansi dapat dinilai, tetapi kapasitas, sumber pengetahuan, konsistensi, dan pemeriksaan silang belum tersedia."
    if label=="ADMISSION" or "mengakui" in s or "pengakuan" in s:
        return "Pengakuan / admission", "SEDANG — perlu dipastikan siapa yang membuat, konteks, ruang lingkup, dan apakah mempunyai nilai pembuktian formal."
    if any(k in s for k in ("email","whatsapp","chat","rekaman","elektronik","screenshot","metadata")):
        return "Bukti elektronik/digital", "SEDANG — substansi terindikasi, tetapi integritas, metadata, chain of custody, dan dasar hukum elektronik harus diverifikasi."
    if system=="CRIMINAL" and any(k in s for k in ("ahli","forensik","audit")):
        return "Keterangan ahli / hasil pemeriksaan ahli", "SEDANG — kompetensi ahli, metodologi, dan keterkaitan dengan unsur tindak pidana perlu diuji."
    return "Dalil/fakta sumber — belum terklasifikasi sebagai alat bukti formal", "RENDAH — baru teridentifikasi dari narasi/pleading; belum cukup untuk dianggap alat bukti formal."


def _opponent_weakness(item: Dict, strength: str) -> str:
    s=(str(item.get("statement") or "")+" "+str(item.get("evidence") or "")).lower()
    if "tanpa" in s and any(k in s for k in ("ijin","izin","sepengetahuan","dokumen")):
        return "Uji lawan pada dasar kewenangan/persetujuan, bukti pemberitahuan, serta dokumen pembanding yang menyangkal klaim 'tanpa izin/sepengetahuan'."
    if "sertipikat" in s or "sertifikat" in s:
        return "Minta dokumen dasar penerbitan, warkah, riwayat peralihan, data fisik/yuridis, dan bukti yang menyerang atau menguatkan asal-usul hak."
    if strength.startswith("RENDAH"):
        return "Serang sebagai dalil yang belum ditopang bukti primer, belum terautentikasi, atau belum memiliki nexus langsung dengan unsur/posita yang harus dibuktikan."
    return "Uji autentikasi, relevansi, konsistensi internal, tempus, sumber pengetahuan, serta bukti kontra yang memutus hubungan antara bukti dan fakta yang diklaim."


def _evidence_matrix(result: Dict) -> Dict:
    basis=_evidence_basis(result)
    ledger=result.get("source_ledger") or []
    # v1.3.13.11.10: metadata, identity blocks, headings and bare legal
    # references are not promoted into the evidentiary matrix.  The source
    # ledger still preserves them for traceability.
    rows=evidence_rows(ledger,basis["system"],limit=28)
    # evidence_rows preserves the canonical opponent_evidence_weakness field
    # consumed by UI/exporters while applying the stricter source classifier.
    return {"legal_basis":basis,"rows":rows}


def _law_candidates(result: Dict) -> List[str]:
    out=[]
    for item in result.get("applicable_law") or []:
        if isinstance(item,dict):
            s=item.get("source") or item.get("regulation") or item.get("qualified_citation") or item.get("title")
        else: s=item
        if s: out.append(str(s))
    snap=result.get("case_regulatory_snapshot") or {}
    for row in snap.get("official_results") or []:
        if not isinstance(row,dict): continue
        v=row.get("positive_law_verification") or {}
        if v.get("final_status") != "VERIFIED_APPLICABLE": continue
        pv=v.get("provision_verification") or {}
        p=", ".join(pv.get("verified") or [])
        title=row.get("title") or "Regulasi terverifikasi"
        out.append(f"{title}"+(f" — {p}" if p else ""))
    return _uniq(out,12)


def _legal_construction(result: Dict, matrix: Dict) -> Dict:
    issues=_uniq(result.get("legal_issues") or [], 8)
    laws=_law_candidates(result)
    ledger=result.get("source_ledger") or []
    chains=[]
    for issue in issues[:6]:
        ranked=ranked_support_for_issue(issue,ledger,limit=2)
        best=ranked[0] if ranked else None
        # Never pair an issue with an arbitrary same-index fact/evidence row.
        # If no semantic nexus is found, fail closed and say so explicitly.
        material_fact=(best.get("statement") if best else "Belum ditemukan fakta sumber dengan nexus semantik yang cukup untuk isu ini.")
        supporting=(best.get("classification") if best else "Bukti primer belum terpetakan")
        evidence_ref=(best.get("statement") if best else "-")
        nexus_score=(best.get("score") if best else 0.0)
        nexus_reason=(best.get("reason") if best else "Tidak ada pasangan fakta/bukti yang lolos ambang nexus.")
        probative_score=(best.get("probative_score") if best else 0.0)
        probative_level=(best.get("probative_level") if best else "NONE")
        probative_sufficient=bool(best.get("probative_sufficient")) if best else False
        probative_reason=(best.get("probative_reason") if best else "Belum ada sumber dengan bobot pembuktian yang cukup untuk isu ini.")

        # Rule selection is also fail-closed.  A rule may be shown only from the
        # already filtered applicable-law candidate list; absence of one is not
        # filled by cycling through an unrelated instrument.
        issue_low=issue.lower(); rule="Dasar hukum spesifik belum terverifikasi."
        for candidate in laws:
            cl=candidate.lower()
            if any(k in issue_low and k in cl for k in ("pidana","tipikor","korupsi","kredit","bank","fidusia","tempus","acara")):
                rule=candidate; break
        if rule.startswith("Dasar hukum") and len(laws)==1:
            rule=laws[0]

        status="REQUIRES_VERIFICATION"
        if best and not probative_sufficient:
            status="SEMANTIC_NEXUS_ONLY"
        elif best and rule != "Dasar hukum spesifik belum terverifikasi.":
            status="PROVISIONALLY_SUPPORTED"
        elif best:
            status="EVIDENCE_NEXUS_FOUND_LAW_UNVERIFIED"
        chains.append({
            "issue":issue,
            "material_fact":material_fact,
            "supporting_evidence":supporting,
            "evidence_reference":evidence_ref,
            "evidence_nexus_score":nexus_score,
            "evidence_nexus_reason":nexus_reason,
            "probative_score":probative_score,
            "probative_level":probative_level,
            "probative_sufficient":probative_sufficient,
            "probative_reason":probative_reason,
            "legal_rule":rule,
            "causal_logic":(("Sumber memiliki keterkaitan topik dengan isu, namun daya buktinya harus dinilai terpisah. " + probative_reason) if best else "Tidak boleh dibentuk jalinan kausalitas sebelum ditemukan fakta/bukti sumber yang benar-benar terkait dengan isu ini."),
            "construction_status":status
        })
    synthesis=str(result.get("legal_analysis") or "").strip()
    if not synthesis:
        synthesis="Konstruksi hukum belum dapat disimpulkan final sebelum fakta material, alat bukti primer, dan norma yang berlaku pada tempus perkara diverifikasi secara berantai."
    return {"synthesis":synthesis,"chains":chains}


def _domain_steps(result: Dict) -> List[Dict]:
    domains=set((result.get("domain_classification") or {}).get("domain_contract") or [])
    steps=[]
    civil=bool(domains & {"civil_contract","civil_procedure","land_property","religious_court","employment"})
    criminal=bool(domains & {"criminal","corruption"})
    if civil:
        steps.extend([
            {"priority":"P2","time_window":"3–7 hari","action":"Susun posisi pra-litigasi/somasi atau tanggapan formal berdasarkan hubungan hukum dan bukti yang sudah tervalidasi.","condition":"Jika sengketa masih dapat/harus ditempuh melalui pemberitahuan atau upaya pra-litigasi."},
            {"priority":"P2","time_window":"7–14 hari","action":"Finalisasi forum, kompetensi, para pihak, posita, petitum, dan daftar bukti untuk pendaftaran perkara jika penyelesaian pra-litigasi tidak tercapai.","condition":"Jika dasar gugatan/permohonan dan forum telah terverifikasi."},
            {"priority":"P3","time_window":"Saat pendaftaran/awal persidangan","action":"Nilai kebutuhan sita jaminan/conservatoir beslag atau tindakan provisi lain berdasarkan risiko pengalihan aset/objek dan syarat formil yang dapat dibuktikan.","condition":"Hanya jika fakta konkret dan syarat hukum tindakan provisi terpenuhi."},
        ])
    if criminal:
        steps.extend([
            {"priority":"P2","time_window":"3–7 hari","action":"Kunci kronologi, sumber bukti, chain of custody, dan kesesuaian setiap alat bukti dengan unsur pasal yang benar-benar berlaku pada tempus perkara.","condition":"Sebelum menetapkan strategi pembelaan/penuntutan final."},
            {"priority":"P2","time_window":"7–14 hari","action":"Susun matriks unsur-versus-bukti dan identifikasi bukti ekskulpatoris, saksi/ahli, serta keberatan prosedural yang mempunyai dasar faktual.","condition":"Setelah berkas/bukti utama tersedia."},
        ])
    return steps


def _tactical_action_plan(result: Dict) -> List[Dict]:
    base=result.get("action_plan") or []
    rows=[]; step=1
    windows={"P1":"0–3 hari","P2":"3–7 hari","P3":"7–14 hari"}
    for item in base[:10]:
        if not isinstance(item,dict): continue
        pr=str(item.get("priority") or "P2").upper()
        rows.append({
            "step":step,
            "priority":pr,
            "time_window":windows.get(pr,"3–7 hari"),
            "action":item.get("action") or item.get("issue") or "Tindak lanjut perkara",
            "objective":item.get("issue") or "Menutup gap analitis/pembuktian",
            "condition":item.get("current_status") or "PERLU DIUJI",
            "why_it_matters":item.get("why_it_matters") or ""
        }); step+=1
    existing=" ".join(str(r.get("action") or "").lower() for r in rows)
    for item in _domain_steps(result):
        key=str(item.get("action") or "").lower().split(" ")[:4]
        if key and " ".join(key) in existing: continue
        rows.append({"step":step,"priority":item["priority"],"time_window":item["time_window"],"action":item["action"],"objective":"Langkah taktis bersyarat","condition":item["condition"],"why_it_matters":"Harus disesuaikan dengan posture, forum, tempus, dan bukti aktual."}); step+=1
        if len(rows)>=14: break
    return rows


def build_case_working_paper(result: Dict) -> Dict:
    """Return the canonical four-part working paper without mutating core analysis."""
    evidence=_evidence_matrix(result)
    return {
        "format_version":"1.0",
        "working_paper_percentage":_analysis_readiness(result),
        "evidence_map":evidence,
        "legal_construction":_legal_construction(result,evidence),
        "action_plan":_tactical_action_plan(result),
        "professional_verification":"PENDING"
    }
