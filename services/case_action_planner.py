"""Precision action planning for Case Analysis.

Converts the existing legal review + element reasoning into an auditable,
case-specific execution plan. The planner does not decide guilt, liability,
or litigation outcome; it decides what should be verified, collected,
constructed, or drafted next, and why.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

from services.case_role_detector import detect_case_role
from services.positive_law_verification import extract_provision_refs, normalize_provision_ref


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _uniq(items: List[str], limit: int = 20) -> List[str]:
    out, seen = [], set()
    for item in items or []:
        s = _clean(item)
        k = s.lower()
        if not s or k in seen:
            continue
        seen.add(k); out.append(s)
        if len(out) >= limit: break
    return out


def _doc_type(result: Dict[str, Any]) -> str:
    return _clean((result.get("professional_review") or {}).get("document_structure", {}).get("document_type") or "LEGAL_DOCUMENT").upper()


def _is_objection(result: Dict[str, Any]) -> bool:
    sr = (result.get("professional_review") or {}).get("strategic_recommendation") or {}
    return _doc_type(result) == "EKSEPSI_OR_OBJECTION" or sr.get("approach") == "REBUILD_OBJECTION_AROUND_FORMAL_DEFECTS"


def _is_corruption_credit(result: Dict[str, Any]) -> bool:
    dc = result.get("domain_classification") or {}
    domains = set(dc.get("domain_contract") or [])
    return bool(domains & {"corruption", "financial_services"}) or bool(result.get("is_corruption")) or bool(result.get("is_credit"))


def _element_rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [x for x in ((result.get("element_reasoning") or {}).get("elements") or []) if isinstance(x, dict)]


def _findings(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [x for x in ((result.get("professional_review") or {}).get("findings") or []) if isinstance(x, dict)]


def _has_finding(result: Dict[str, Any], *types: str) -> bool:
    return any(str(f.get("type") or "") in types for f in _findings(result))


def _law_verified(result: Dict[str, Any]) -> bool:
    return bool((result.get("element_reasoning") or {}).get("law_gate", {}).get("verified"))


def _add(rows: List[Dict[str, Any]], *, priority: str, issue: str, action: str,
        objective: str, why: str, deliverable: str, success: str,
        dependency: str = "Tidak ada", owner: str = "Lawyer / Case Team",
        category: str = "VERIFY", related_elements: List[str] | None = None,
        evidence_targets: List[str] | None = None, source_basis: List[str] | None = None,
        risk_if_skipped: str = "Gap tetap terbuka dan dapat melemahkan posisi hukum.") -> None:
    rows.append({
        "priority": priority, "category": category, "issue": issue,
        "action": action, "objective": objective, "why_it_matters": why,
        "deliverable": deliverable, "success_criteria": success,
        "dependency": dependency, "owner": owner,
        "related_elements": _uniq(related_elements or [], 8),
        "evidence_targets": _uniq(evidence_targets or [], 8),
        "source_basis": _uniq(source_basis or [], 6),
        "risk_if_skipped": risk_if_skipped,
    })


# ---------------------------------------------------------------------------
# General procedural playbook (HIR/RBg/KUHAP-based), keyed by
# (ranah_hukum, posisi_pengguna). This is deliberately additive: it only fires
# when neither the Kasus-A objection path nor the Kasus-A corruption/credit
# merits path claimed the case (see `_precision_actions`), so it never changes
# behavior for the two flows the existing test suite already pins down. It
# exists to close the generalization gap the objection/corr_credit branches
# do not cover: any other (ranah_hukum, posisi_pengguna) combination
# previously produced zero procedural/tactical actions, only generic
# gap-closing ones.
# ---------------------------------------------------------------------------

def _role_based_procedural_actions(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    source_text = result.get("source_text") or result.get("text") or ""
    role = detect_case_role(source_text, result)
    ranah = role.get("ranah_hukum")
    posisi = role.get("posisi_pengguna")
    role_basis = [f"Role detection: ranah_hukum={ranah} ({role.get('basis')})",
                  f"Role detection: posisi_pengguna={posisi} (confidence={role.get('confidence')})"]

    if ranah == "PERDATA" and posisi == "TERGUGAT":
        _add(rows, priority="P1", category="PROCEDURAL",
             issue="Eksepsi Kompetensi (Relatif/Absolut)",
             action="Uji domisili hukum para pihak, klausul forum/kompetensi dalam perjanjian, dan kesesuaian objek sengketa dengan kompetensi absolut pengadilan yang dituju.",
             objective="Menentukan apakah gugatan diajukan di forum yang berwenang sebelum masuk ke pokok perkara.",
             why="Eksepsi kompetensi adalah langkah pertama hukum acara perdata (HIR/RBg) yang wajib diuji sebelum jawaban atas pokok perkara.",
             deliverable="Memo Eksepsi Kompetensi + dasar domisili/klausul forum",
             success="Kompetensi relatif dan absolut pengadilan tervalidasi terhadap objek sengketa dan domisili para pihak.",
             evidence_targets=["Perjanjian/akta dasar hubungan hukum", "Bukti domisili/alamat resmi para pihak", "Surat gugatan asli"],
             source_basis=role_basis + ["Hukum Acara Perdata (HIR/RBg)"],
             risk_if_skipped="Tergugat kehilangan kesempatan menguji forum sebelum terikat pada pokok perkara.")
        _add(rows, priority="P1", category="DRAFT",
             issue="Draf Jawaban Gugatan",
             action="Bantah posita gugatan satu per satu (fakta, hubungan hukum, dan dalil kerugian), dan pasangkan setiap bantahan dengan bukti primer yang tersedia.",
             objective="Menyusun jawaban yang terstruktur dan tertaut langsung ke posita penggugat, bukan bantahan umum.",
             why="Jawaban yang tidak menjawab posita secara spesifik berisiko dianggap tidak membantah (dalil dianggap diakui).",
             deliverable="Draf Jawaban Gugatan per-posita",
             success="Setiap posita material memiliki bantahan eksplisit dan rujukan bukti.",
             evidence_targets=["Dokumen/bukti kontra posita", "Perjanjian/korespondensi terkait"],
             source_basis=role_basis,
             risk_if_skipped="Posita yang tidak dibantah secara eksplisit dapat dianggap diakui.")
        _add(rows, priority="P2", category="PROCEDURAL",
             issue="Kelayakan Gugatan Rekonvensi (Balik)",
             action="Nilai apakah tergugat memiliki dasar faktual dan hukum untuk mengajukan gugatan balik dalam perkara yang sama (misal wanprestasi timbal balik atau kerugian akibat gugatan).",
             objective="Memanfaatkan forum yang sama untuk klaim balik jika secara faktual dan yuridis relevan.",
             why="Rekonvensi harus diajukan bersama jawaban pertama; kesempatan hilang jika terlewat.",
             deliverable="Analisis kelayakan + draf rekonvensi (jika layak)",
             success="Keputusan terdokumentasi mengenai layak/tidaknya rekonvensi beserta dasarnya.",
             evidence_targets=["Bukti kerugian tergugat", "Dasar hubungan hukum timbal balik"],
             source_basis=role_basis,
             risk_if_skipped="Klaim balik yang sah dapat hilang karena tidak diajukan pada kesempatan pertama.")

    elif ranah == "PERDATA" and posisi == "PENGGUGAT":
        _add(rows, priority="P1", category="LEGAL_VERIFY",
             issue="Legal standing dan syarat formil gugatan",
             action="Verifikasi kapasitas hukum penggugat, kelengkapan surat kuasa, dan kesesuaian format gugatan (identitas, posita, petitum) dengan HIR/RBg.",
             objective="Mencegah gugatan gugur karena cacat formil sebelum masuk pokok perkara.",
             why="Cacat formil adalah alasan paling umum eksepsi tergugat yang dapat menunda atau menggugurkan gugatan.",
             deliverable="Checklist syarat formil gugatan",
             success="Seluruh syarat formil (identitas, kuasa, posita-petitum) terverifikasi lengkap.",
             evidence_targets=["Surat kuasa khusus", "Identitas resmi para pihak"],
             source_basis=role_basis,
             risk_if_skipped="Gugatan berisiko dieksepsi cacat formil sebelum pokok perkara diuji.")
        _add(rows, priority="P1", category="DRAFT",
             issue="Koherensi posita-petitum dengan alat bukti primer",
             action="Pastikan setiap petitum bertumpu pada posita yang didukung alat bukti primer yang sudah terverifikasi.",
             objective="Menghindari petitum yang tidak didukung dalil atau dalil yang tidak dituntut.",
             why="Ketidaksesuaian posita-petitum adalah celah umum yang dieksploitasi lewat eksepsi obscuur libel.",
             deliverable="Matriks Posita → Bukti → Petitum",
             success="Setiap petitum tertaut pada posita dan bukti yang jelas.",
             evidence_targets=["Bukti pendukung tiap posita"],
             source_basis=role_basis,
             risk_if_skipped="Risiko eksepsi obscuur libel dari pihak lawan.")
        _add(rows, priority="P2", category="PROCEDURAL",
             issue="Antisipasi eksepsi kompetensi/formil dari tergugat",
             action="Siapkan tanggapan atas kemungkinan eksepsi kompetensi relatif/absolut dan cacat formil sebelum replik.",
             objective="Mempercepat proses bila tergugat mengajukan eksepsi.",
             why="Kesiapan tanggapan eksepsi mengurangi risiko keterlambatan dan argumentasi darurat.",
             deliverable="Draf tanggapan eksepsi (kontingensi)",
             success="Tanggapan siap dipakai bila eksepsi diajukan.",
             source_basis=role_basis,
             risk_if_skipped="Tanggapan eksepsi disusun terburu-buru dengan waktu terbatas.")

    elif ranah in ("PIDANA_UMUM", "PIDANA_KHUSUS") and posisi == "TERDAKWA":
        _add(rows, priority="P1", category="PROCEDURAL",
             issue="Kelayakan Praperadilan (Uji Formil Penangkapan/Penahanan/Penyidikan)",
             action="Uji keabsahan formil penangkapan, penahanan, dan penetapan tersangka terhadap syarat KUHAP (minimal dua alat bukti, prosedur penetapan, jangka waktu).",
             objective="Menentukan apakah ada dasar mengajukan praperadilan sebelum atau bersamaan dengan proses pokok.",
             why="Praperadilan adalah jalur formil KUHAP untuk menguji keabsahan tindakan penyidik sebelum masuk pokok perkara.",
             deliverable="Analisis kelayakan praperadilan + dasar formil",
             success="Keputusan terdokumentasi layak/tidaknya praperadilan beserta dasarnya.",
             evidence_targets=["Surat penetapan tersangka", "Berita acara penangkapan/penahanan", "SPDP"],
             source_basis=role_basis + ["KUHAP"],
             risk_if_skipped="Cacat formil pada tahap penyidikan tidak diuji sebelum perkara berlanjut ke pokok perkara.")
        _add(rows, priority="P1", category="DRAFT",
             issue="Nota Keberatan (Eksepsi Dakwaan)",
             action="Uji syarat formil (identitas terdakwa, uraian delik yang jelas dan lengkap) dan syarat materiil dakwaan sesuai Pasal 143 KUHAP.",
             objective="Menyusun eksepsi terhadap dakwaan yang tidak memenuhi syarat cermat, jelas, dan lengkap.",
             why="Dakwaan yang batal demi hukum atau tidak dapat diterima menghentikan pemeriksaan pokok perkara.",
             deliverable="Draf Nota Keberatan",
             success="Setiap cacat formil/materiil dakwaan yang ditemukan terpetakan ke dasar hukum yang tepat.",
             evidence_targets=["Surat dakwaan asli"],
             source_basis=role_basis + ["Pasal 143 KUHAP"],
             risk_if_skipped="Cacat dakwaan yang sebenarnya ada tidak dimanfaatkan pada kesempatan pertama.")
        _add(rows, priority="P2", category="EVIDENCE",
             issue="Persiapan Saksi Meringankan (A De Charge)",
             action="Identifikasi calon saksi/ahli a de charge yang relevan dengan unsur yang disengketakan, dan susun daftar pertanyaan yang tertaut ke unsur delik.",
             objective="Memastikan pembelaan tidak hanya bertumpu pada eksepsi formil, tetapi juga siap pada tahap pembuktian.",
             why="Kesiapan saksi a de charge sejak awal mencegah pembelaan tergesa-gesa saat tahap pembuktian.",
             deliverable="Daftar saksi/ahli a de charge + daftar pertanyaan per unsur",
             success="Setiap unsur yang disengketakan memiliki minimal satu calon saksi/ahli pendukung.",
             evidence_targets=["Identitas calon saksi/ahli", "Keterkaitan saksi dengan unsur delik"],
             source_basis=role_basis,
             risk_if_skipped="Pembelaan pada tahap pembuktian kekurangan saksi yang telah disiapkan.")

    elif ranah in ("PIDANA_UMUM", "PIDANA_KHUSUS") and posisi == "KORBAN_PELAPOR":
        _add(rows, priority="P1", category="LEGAL_VERIFY",
             issue="Kelengkapan laporan polisi dan alat bukti pendukung",
             action="Verifikasi laporan polisi, kronologi tertulis, dan alat bukti awal (dokumen, saksi, barang bukti) yang mendukung unsur delik yang dilaporkan.",
             objective="Memastikan laporan memiliki dasar yang cukup untuk ditindaklanjuti penyidik.",
             why="Laporan tanpa alat bukti awal yang memadai berisiko dihentikan pada tahap penyelidikan.",
             deliverable="Checklist kelengkapan laporan + alat bukti awal",
             success="Setiap unsur delik yang dilaporkan memiliki minimal satu alat bukti awal.",
             evidence_targets=["Laporan polisi/tanda terima laporan", "Dokumen/saksi pendukung"],
             source_basis=role_basis,
             risk_if_skipped="Laporan berisiko dihentikan karena minimnya alat bukti awal.")
        _add(rows, priority="P2", category="PROCEDURAL",
             issue="Persiapan permohonan restitusi/ganti rugi",
             action="Susun perhitungan kerugian materiil/immateriil korban dan dasar hukum permohonan restitusi.",
             objective="Menyiapkan dasar klaim restitusi sejak tahap awal proses pidana.",
             why="Permohonan restitusi memerlukan dasar perhitungan kerugian yang jelas dan terdokumentasi.",
             deliverable="Perhitungan kerugian + draf permohonan restitusi",
             success="Perhitungan kerugian terdokumentasi dan tertaut bukti.",
             evidence_targets=["Bukti kerugian materiil", "Dokumentasi dampak"],
             source_basis=role_basis,
             risk_if_skipped="Klaim restitusi tidak siap diajukan pada tahap yang tepat.")

    elif ranah == "TUN" and posisi in ("PEMOHON", "PENGGUGAT"):
        _add(rows, priority="P1", category="LEGAL_VERIFY",
             issue="Tenggang waktu 90 hari sejak KTUN diketahui/diterima",
             action="Kunci tanggal diketahui/diterimanya Keputusan Tata Usaha Negara (KTUN) dan hitung tenggang waktu gugatan 90 hari sesuai UU Peradilan TUN/UU Administrasi Pemerintahan.",
             objective="Memastikan gugatan tidak melewati tenggang waktu formil.",
             why="Gugatan yang diajukan melewati tenggang waktu akan dinyatakan tidak dapat diterima (niet ontvankelijk verklaard).",
             deliverable="Matriks tanggal KTUN → tenggang waktu → status",
             success="Tenggang waktu gugatan terverifikasi dan didukung bukti tanggal.",
             evidence_targets=["KTUN asli/salinan", "Bukti tanggal penerimaan/pemberitahuan"],
             source_basis=role_basis + ["UU Peradilan TUN", "UU Administrasi Pemerintahan"],
             risk_if_skipped="Gugatan berisiko ditolak karena lewat tenggang waktu.")
        _add(rows, priority="P1", category="PROCEDURAL",
             issue="Upaya administratif sebelum gugatan (jika disyaratkan)",
             action="Periksa apakah peraturan sektoral mensyaratkan upaya administratif (keberatan/banding administratif) sebelum gugatan diajukan ke PTUN.",
             objective="Memenuhi syarat formil upaya administratif sesuai UU Administrasi Pemerintahan.",
             why="Gugatan yang diajukan tanpa menempuh upaya administratif yang disyaratkan berisiko tidak dapat diterima.",
             deliverable="Analisis kewajiban upaya administratif + bukti penempuhannya (jika ada)",
             success="Status upaya administratif (disyaratkan/tidak, sudah/belum ditempuh) terdokumentasi.",
             source_basis=role_basis,
             risk_if_skipped="Gugatan PTUN berisiko cacat formil karena upaya administratif belum ditempuh.")
        _add(rows, priority="P2", category="DRAFT",
             issue="Susun gugatan PTUN dengan objek sengketa yang jelas",
             action="Rumuskan objek sengketa (KTUN yang digugat), dasar kepentingan hukum penggugat, dan petitum sesuai format UU Peradilan TUN.",
             objective="Menyusun gugatan yang objeknya jelas dan memenuhi syarat formil PTUN.",
             why="Objek sengketa yang tidak jelas adalah alasan umum gugatan PTUN dinyatakan tidak dapat diterima.",
             deliverable="Draf gugatan PTUN",
             success="Objek sengketa, kepentingan hukum, dan petitum tersusun jelas dan konsisten.",
             source_basis=role_basis,
             risk_if_skipped="Gugatan berisiko kabur (obscuur libel) pada objek sengketanya.")

    else:
        # Fail-closed fallback: role signal too weak or combination not yet
        # modeled. Surface this explicitly rather than silently producing no
        # procedural guidance, so a human reviewer knows the gap exists.
        _add(rows, priority="P2", category="PROCEDURAL",
             issue="Identifikasi forum dan posisi pihak secara manual",
             action=f"Sistem mendeteksi ranah_hukum={ranah}, posisi_pengguna={posisi} dengan keyakinan rendah. Verifikasi manual forum yang berwenang dan posisi klien sebelum menyusun langkah taktis prosedural.",
             objective="Mencegah rekomendasi taktis yang keliru akibat kesalahan deteksi ranah/posisi.",
             why="Playbook prosedural per (ranah_hukum, posisi_pengguna) belum mengenali kombinasi ini secara meyakinkan.",
             deliverable="Konfirmasi manual forum dan posisi pihak",
             success="Ranah hukum dan posisi pengguna terverifikasi oleh lawyer.",
             source_basis=role_basis,
             risk_if_skipped="Langkah taktis berikutnya dapat disusun berdasarkan asumsi forum/posisi yang salah.")

    return rows


# ---------------------------------------------------------------------------
# Anti-hallucination citation guardrail (/TRUTH bagian 3).
#
# This is deliberately cross-cutting: it runs for every posture/branch, not
# only the role-based playbook, because a fabricated or unverified pasal
# number is exactly as dangerous inside an objection draft or a merits memo
# as it is inside a generic procedural step. It never invents a "correct"
# citation and never removes a citation from the source text — it only flags
# which explicit Pasal references in the record have NOT yet cleared the
# existing positive_law_verification / instrument_identity_contract gate, so
# the planner cannot silently recommend drafting around an unverified article.
# ---------------------------------------------------------------------------

def _verified_provision_refs(result: Dict[str, Any]) -> set[str]:
    snap = result.get("case_regulatory_snapshot") or {}
    verified: set[str] = set()
    for row in snap.get("official_results") or []:
        if not isinstance(row, dict):
            continue
        v = row.get("positive_law_verification") or {}
        if v.get("final_status") != "VERIFIED_APPLICABLE":
            continue
        pv = v.get("provision_verification") or {}
        for ref in pv.get("verified") or []:
            norm = normalize_provision_ref(ref) or _clean(ref)
            if norm:
                verified.add(norm.lower())
    return verified


def _cited_provision_refs(result: Dict[str, Any]) -> List[str]:
    explicit = [normalize_provision_ref(r) or _clean(r) for r in (result.get("provision_refs") or [])]
    explicit = [r for r in explicit if r]
    if explicit:
        return _uniq(explicit, 24)
    # Fall back to scanning the source text directly when provision_refs was
    # not populated upstream (e.g. planner called in isolation/tests).
    return _uniq(extract_provision_refs(result.get("source_text") or result.get("text") or ""), 24)


def citation_guardrail(result: Dict[str, Any]) -> Dict[str, Any]:
    cited = _cited_provision_refs(result)
    verified = _verified_provision_refs(result)
    unverified = [c for c in cited if c.lower() not in verified]
    return {
        "cited_provisions": cited,
        "verified_provisions": sorted(verified),
        "unverified_provisions": unverified,
        "note": "Pasal pada 'unverified_provisions' tidak boleh dijadikan dasar dalil/rekomendasi taktis sampai lolos "
                "positive_law_verification (identitas instrumen, status berlaku, tempus, dan case nexus).",
    }


def _precision_actions(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    elements = _element_rows(result)
    gaps = _uniq((result.get("evidentiary_gaps") or []) + (result.get("evidence_needed") or []), 20)
    review = result.get("professional_review") or {}
    tempus = (result.get("reasoning_guard") or {}).get("tempus") or {}
    anomalies = (result.get("reasoning_guard") or {}).get("citation_anomalies") or []
    objection = _is_objection(result)
    corr_credit = _is_corruption_credit(result)

    # 1. Always resolve primary-source uncertainty before substantive drafting.
    if objection and (_has_finding(result, "TEMPUS_GAP") or str(tempus.get("status") or "").upper() not in {"TEMPUS_VERIFIED", ""}):
        _add(rows, priority="P1", category="LEGAL_VERIFY",
             issue="Tempus delicti dan ketentuan peralihan",
             action="Kunci tanggal/periode setiap perbuatan yang dituduhkan, lalu buat matriks tanggal → norma yang berlaku → ketentuan peralihan → konsekuensi penerapan.",
             objective="Menentukan rezim hukum materiil/acara yang benar sebelum menyusun serangan eksepsi.",
             why="Serangan terhadap dakwaan dapat kehilangan dasar bila tempus atau norma yang dirujuk ternyata berbeda dari asumsi dokumen.",
             deliverable="Tempus Matrix + daftar norma lama/baru + status verifikasi sumber resmi",
             success="Setiap perbuatan material mempunyai tanggal/periode dan setiap norma mempunyai dasar keberlakuan yang dapat ditelusuri.",
             owner="Lawyer + Legal Research",
             evidence_targets=["Surat dakwaan asli", "SK/keputusan terkait", "tanggal pencairan/approval", "ketentuan peralihan"],
             source_basis=["Reasoning Guard: tempus", "Professional Review: TEMPUS_GAP"],
             risk_if_skipped="Argumentasi salah tempus atau salah rezim hukum dapat menjadi titik serang balik.")

    if objection and (_has_finding(result, "LEGAL_CITATION_ANOMALY") or anomalies):
        _add(rows, priority="P1", category="PRIMARY_DOC",
             issue="Validasi identitas dan nomor seluruh peraturan dalam dakwaan asli",
             action="Bandingkan setiap nomor/tahun/pasal yang disebut dalam draft dengan surat dakwaan asli dan sumber resmi; tandai mana yang benar-benar tertulis oleh JPU dan mana yang hanya typo pada bahan kerja.",
             objective="Mencegah LexiCore membangun keberatan berdasarkan kesalahan transkripsi dari dokumen sekunder.",
             why="Kesalahan tahun/nomor pada bahan kerja tidak boleh diperlakukan sebagai cacat dakwaan tanpa pembuktian terhadap dokumen primer.",
             deliverable="Citation Audit Table: teks asli | hasil verifikasi | status | dampak argumentasi",
             success="100% rujukan regulasi yang menjadi dasar eksepsi memiliki pasangan dokumen primer dan sumber resmi.",
             evidence_targets=["Surat dakwaan asli", "salinan resmi peraturan", "ketentuan perubahan/peralihan"],
             source_basis=["Professional Review: LEGAL_CITATION_ANOMALY"],
             risk_if_skipped="Eksepsi dapat menyerang kesalahan yang sebenarnya hanya ada pada bahan internal.")

    if objection:
        _add(rows, priority="P1", category="PROCEDURAL",
             issue="Atribusi perbuatan individual terdakwa",
             action="Pecah rantai perbuatan menjadi: permohonan → appraisal/survei → analisa → rekomendasi → persetujuan → pencairan → monitoring → default → recovery; isi siapa melakukan apa, kapan, dengan dokumen apa, dan bagian mana yang secara eksplisit diatribusikan kepada terdakwa.",
             objective="Menguji apakah surat dakwaan benar-benar menghubungkan terdakwa dengan perbuatan konkret, bukan hanya jabatan atau tanda tangan.",
             why="Kejelasan atribusi adalah inti serangan formil ketika narasi menggabungkan fungsi organisasi dengan tanggung jawab personal.",
             deliverable="Individual Attribution Matrix",
             success="Tidak ada unsur/perbuatan material yang masih hanya ditopang oleh label jabatan tanpa tindakan spesifik.",
             evidence_targets=["surat dakwaan", "SK jabatan/kewenangan", "fiat", "notulen komite", "BAP", "dokumen approval"],
             source_basis=["Professional Review: individual act / attribution gap"],
             risk_if_skipped="Serangan error in persona/atribusi tetap abstrak dan mudah dipatahkan.")

        _add(rows, priority="P1", category="PROCEDURAL",
             issue="Uji rantai kausalitas dalam konstruksi dakwaan",
             action="Buat causal chain terdakwa → tindakan → pencairan → default/akibat → kerugian yang didalilkan; tandai setiap mata rantai yang berasal dari tindakan pihak lain atau belum dijelaskan dalam dakwaan.",
             objective="Menentukan apakah dakwaan menjelaskan hubungan sebab-akibat secara cukup untuk dipahami dan dibantah.",
             why="Pencairan kredit, kegagalan debitur, tindakan atas agunan, dan kerugian tidak boleh otomatis diperlakukan sebagai satu tindakan terdakwa.",
             deliverable="Causation Gap Map + daftar intervening acts",
             success="Setiap lompatan sebab-akibat memiliki fakta sumber; mata rantai yang kosong diberi status GAP, bukan diisi asumsi.",
             related_elements=[e.get("element", "") for e in elements if "kausal" in _clean(e.get("element")).lower() or "causal" in _clean(e.get("element")).lower()],
             evidence_targets=["dokumen pencairan", "monitoring", "status default", "audit kerugian", "tindakan debitur", "agunan/recovery"],
             source_basis=["Element Reasoning: Kausalitas", "Professional Review: attribution"],
             risk_if_skipped="Hubungan jabatan → kerugian dapat terlihat seolah-olah otomatis.")

        _add(rows, priority="P2", category="DRAFT",
             issue="Rebuild eksepsi dari cacat surat dakwaan",
             action="Untuk tiap keberatan gunakan format: kutipan/identifikasi bagian dakwaan → cacat konkret → akibat terhadap kemampuan terdakwa memahami/menjawab dakwaan → dasar hukum terverifikasi → petitum yang sesuai.",
             objective="Mengubah hasil analisis menjadi naskah eksepsi yang operasional dan tidak mencampur merits.",
             why="Draft akan lebih presisi bila setiap argumentasi mempunyai target tekstual dan akibat hukum yang jelas.",
             deliverable="Outline eksepsi final per isu + mapping ke petitum",
             success="Setiap petitum mempunyai dasar dari satu atau lebih cacat formil yang dapat ditunjuk secara konkret.",
             dependency="Tempus Matrix + Citation Audit + Individual Attribution Matrix",
             source_basis=["Professional Review strategic recommendation"],
             risk_if_skipped="Argumentasi tetap berupa uraian umum dan sulit dipetakan ke konsekuensi prosedural.")

        _add(rows, priority="P2", category="MERITS_RESERVE",
             issue="Pisahkan pembelaan merits: fidusia, agunan, recovery, actual loss",
             action="Bangun reserve merits memo yang memetakan outstanding → nilai agunan → status fidusia → eksekusi/recovery → actual loss → beneficiary → kontribusi pihak lain, tanpa menjadikannya satu-satunya dasar kompetensi Tipikor.",
             objective="Menjaga argumen substansi tetap tersedia untuk persidangan tanpa membebani eksepsi formil.",
             why="Fidusia/agunan dapat penting untuk loss dan causation, tetapi tidak otomatis menentukan forum atau menghapus unsur pidana.",
             deliverable="Merits Defense Memo + Recovery/Loss Matrix",
             success="Setiap angka kerugian dapat ditelusuri ke saldo, pembayaran, nilai agunan, realisasi recovery, dan metode audit.",
             evidence_targets=["perjanjian kredit", "BPKB/sertifikat fidusia", "appraisal", "outstanding", "pembayaran", "lelang/eksekusi", "LHP/PKKN"],
             source_basis=["Professional Review: FIDUCIARY_NON_DISPOSITIVE", "Element Reasoning: loss/causation"],
             risk_if_skipped="Pembelaan kehilangan alternatif penting ketika perkara masuk merits.")

    elif corr_credit:
        # Element-driven merits workflow for corruption/credit cases.
        if not _law_verified(result):
            _add(rows, priority="P1", category="LEGAL_VERIFY",
                 issue="Verifikasi norma materiil yang benar-benar berlaku",
                 action="Kunci instrumen, status berlaku, tempus, case nexus, dan pasal/unsur yang benar-benar ditemukan pada sumber resmi sebelum menilai unsur.",
                 objective="Mencegah element test memakai pasal yang salah atau tidak applicable.",
                 why="Legal element analysis hanya bermakna bila norma yang diuji memang berlaku pada perkara.",
                 deliverable="Applicable Law Sheet per unsur", success="Setiap unsur mempunyai minimal satu norma/pasal yang lolos verification gate.",
                 evidence_targets=["sumber resmi peraturan", "ketentuan peralihan", "teks pasal"],
                 source_basis=["Element Reasoning law gate"],
                 risk_if_skipped="Kesimpulan unsur dapat berdiri di atas norma yang salah.")

        targets = {
            "Kerugian": ("P1", "Actual loss chain", "Kumpulkan saldo/outstanding, pembayaran, kolektibilitas, pencadangan yang relevan, nilai agunan, realisasi recovery, dan LHP/PKKN; hitung ulang dengan tanggal cut-off yang sama.", "Menentukan apakah angka yang didalilkan merupakan kerugian nyata dan berapa yang benar-benar belum pulih.", ["LHP/PKKN", "ledger kredit", "bukti pembayaran", "appraisal", "dokumen recovery"]),
            "Kausal": ("P1", "Causal chain", "Petakan keputusan/omission terdakwa → pencairan → kondisi kredit → default → recovery → loss; masukkan tindakan staf, komite, debitur, dan pihak pemegang agunan sebagai possible intervening acts.", "Menguji apakah kerugian dapat diatribusikan secara personal.", ["fiat/approval", "notulen komite", "BAP", "monitoring", "dokumen debitur"]),
            "Mens": ("P1", "Mens rea / benefit tracing", "Telusuri fee, kickback, transfer, afiliasi, hubungan khusus, komunikasi, atau manfaat personal/korporasi yang secara faktual menghubungkan terdakwa dengan tujuan keuntungan.", "Menguji unsur mental/tujuan secara individual, bukan dengan inferensi dari jabatan semata.", ["rekening", "transfer", "komunikasi", "afiliasi", "BAP saksi/ahli"]),
            "Personal": ("P1", "Responsibility matrix", "Petakan fungsi marketing, analis, appraisal, komite, pemutus akhir, kepatuhan, SPI, dewan pengawas, debitur: tugas, pengetahuan, tindakan, dokumen, dan titik keputusan masing-masing.", "Memisahkan tanggung jawab organisasi dari tanggung jawab personal.", ["SK", "SOP", "job description", "notulen", "fiat", "BAP"]),
        }
        for e in elements:
            name=_clean(e.get("element")); low=name.lower()
            chosen=None
            for key, pack in targets.items():
                if (key=="Kerugian" and "kerug" in low) or (key=="Kausal" and ("kausal" in low or "causal" in low)) or (key=="Mens" and "mens" in low) or (key=="Personal" and ("personal" in low or "tanggung jawab" in low)):
                    chosen=pack; break
            if chosen and e.get("status") != "SUPPORTED":
                pr, issue, action, obj, ev = chosen
                _add(rows, priority=pr, category="EVIDENCE", issue=issue, action=action, objective=obj,
                     why=f"Status unsur saat ini: {_clean(e.get('status')) or 'BELUM ESTABLISHED'}; dukungan bukti kuat={e.get('strong_evidence_source_count',0)}.",
                     deliverable=f"Evidence pack untuk unsur: {name}", success="Bukti primer dan counter-evidence dapat diuji silang dan tidak hanya berasal dari pleading.",
                     related_elements=[name], evidence_targets=ev, source_basis=["Element Reasoning: "+name])

        if result.get("is_credit") or "financial_services" in set((result.get("domain_classification") or {}).get("domain_contract") or []):
            _add(rows, priority="P2", category="GOVERNANCE",
                 issue="Credit approval chain dan SOP pada tempus",
                 action="Rekonstruksi siapa yang melakukan survei, 5C, appraisal, rekomendasi, approval, pencairan, monitoring, dan recovery; cocokkan masing-masing dengan SOP/PKPB yang berlaku pada tanggal tindakan.",
                 objective="Menentukan apakah deviasi adalah tindakan personal, collective decision, atau fungsi unit lain.",
                 why="Pelanggaran SOP tidak otomatis menunjukkan bahwa seluruh unsur pidana dilakukan oleh pemutus akhir.",
                 deliverable="Credit Responsibility & SOP Matrix", success="Setiap langkah memiliki actor, authority, document, date, dan status compliance.",
                 evidence_targets=["PKPB/SOP", "SK/SE Direksi", "survei", "SLIK", "5C", "appraisal", "notulen", "fiat"])

    else:
        # Neither the objection path nor the corruption/credit merits path
        # claimed this case. Without this branch the planner previously fell
        # straight through to generic gap-closing only — no procedural/
        # tactical guidance at all. This is the generalization gap identified
        # in the LEXICORE audit: fill it with the role-based playbook.
        rows.extend(_role_based_procedural_actions(result))

    # Generic gap-closing actions for unresolved material gaps, but only when not already covered.
    covered = " ".join(r["issue"].lower() for r in rows)
    for gap in gaps:
        key_words=[w for w in re.findall(r"[a-z0-9]+", gap.lower()) if len(w)>5][:4]
        if key_words and sum(1 for w in key_words if w in covered) >= max(1, len(key_words)//2):
            continue
        _add(rows, priority="P2", category="EVIDENCE", issue=gap,
             action=f"Dapatkan dokumen/bukti primer yang secara langsung menjawab: {gap}. Setelah diperoleh, uji autentikasi, tempus, relevansi, dan nexus terhadap unsur terkait.",
             objective="Menutup gap pembuktian tanpa menaikkan inference menjadi fakta.",
             why="Gap ini masih membatasi kekuatan kesimpulan dan harus ditutup sebelum reliance.",
             deliverable="Evidence item + verification note", success="Ada bukti primer yang dapat ditelusuri dan hasil uji relevansinya terdokumentasi.",
             source_basis=["Evidentiary gaps"])

    # Hard traceability rule: every unresolved element must point to at least one
    # executable action. If a domain-specific action did not capture it, create
    # a deterministic evidence-closing action rather than leaving the element orphaned.
    referenced = set()
    for a in rows:
        for e in a.get("related_elements") or []:
            referenced.add(_clean(e).lower())
    for e in elements:
        name = _clean(e.get("element"))
        if not name or e.get("status") not in {"NOT_ESTABLISHED", "NEEDS_EVIDENCE", "DISPUTED"}:
            continue
        if name.lower() not in referenced:
            _add(rows, priority="P1" if e.get("status") == "NOT_ESTABLISHED" else "P2",
                 category="EVIDENCE", issue=f"Element closure: {name}",
                 action=f"Tutup gap unsur '{name}' dengan bukti primer, counter-evidence, dan uji elemen yang eksplisit; jangan menaikkan inference menjadi fakta.",
                 objective=f"Menentukan apakah unsur '{name}' dapat established, disputed, atau tetap not established.",
                 why=f"Unsur berstatus {_clean(e.get('status'))}; tanpa action owner dan evidence target, gap tidak dapat ditutup secara auditable.",
                 deliverable=f"Element Evidence Pack — {name}",
                 success="Bukti pendukung dan bantahan terpetakan, sumber dapat diautentikasi, dan hasil element test terdokumentasi.",
                 related_elements=[name], evidence_targets=["bukti primer terkait unsur", "counter-evidence", "dokumen sumber"],
                 source_basis=["Element Reasoning: unresolved element"],
                 risk_if_skipped="Unsur tetap tidak teruji dan legal conclusion tidak dapat dinaikkan secara defensible.")

    # Sort: priority, procedural/legal before generic evidence, then deterministic order.
    rank={"P1":0,"P2":1,"P3":2}
    cat_rank={"PRIMARY_DOC":0,"LEGAL_VERIFY":1,"PROCEDURAL":2,"EVIDENCE":3,"GOVERNANCE":4,"MERITS_RESERVE":5,"DRAFT":6}
    rows.sort(key=lambda r:(rank.get(r["priority"],9), cat_rank.get(r["category"],9), r["issue"].lower()))
    for i,r in enumerate(rows[:18],1):
        r["step"]=i
        r["time_window"]={"P1":"0–3 hari","P2":"3–7 hari","P3":"7–14 hari"}.get(r["priority"],"3–7 hari")
    return rows[:18]


def build_case_action_plan(result: Dict[str, Any]) -> Dict[str, Any]:
    actions=_precision_actions(result)
    guard=citation_guardrail(result)
    blockers=[]
    if not _law_verified(result): blockers.append("Norma applicable belum lolos verification gate.")
    for e in _element_rows(result):
        if e.get("status") in {"NOT_ESTABLISHED","NEEDS_EVIDENCE","DISPUTED"}:
            blockers.append(f"Unsur belum settled: {_clean(e.get('element'))} ({_clean(e.get('status'))}).")
    if _is_objection(result) and (_has_finding(result,"TEMPUS_GAP","LEGAL_CITATION_ANOMALY")):
        blockers.append("Dokumen primer dakwaan dan/atau tempus masih menjadi critical verification point.")
    if guard["unverified_provisions"]:
        blockers.append(
            "Pasal berikut disebut dalam dokumen tetapi belum lolos verifikasi sumber resmi (identitas/status/tempus/case-nexus): "
            + ", ".join(guard["unverified_provisions"][:8])
            + ". Jangan jadikan dasar dalil/rekomendasi sebelum diverifikasi."
        )
        actions.insert(0, {
            "priority": "P1", "category": "PRIMARY_DOC",
            "issue": "Verifikasi pasal yang belum lolos gate sumber resmi",
            "action": "Untuk tiap pasal pada daftar berikut, telusuri teks asli pada sumber resmi (JDIH/situs resmi instansi), konfirmasi identitas instrumen, status berlaku, dan tempus sebelum dipakai sebagai dasar dalil: "
                      + ", ".join(guard["unverified_provisions"][:8]) + ".",
            "objective": "Mencegah action plan atau draft menggunakan pasal yang salah, sudah dicabut, atau salah identitas instrumen.",
            "why_it_matters": "Pasal yang disebut dalam dokumen kerja tidak otomatis berarti pasal itu benar, berlaku, dan applicable pada perkara ini.",
            "deliverable": "Provision Verification Table: pasal | instrumen | status | tempus | hasil",
            "success_criteria": "Setiap pasal pada daftar berstatus VERIFIED_APPLICABLE atau dinyatakan eksplisit tidak dapat dipakai.",
            "dependency": "Tidak ada", "owner": "Legal Research",
            "related_elements": [], "evidence_targets": ["Sumber resmi peraturan (JDIH/situs instansi)"],
            "source_basis": ["positive_law_verification", "instrument_identity_contract"],
            "risk_if_skipped": "Draft/argumentasi dapat berdiri di atas pasal fiktif, sudah dicabut, atau salah instrumen.",
            "step": 0, "time_window": "0–3 hari",
        })
        for i, a in enumerate(actions, 1):
            a["step"] = i
    return {
        "engine":"LEXICORE_PRECISION_ACTION_PLANNER_V1",
        "method":"FINDING_ELEMENT_GAP_TO_EXECUTABLE_ACTION",
        "status":"ACTIONABLE" if actions else "NO_ACTION_GENERATED",
        "strategic_posture": "FORMAL_OBJECTION_FIRST__MERITS_RESERVED" if _is_objection(result) else "ELEMENT_AND_EVIDENCE_FIRST",
        "blockers":_uniq(blockers,10),
        "citation_guardrail":guard,
        "actions":actions,
        "next_best_action": actions[0] if actions else None,
        "completion_rule":"Action dianggap selesai hanya bila deliverable dan success criteria terpenuhi; bukan hanya karena rekomendasi sudah ditampilkan.",
        "disclaimer":"Action plan adalah rencana kerja berbasis record yang tersedia. Ia tidak menentukan hasil perkara dan tetap memerlukan verifikasi lawyer terhadap dokumen primer dan hukum positif."
    }
