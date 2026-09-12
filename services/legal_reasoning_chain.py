"""Auditable end-to-end legal reasoning chain for Case Analysis.

The chain makes the intended reasoning contract explicit:
Issue -> Applicable Law -> Legal Elements -> Alleged Act -> Evidence ->
Counter-Evidence -> Element Test -> Causation -> Risk ->
Procedural/Merits Classification -> Recommended Action.

This module is deliberately fail-closed. It never upgrades a pleading assertion
or semantic keyword hit into proof, and it never silently invents a legal rule.
Each stage carries an explicit status so a missing stage is visible rather than
being represented by plausible prose.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _norm(v: Any) -> str:
    return re.sub(r"\W+", " ", _clean(v).lower()).strip()


def _uniq(items: Iterable[str], limit: int = 20) -> List[str]:
    out, seen = [], set()
    for item in items or []:
        s = _clean(item)
        k = _norm(s)
        if not s or k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _terms(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]{4,}", _clean(text).lower()))
    stop = {
        "yang", "dengan", "untuk", "dalam", "dari", "pada", "atau", "serta",
        "terhadap", "adalah", "belum", "harus", "dapat", "secara", "karena",
        "apakah", "sebagai", "antara", "telah", "akan", "oleh", "bahwa",
        "maka", "yang", "sudah", "tidak", "hukum", "perkara", "unsur",
    }
    return {w for w in words if w not in stop}


def _issue_for_element(element: Dict[str, Any], issues: List[str]) -> str:
    explicit = _clean(element.get("owner_issue") or element.get("issue") or element.get("legal_issue"))
    if explicit:
        return explicit
    if not issues:
        return "Isu hukum belum dipetakan secara eksplisit."
    name=_clean(element.get('element')).lower()
    semantic_patterns=[]
    if 'kausal' in name:
        semantic_patterns=['kausal','hubungan kausal','intervening']
    elif 'kerugian keuangan' in name or 'kerugian negara' in name or 'kerugian daerah' in name:
        semantic_patterns=['kerugian keuangan','actual loss','kerugian negara','kerugian daerah']
    elif 'mens rea' in name or 'menguntungkan' in name or 'kesengajaan' in name:
        semantic_patterns=['kesengajaan','menguntungkan','mens rea','tujuan']
    elif 'personal responsibility' in name or 'tanggung jawab' in name or 'atribusi' in name:
        semantic_patterns=['tanggung jawab','diatribusikan','atribusi','pemutus akhir','pembagian tanggung jawab']
    elif 'melawan hukum' in name or 'penyalahgunaan kewenangan' in name:
        semantic_patterns=['penyimpangan prosedur','perbuatan koruptif','melawan hukum','penyalahgunaan kewenangan']
    for pattern in semantic_patterns:
        for issue in issues:
            if pattern in issue.lower():
                return issue
    et = _terms(element.get("element"))
    ranked = []
    for idx, issue in enumerate(issues):
        overlap = len(et & _terms(issue))
        # A tempus issue is never a fallback owner for a non-tempus element.
        if 'tempus' in issue.lower() and 'tempus' not in name:
            overlap=-1
        ranked.append((overlap, -idx, issue))
    ranked.sort(reverse=True)
    return ranked[0][2] if ranked and ranked[0][0] > 0 else "Isu pemilik unsur belum terpetakan secara eksplisit."


def _domain_family(value: str) -> str:
    low=_clean(value).lower()
    if any(k in low for k in ("pertanahan","land","properti","agraria","bpn")): return "land_property"
    if any(k in low for k in ("peradilan agama","religious","waris","agama")): return "religious_court"
    if any(k in low for k in ("acara perdata","civil procedure","hir","rbg","rv")): return "civil_procedure"
    if any(k in low for k in ("perikatan","kontrak","contract","wanprestasi")): return "civil_contract"
    if any(k in low for k in ("perbuatan melawan hukum","tort","pmh")): return "civil_tort"
    if any(k in low for k in ("pidana","criminal","tipikor","korupsi")): return "criminal"
    return ""


def _domain_compatible(owner_domain: str, law_domain: str, source: str) -> bool:
    owner=_domain_family(owner_domain) or _clean(owner_domain).lower()
    candidate=_domain_family(" ".join([law_domain,source]))
    if not owner or not candidate:
        return True
    if owner==candidate:
        return True
    compatible={
        "religious_court":{"civil_procedure","religious_court"},
        "land_property":{"land_property","civil_tort"},
        "civil_tort":{"civil_tort","civil_procedure"},
        "civil_contract":{"civil_contract","civil_procedure"},
        "civil_procedure":{"civil_procedure"},
    }
    return candidate in compatible.get(owner,{owner})


def _governing_law_compatible(element: Dict[str, Any], issue: str, candidate: Dict[str, Any]) -> bool:
    """Separate contextual regulation from the norm governing a legal element."""
    name=_clean(element.get('element')).lower()
    blob=_clean(' '.join([candidate.get('source',''), candidate.get('domain','')])).lower()
    criminal_element=any(k in name for k in ('melawan hukum','penyalahgunaan kewenangan','mens rea','menguntungkan','kerugian keuangan','kerugian negara','kerugian daerah','kausal','personal responsibility','tanggung jawab personal'))
    if criminal_element:
        # Banking/SOP rules can establish a duty or context, but do not govern
        # Tipikor offence elements unless the chain separately labels them contextual.
        if any(k in blob for k in ('perbankan','bpr','pojk','seojk')) and not any(k in blob for k in ('tipikor','korupsi','pemberantasan tindak pidana korupsi','kuhp')):
            return False
    if 'tempus' in issue.lower() and 'kausal' in name:
        return False
    return True


def _law_candidates(result: Dict[str, Any], element: Dict[str, Any], issue: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    terms = _terms(" ".join([issue, _clean(element.get("element")), _clean(element.get("applicable_law"))]))
    # SAL v1.0 Single Source of Truth: once enforced, Candidate Law is closed.
    # Never fall back to result.applicable_law/official raw results when the
    # governed pool is empty.
    governed = result.get('sal_governed_pools') or {}
    if result.get('sal_single_source_of_truth') and governed.get('orchestration_status') == 'ENFORCED':
        for item in governed.get('candidate_law_pool') or []:
            if not isinstance(item, dict):
                continue
            source=_clean(item.get('source') or item.get('title') or item.get('citation'))
            if not source:
                continue
            candidates.append({
                'source':source, 'status':_clean(item.get('status') or 'UNVERIFIED').upper(),
                'domain':_clean(item.get('domain')), 'provisions':item.get('provisions') or [],
                'identity_confirmed':item.get('identity_confirmed'), 'case_nexus_status':item.get('case_nexus_status'),
                'tempus_status':item.get('tempus_status'), 'tempus_applicable':item.get('tempus_applicable'),
                'score':len(terms & _terms(' '.join([source]+list(item.get('provisions') or [])))),
                'origin':item.get('origin') or 'sal_governed_law_pool',
            })
        owner_domain=_clean(element.get('owner_domain'))
        if owner_domain:
            candidates=[c for c in candidates if _domain_compatible(owner_domain,_clean(c.get('domain')),_clean(c.get('source')))]
        from services.semantic_admission import law_subject_matter_admissible
        dc=result.get('domain_contract') or result.get('domain_classification') or {}
        case_domains=(list(dc.get('domain_contract') or []) if isinstance(dc,dict) else [])
        if isinstance(dc,dict) and dc.get('primary_domain'): case_domains.append(dc.get('primary_domain'))
        if owner_domain: case_domains.append(owner_domain)
        case_text=_clean(result.get('source_text') or '')[:12000]
        candidates=[c for c in candidates if law_subject_matter_admissible(_clean(c.get('source')),case_domains=case_domains,issue_text=issue,case_text=case_text)[0]]
        candidates=[c for c in candidates if _governing_law_compatible(element,issue,c)]
        candidates.sort(key=lambda x:(1 if x.get('status')=='VERIFIED_APPLICABLE' else 0,int(x.get('score') or 0)),reverse=True)
        return [c for c in candidates if c.get('status')=='VERIFIED_APPLICABLE' or int(c.get('score') or 0)>0][:6]
    for item in result.get("applicable_law") or []:
        if isinstance(item, dict):
            source = _clean(item.get("source") or item.get("regulation") or item.get("qualified_citation") or item.get("title"))
            status = _clean(item.get("status") or "UNVERIFIED").upper()
            domain = _clean(item.get("domain"))
            text = " ".join([source, domain, status])
            score = len(terms & _terms(text))
            if source:
                candidates.append({"source": source, "status": status, "domain": domain, "score": score, "origin": "applicable_law"})
        elif _clean(item):
            candidates.append({"source": _clean(item), "status": "UNVERIFIED", "domain": "", "score": len(terms & _terms(item)), "origin": "applicable_law"})

    snap = result.get("case_regulatory_snapshot") or {}
    for row in snap.get("official_results") or []:
        if not isinstance(row, dict):
            continue
        v = row.get("positive_law_verification") or {}
        source = _clean(row.get("title") or row.get("citation") or row.get("source"))
        pv = v.get("provision_verification") or {}
        verified = _uniq(pv.get("verified") or [], 12)
        status = _clean(v.get("final_status") or "UNVERIFIED").upper()
        if source:
            candidates.append({
                "source": source,
                "status": status,
                "domain": _clean(row.get("domain") or ""),
                "provisions": verified,
                "identity_confirmed": v.get("identity_confirmed"),
                "case_nexus_status": v.get("case_nexus_status"),
                "tempus_status": v.get("tempus_status"),
                "tempus_applicable": v.get("tempus_applicable"),
                "score": len(terms & _terms(" ".join([source] + verified))),
                "origin": "official_results",
            })
    owner_domain=_clean(element.get("owner_domain"))
    if owner_domain:
        candidates=[c for c in candidates if _domain_compatible(owner_domain, _clean(c.get("domain")), _clean(c.get("source")))]
    from services.semantic_admission import law_subject_matter_admissible
    case_domains=[]
    dc=result.get('domain_contract') or result.get('domain_classification') or {}
    if isinstance(dc,dict):
        case_domains=list(dc.get('domain_contract') or []) or [dc.get('primary_domain')]
    if owner_domain:
        case_domains.append(owner_domain)
    case_text=_clean(result.get('source_text') or '')[:12000]
    candidates=[c for c in candidates if law_subject_matter_admissible(_clean(c.get('source')), case_domains=case_domains, issue_text=issue, case_text=case_text)[0]]
    candidates=[c for c in candidates if _governing_law_compatible(element, issue, c)]
    # Prefer semantically relevant candidates, then verified applicability.
    candidates.sort(key=lambda x: (
        1 if x.get("status") == "VERIFIED_APPLICABLE" else 0,
        int(x.get("score") or 0),
    ), reverse=True)
    # Never assign an unrelated global candidate as "Applicable Law" only because
    # it was the first retrieved instrument. Zero-nexus candidates remain outside
    # the element chain unless they are actually VERIFIED_APPLICABLE.
    candidates=[c for c in candidates if c.get("status")=="VERIFIED_APPLICABLE" or int(c.get("score") or 0)>0]
    return candidates[:6]


def _normalized_evidence(items: Any, role: str) -> List[Dict[str, Any]]:
    if not items:
        return []
    if not isinstance(items, list):
        items = [items]
    rows = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            statement = _clean(item.get("statement") or item.get("evidence") or item.get("text"))
            if not statement:
                continue
            rows.append({
                "source_index": item.get("source_index", idx),
                "statement": statement[:700],
                "classification": _clean(item.get("display_classification") or item.get("source_classification") or item.get("label") or "SOURCE"),
                "label": _clean(item.get("label") or "SOURCE"),
                "segment": item.get("segment"),
                "score": item.get("mapping_score") or item.get("score") or 0,
                "role": role,
            })
        else:
            statement = _clean(item)
            if statement:
                rows.append({"source_index": idx, "statement": statement[:700], "classification": "SOURCE", "label": "SOURCE", "segment": None, "score": 0, "role": role})
    return rows


def _source_route_allows(result: Dict[str, Any], evidence_item: Dict[str, Any], route: str) -> bool:
    """Bind canonical-chain consumers to the upstream SAL ledger decision."""
    from services.semantic_admission import route_allowed
    idx = evidence_item.get("source_index")
    ledger = result.get("source_ledger") or []
    if isinstance(idx, int) and 0 <= idx < len(ledger) and isinstance(ledger[idx], dict):
        return route_allowed(ledger[idx], route)
    # If the producer row itself preserved a SAL contract, enforce it directly.
    if isinstance(evidence_item.get("sal_contract"), dict):
        return route_allowed(evidence_item, route)
    # Once SSoT is enforced, a row without a valid route token is blocked.
    if result.get('sal_single_source_of_truth'):
        return False
    return True


def _evidence_items(result: Dict[str, Any], element: Dict[str, Any], issue: str) -> List[Dict[str, Any]]:
    # The element mapper is the authoritative producer for element-specific
    # mappings.  Preserve those mappings before attempting a secondary lexical
    # projection from the ledger; this prevents cross-layer contract drift.
    explicit = _normalized_evidence(element.get("supporting_evidence"), "SUPPORT")
    if explicit:
        from services.element_reasoning import evidence_proposition_admissibility
        admissible=[]
        for ev in explicit:
            if not _source_route_allows(result, ev, "Evidence Map"):
                continue
            ok,reason=evidence_proposition_admissibility(ev.get('statement',''), element_id=str(element.get('id') or ''), element_name=str(element.get('element') or ''), owner_domain=str(element.get('owner_domain') or ''))
            if ok:
                ev={**ev,'admissibility':'PASS','admissibility_reason':reason}
                admissible.append(ev)
        return admissible[:8]
    if result.get('sal_single_source_of_truth'):
        from services.sal_source_of_truth import pool_for_consumer
        ledger = pool_for_consumer(result, 'Evidence Map')
    else:
        ledger = result.get("material_source_ledger") or result.get("source_ledger") or []
    target_terms = _terms(" ".join([issue, _clean(element.get("element")), _clean(element.get("alleged_act")), _clean(element.get("prosecution_support"))]))
    rows = []
    for idx, item in enumerate(ledger):
        if not isinstance(item, dict):
            continue
        statement = _clean(item.get("statement") or item.get("evidence") or item.get("text"))
        if not statement:
            continue
        if not _source_route_allows(result, {**item, "source_index": item.get("source_index", idx)}, "Evidence Map"):
            continue
        score = len(target_terms & _terms(statement))
        if score <= 0:
            continue
        from services.element_reasoning import evidence_proposition_admissibility
        ok, admissibility_reason = evidence_proposition_admissibility(statement, element_id=str(element.get('id') or ''), element_name=str(element.get('element') or ''), owner_domain=str(element.get('owner_domain') or ''))
        if not ok:
            continue
        classification = _clean(item.get("display_classification") or item.get("source_classification") or item.get("label") or "SOURCE")
        rows.append({
            "source_index": item.get("source_index", idx),
            "statement": statement[:700],
            "classification": classification,
            "label": _clean(item.get("label") or "SOURCE"),
            "segment": item.get("segment"),
            "score": score,
            "role": "SUPPORT",
            "admissibility": "PASS",
            "admissibility_reason": admissibility_reason,
        })
    rows.sort(key=lambda x: (float(x.get("score") or 0), 1 if x.get("classification") == "ACTUAL_EVIDENTIARY_ITEM" else 0), reverse=True)
    return rows[:8]


def _counter_evidence(element: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    mapped = _normalized_evidence(element.get("counter_evidence") or element.get("defense_evidence"), "COUNTER")
    argument = _clean(element.get("defense_focus") or element.get("defense_counterpoint") or "")
    if not argument:
        arguments = element.get("counter_arguments") or []
        if isinstance(arguments, list) and arguments:
            first = arguments[0]
            argument = _clean(first.get("statement") if isinstance(first, dict) else first)
    if mapped:
        return {"status": "MAPPED", "items": mapped[:8], "counter_argument": argument}
    if argument:
        return {
            "status": "COUNTER_ARGUMENT_ONLY",
            "items": [],
            "counter_argument": argument,
            "note": "Poin ini adalah argumentasi/bantahan, bukan bukti kontra yang telah teridentifikasi.",
        }
    return {"status": "MISSING", "items": [], "counter_argument": "", "note": "Belum ada counter-evidence atau counter-argument yang terpetakan."}


def _classify_stage(element: Dict[str, Any], issue: str, result: Dict[str, Any]) -> str:
    explicit = _clean(element.get("procedural_merits") or element.get("classification")).upper()
    if explicit in {"PROCEDURAL", "MERITS", "MIXED"}:
        return explicit
    text = _clean(issue + " " + _clean(element.get("element"))).lower()
    procedural = any(k in text for k in (
        "kompetensi", "forum", "surat dakwaan", "dakwaan", "error in persona",
        "cacat formil", "posita", "petitum", "surat kuasa", "legal standing",
        "pihak lengkap", "kewenangan absolut", "kewenangan relatif", "eksepsi"
    ))
    merits = any(k in text for k in (
        "kerugian", "kausal", "mens rea", "melawan hukum", "penyalahgunaan",
        "wanprestasi", "sertipikat", "sertifikat", "alas hak", "kepemilikan",
        "perjanjian", "waris", "tanggung jawab", "atribusi"
    ))
    if procedural and merits:
        return "MIXED"
    if procedural:
        return "PROCEDURAL"
    return "MERITS"


def _causation_stage(element: Dict[str, Any], result: Dict[str, Any], classification: str = "MERITS") -> Dict[str, str]:
    if classification == "PROCEDURAL":
        return {"value": "Hubungan kausal merits tidak diterapkan sebagai unsur untuk isu prosedural ini; tahap dipertahankan sebagai GAP/non-merits.", "status": "GAP"}
    value = _clean(element.get("causation"))
    if value and not value.lower().startswith("hubungan kausal belum"):
        return {"value": value, "status": "MAPPED"}
    raw = result.get("causation_analysis")
    if isinstance(raw, dict):
        status = _clean(raw.get("status") or "NOT_ASSESSED").upper()
        reason = _clean(raw.get("reason") or raw.get("analysis") or "")
        gap_statuses = {"NOT_ASSESSED", "NEXUS_NOT_ESTABLISHED", "COUNTER_EVIDENCE_PRESENT"}
        return {"value": reason or status, "status": "GAP" if status in gap_statuses else "MAPPED"}
    value = _clean(raw)
    return {"value": value, "status": "GAP" if not value or "belum" in value.lower() else "MAPPED"}


def _action_links(result: Dict[str, Any], element: Dict[str, Any], issue: str) -> List[Dict[str, Any]]:
    actions = (result.get("precision_action_plan") or {}).get("actions") or result.get("action_plan") or []
    name = _norm(element.get("element"))
    issue_terms = _terms(issue)
    linked = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        related = [_norm(x) for x in action.get("related_elements") or []]
        blob = " ".join(str(v or "") for v in action.values())
        if name and name in related:
            linked.append(action)
            continue
        if len(issue_terms & _terms(blob)) >= 2:
            linked.append(action)
    return linked[:5]


def _status_from_stage(*, law: Dict[str, Any] | None, evidence: List[Dict[str, Any]], counter: Dict[str, Any], element: Dict[str, Any], causation_status: str) -> str:
    if not law or law.get("status") != "VERIFIED_APPLICABLE":
        return "BLOCKED_LAW_VERIFICATION"
    if not evidence:
        return "BLOCKED_EVIDENCE"
    if not _clean(element.get("element")):
        return "BLOCKED_ELEMENT_DEFINITION"
    if not _clean(element.get("alleged_act") or element.get("prosecution_support")):
        return "BLOCKED_ALLEGED_ACT"
    if counter.get("status") == "MISSING":
        return "COUNTER_EVIDENCE_GAP"
    if causation_status != "MAPPED":
        return "CAUSATION_GAP"
    return "CHAIN_READY_FOR_PROFESSIONAL_TEST"


def _stable_key(prefix: str, text: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", _clean(text).lower()).strip("-")[:72]
    return f"{prefix}:{token or 'unmapped'}"


def _granular_element_status(test_status: str, law_status: str, evidence_count: int, counter_status: str, act_status: str) -> str:
    ts = _clean(test_status).upper()
    if law_status != "VERIFIED_APPLICABLE":
        return "LAW_GATE_HOLD"
    if act_status != "MAPPED":
        return "ACT_ATTRIBUTION_UNVERIFIED"
    if evidence_count <= 0:
        return "NO_SUPPORTING_EVIDENCE"
    if counter_status == "MAPPED" and ts in {"SUPPORTED", "PARTIALLY_SUPPORTED", "DISPUTED"}:
        return "SUPPORTED_WITH_COUNTER" if ts != "DISPUTED" else "DISPUTED_WITH_COUNTER"
    if counter_status == "COUNTER_ARGUMENT_ONLY":
        return "ARGUMENT_CONTESTED_EVIDENCE_UNRESOLVED"
    if ts == "SUPPORTED":
        return "PRIMA_FACIE_SUPPORTED"
    if ts in {"NOT_ESTABLISHED", "NEEDS_EVIDENCE"}:
        return "UNVERIFIED"
    return ts or "UNVERIFIED"


def _aggregate_issue_risk(chains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for row in chains:
        issue = _clean((row.get("issue") or {}).get("value"))
        if issue not in grouped:
            grouped[issue] = []
            order.append(issue)
        grouped[issue].append(row)
    out=[]
    for issue in order:
        rows=grouped[issue]
        ready=sum(1 for r in rows if r.get("status")=="CHAIN_READY_FOR_PROFESSIONAL_TEST")
        holds=len(rows)-ready
        class_values={_clean((r.get("procedural_merits_classification") or {}).get("value")) for r in rows}
        out.append({
            "issue": issue,
            "issue_key": _stable_key("issue", issue),
            "element_count": len(rows),
            "ready_elements": ready,
            "held_elements": holds,
            "risk_level": "HIGH" if holds else "MEDIUM",
            "classification": "MIXED" if len(class_values-{""})>1 else (next(iter(class_values-{""}), "UNMAPPED")),
            "status": "HOLD" if holds else "READY_FOR_PROFESSIONAL_REVIEW",
        })
    return out


def build_reasoning_chain(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build one auditable chain row per legal element."""
    elements = [x for x in (result.get("element_reasoning") or {}).get("elements", []) if isinstance(x, dict)]
    if not elements:
        elements = [x for x in result.get("element_matrix") or [] if isinstance(x, dict)]
    issues = _uniq(result.get("legal_issues") or [], 18)
    chains = []
    stage_counts = {k: 0 for k in (
        "issue", "applicable_law", "legal_elements", "alleged_act", "evidence",
        "counter_evidence", "element_test", "causation", "risk", "classification", "recommended_action"
    )}

    for idx, element in enumerate(elements, 1):
        element_name = _clean(element.get("element") or f"Element {idx}")
        issue = _issue_for_element(element, issues)
        # SAL Positive-Allow SSoT: an owner/template issue is not a CURRENT issue
        # unless the Issue consumer has an admitted source-basis token.  No raw
        # or template fallback is allowed when the current-issue pool is empty.
        if result.get('sal_single_source_of_truth'):
            from services.sal_source_of_truth import pool_for_consumer
            if not pool_for_consumer(result, 'Issue'):
                issue = ''
        laws = _law_candidates(result, element, issue)
        law = laws[0] if laws else None

        # Strict Element Instantiation Control (SAL v1.0 / SSoT).
        # A blueprint/template element is not a live legal element unless it has
        # BOTH an admitted current Issue owner and an admitted Governing Law.
        # Do not emit a plausible placeholder element when either owner is absent.
        element_instantiated = bool(issue and law)
        if result.get('sal_single_source_of_truth') and not element_instantiated:
            element_name = ''

        evidence = _evidence_items(result, element, issue) if element_instantiated else []
        counter = _counter_evidence(element, result)
        alleged_act = _clean(element.get("alleged_act") or element.get("prosecution_support") or "") if element_instantiated else ""
        if result.get('sal_single_source_of_truth'):
            from services.sal_source_of_truth import pool_for_consumer
            _act_pool=pool_for_consumer(result,'Alleged Act')
            _allowed_texts={_clean(r.get('statement') or r.get('evidence') or r.get('text')) for r in _act_pool if isinstance(r,dict)}
            _allowed_texts.discard('')
            if alleged_act not in _allowed_texts:
                alleged_act=''
        if alleged_act.startswith("Perbuatan yang didalilkan belum"):
            alleged_act = ""
        classification = _classify_stage(element, issue, result)
        causation_stage = _causation_stage(element, result, classification)
        causation = causation_stage["value"]
        actions = _action_links(result, element, issue)
        test_status = _clean(element.get("status") or "NEEDS_EVIDENCE").upper()
        if not actions:
            actions = [{
                "priority": "P1" if test_status in {"NOT_ESTABLISHED", "NEEDS_EVIDENCE", "DISPUTED"} else "P2",
                "category": "VERIFY",
                "issue": issue,
                "action": f"Verifikasi ulang rantai unsur '{element_name}' dari norma yang berlaku, act yang didalilkan, bukti primer, counter-evidence, dan kausalitas; dokumentasikan hasil element test.",
                "objective": f"Menutup atau mempertahankan status unsur '{element_name}' secara auditable.",
                "why_it_matters": "Setiap unsur harus mempunyai tindak lanjut yang dapat dieksekusi; tidak ada unsur yang boleh orphan.",
                "deliverable": f"Element Verification Note — {element_name}",
                "success_criteria": "Status unsur, bukti pendukung, counter-evidence, dan alasan element test terdokumentasi serta dapat ditelusuri ke sumber.",
                "related_elements": [element_name],
                "evidence_targets": ["bukti primer terkait unsur", "counter-evidence", "sumber resmi norma"],
                "risk_if_skipped": "Unsur tetap tidak tertutup dan kesimpulan final tidak defensible.",
            }]
        law_status = law.get("status") if law else "MISSING"
        evidence_status = "MAPPED" if evidence else "MISSING"
        act_status = "MAPPED" if alleged_act else "MISSING"
        causation_status = causation_stage["status"]
        risk = _clean(element.get("risk")) or (
            "HIGH — chain cannot support a final conclusion while a required gate or element remains unresolved."
            if test_status != "SUPPORTED" or law_status != "VERIFIED_APPLICABLE" or not evidence
            else "RESIDUAL — admissibility, counter-evidence, causation and judicial assessment remain open."
        )
        overall = _status_from_stage(law=law, evidence=evidence, counter=counter, element=element, causation_status=causation_status)
        if result.get('sal_single_source_of_truth') and not issue:
            overall = 'BLOCKED_ROUTE_CONTRACT'

        chain_id = f"E{idx}"
        issue_key = _stable_key("issue", issue)
        element_key = _stable_key("element", element_name)
        law_key = _stable_key("law", (law or {}).get("source") or "unverified")
        granular_status = _granular_element_status(test_status, law_status, len(evidence), counter.get("status") or "MISSING", act_status)
        row = {
            "chain_id": chain_id,
            "status": overall,
            "binding_context": {
                "chain_id": chain_id,
                "issue_key": issue_key,
                "law_key": law_key,
                "element_key": element_key,
                "owner_domain": _clean(element.get("owner_domain")),
                "owner_issue_id": _clean(element.get("owner_issue_id")),
                "lineage": [issue_key, law_key, element_key],
                "status": "BOUND",
            },
            "issue": {"value": issue, "status": "MAPPED" if issue else "MISSING"},
            "applicable_law": {
                "selected": law,
                "candidates": laws,
                "status": "VERIFIED" if law_status == "VERIFIED_APPLICABLE" else ("CANDIDATE" if laws else "MISSING"),
                "rule": _clean(element.get("applicable_law")) or (law.get("source") if law else ""),
            },
            "legal_elements": {
                "element": element_name,
                "source_status": test_status if element_instantiated else "NOT_INSTANTIATED",
                "owner_domain": _clean(element.get("owner_domain")),
                "owner_issue_id": _clean(element.get("owner_issue_id")),
                "status": "MAPPED" if element_instantiated else "ELEMENT_NOT_INSTANTIATED",
                "reason": "" if element_instantiated else "BLOCKED_ROUTE_CONTRACT: Tidak ada Admitted Issue atau Governing Law aktif.",
            },
            "alleged_act": {"value": alleged_act, "status": act_status},
            "evidence": {"items": evidence, "status": evidence_status, "count": len(evidence)},
            "counter_evidence": counter,
            "element_test": {
                "status": test_status,
                "granular_status": granular_status,
                "gate": "PASS" if test_status == "SUPPORTED" and law_status == "VERIFIED_APPLICABLE" and evidence and act_status == "MAPPED" else "HOLD",
                "reason": _clean(element.get("release_explanation")) or "Uji unsur harus menggabungkan norma yang berlaku, act, bukti pendukung, dan bantahan.",
                "binding": {"issue_key": issue_key, "law_key": law_key, "element_key": element_key},
            },
            "causation": {"value": causation, "status": causation_status},
            "risk": {"level": "HIGH" if overall != "CHAIN_READY_FOR_PROFESSIONAL_TEST" else "MEDIUM", "value": risk, "status": "MAPPED"},
            "procedural_merits_classification": {"value": classification, "status": "MAPPED"},
            "recommended_action": {
                "status": "LINKED" if actions else "MISSING",
                "actions": actions,
                "derived_from": {
                    "element_gate": "PASS" if test_status == "SUPPORTED" else "HOLD",
                    "law_gate": law_status,
                    "act_gate": act_status,
                    "evidence_gate": evidence_status,
                    "counter_gate": counter.get("status") or "MISSING",
                    "causation_gate": causation_status,
                },
            },
        }
        chains.append(row)

        for key, present in {
            "issue": bool(issue),
            "applicable_law": bool(laws),
            "legal_elements": bool(element_instantiated and element_name),
            "alleged_act": bool(alleged_act),
            "evidence": bool(evidence),
            "counter_evidence": counter.get("status") != "MISSING",
            "element_test": bool(test_status),
            "causation": bool(causation),
            "risk": bool(risk),
            "classification": bool(classification),
            "recommended_action": bool(actions),
        }.items():
            stage_counts[key] += int(present)

    n = len(chains)
    coverage = {k: (round(v / n, 3) if n else 0.0) for k, v in stage_counts.items()}
    missing_stages = [k for k, v in coverage.items() if v < 1.0]
    return {
        "engine": "LEXICORE_FULL_LEGAL_REASONING_CHAIN_V2_3_1_FINAL_CORRECTIVE",
        "contract_version": "2.3.1",
        "method": "ISSUE_LAW_ELEMENT_ACT_EVIDENCE_COUNTER_TEST_CAUSATION_RISK_CLASSIFICATION_ACTION",
        "status": "COMPLETED" if chains else "NOT_ASSESSED",
        "chain_count": n,
        "chains": chains,
        "issue_risk": _aggregate_issue_risk(chains),
        "stage_coverage": coverage,
        "missing_stages": missing_stages,
        "structural_goal": "Issue → Applicable Law → Legal Elements → Alleged Act → Evidence → Counter-Evidence → Element Test → Causation → Risk → Procedural/Merits Classification → Recommended Action",
        "goal_status": "STRUCTURALLY_SATISFIED" if chains and not missing_stages else ("PARTIALLY_SATISFIED" if chains else "NOT_SATISFIED"),
        "substantive_gate": "FINAL_LEGAL_CONCLUSION_BLOCKED_WHEN_ANY_REQUIRED_STAGE_IS_UNVERIFIED_OR_MISSING",
        "disclaimer": "Chain ini mengukur keterlacakan analisis, bukan kebenaran materiil, guilt/liability, atau probabilitas hasil perkara. Verifikasi profesional dan dokumen primer tetap diperlukan.",
    }
