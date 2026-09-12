"""LexiCore SAL v1.0 cross-layer contract enforcer.

This module is deliberately small and deterministic.  SAL remains the semantic
producer; this enforcer makes the producer's restricted-routing contract binding
on every downstream consumer and blocks subject-matter-mismatched law results
before they can become Candidate Law.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Tuple

PROOF_NODES = {"Evidence Map", "Case Readiness"}
ALLEGED_ACT_NODE = "Alleged Act"
LEGAL_CONSTRUCTION_NODE = "Legal Construction"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


class LexiCoreContractEnforcer:
    """Binding enforcement for SAL routing and law subject-matter admission."""

    @staticmethod
    def enforce_routing(sal_payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(sal_payload or {})
        adm = dict(payload.get("admission_contract") or {})
        migration = dict(payload.get("downstream_migration") or {})
        state = str(adm.get("admissibility_state") or "REJECTED").upper()
        allowed = list(dict.fromkeys(adm.get("restricted_routes") or []))
        prohibited = list(dict.fromkeys(adm.get("prohibited_routes") or []))
        target = migration.get("primary_target_node") or "NONE"
        directive = migration.get("next_execution_directive") or "STOP"

        def forbid(*nodes: str) -> None:
            nonlocal prohibited
            for node in nodes:
                if node not in prohibited:
                    prohibited.append(node)
            allowed[:] = [node for node in allowed if node not in nodes]

        if state == "LEAD_ONLY":
            forbid("Evidence Map", "Case Readiness", "Alleged Act", "Legal Elements", "Causation")
            if target in prohibited or target == "NONE":
                target = "Document Audit"
                directive = "FORCE_ROUTE_TO_AUDIT_AS_LEAD_ONLY_DO_NOT_CONVERT_TO_PROOF"
                if target not in allowed:
                    allowed.append(target)

        elif state == "LIMITED":
            # LIMITED may legitimately route to Alleged Act for PARTY_ARGUMENT,
            # but never to proof pools. Preserve the producer's narrower route set.
            forbid("Evidence Map", "Case Readiness")
            if target in prohibited:
                target = allowed[0] if allowed else "Document Audit"
                directive = "ENFORCE_LIMITED_ROUTE_NO_PROOF_UPGRADE"

        elif state == "REJECTED":
            forbid("Evidence Map", "Case Readiness", "Alleged Act", "Legal Construction", "Legal Elements", "Causation", "Risk")
            # A rejected source may still carry a producer-authorized Action Plan
            # route (e.g. FUTURE_ACTION). Otherwise isolate it in Document Audit.
            if target not in allowed:
                if "Action Plan" in allowed:
                    target = "Action Plan"
                    directive = "ROUTE_REJECTED_SOURCE_AS_PROSPECTIVE_ACTION_ONLY"
                else:
                    target = "Document Audit"
                    directive = "HARD_ISOLATION_REJECTED_BY_UPSTREAM_SAL"
                    if target not in allowed:
                        allowed.append(target)

        payload["admission_contract"] = {
            **adm,
            "restricted_routes": allowed,
            "prohibited_routes": prohibited,
        }
        payload["downstream_migration"] = {
            **migration,
            "primary_target_node": target,
            "next_execution_directive": directive,
        }
        return payload

    @staticmethod
    def route_allowed(sal_payload: Dict[str, Any], route: str) -> bool:
        payload = LexiCoreContractEnforcer.enforce_routing(sal_payload)
        adm = payload.get("admission_contract") or {}
        allowed = set(adm.get("restricted_routes") or [])
        prohibited = set(adm.get("prohibited_routes") or [])
        return route in allowed and route not in prohibited

    @staticmethod
    def enforce_law_admission(
        law_payload: Dict[str, Any],
        *,
        case_domains: Iterable[str] = (),
        issue_text: str = "",
        case_text: str = "",
    ) -> Tuple[Dict[str, Any], bool, str]:
        """Reject clearly specialized cross-domain norms before Candidate Law.

        This is not substantive-law validation.  It only asks whether the source
        belongs to a subject-matter family that is absent from the active case/issue.
        General procedural/civil instruments are intentionally left for the normal
        law/tempus/status gates downstream.
        """
        payload = dict(law_payload or {})
        source = _clean(payload.get("text_payload") or payload.get("source") or payload.get("title") or payload.get("citation"))
        domain_hint = _clean((payload.get("semantic_envelope") or {}).get("domain_posture") or payload.get("domain"))
        blob = f"{source} {domain_hint}".lower()
        context = f"{issue_text} {case_text} {' '.join(str(x) for x in case_domains or [])}".lower()

        families = {
            "HKI": (
                ("hak cipta", "merek", "paten", "kekayaan intelektual", "lisensi teknologi", "perjanjian lisensi"),
                ("hki", "intellectual_property", "copyright", "trademark", "patent", "lisensi", "merek", "hak cipta"),
            ),
            "PERTAMBANGAN": (
                ("pertambangan", "izin usaha pertambangan", " iup", "mining", "minerba"),
                ("pertambangan", "mining", "minerba", "energi", "iup"),
            ),
            "PERTANAHAN": (
                ("pendaftaran tanah", "agraria", "hak atas tanah", "kantor pertanahan", "bpn", "sertipikat tanah"),
                ("land", "land_property", "pertanahan", "agraria", "tanah", "bpn"),
            ),
            "KETENAGAKERJAAN": (
                ("ketenagakerjaan", "hubungan industrial", "pemutusan hubungan kerja", " phk", "upah pekerja"),
                ("employment", "ketenagakerjaan", "industrial_relations", "buruh", "pekerja", "phk"),
            ),
            "KEPAILITAN": (
                ("kepailitan", "penundaan kewajiban pembayaran utang", " pkpu", "pailit"),
                ("bankruptcy", "kepailitan", "pkpu", "pailit"),
            ),
            "PIDANA": (
                ("tindak pidana", "kuhp", "tipikor", "pemberantasan tindak pidana korupsi", "pidana korupsi"),
                ("criminal", "corruption", "pidana", "tipikor", "korupsi", "tersangka", "terdakwa"),
            ),
        }

        for family, (source_markers, context_markers) in families.items():
            if any(marker in blob for marker in source_markers) and not any(marker in context for marker in context_markers):
                reason = f"SUBJECT_MATTER_MISMATCH_{family}"
                if "admission_contract" in payload:
                    adm = dict(payload.get("admission_contract") or {})
                    adm["admissibility_state"] = "REJECTED"
                    adm["prohibited_routes"] = list(dict.fromkeys((adm.get("prohibited_routes") or []) + ["Candidate Law", "Regulation/Tempus", "Norm Conflict"]))
                    adm["restricted_routes"] = [r for r in (adm.get("restricted_routes") or []) if r not in {"Candidate Law", "Regulation/Tempus", "Norm Conflict"}]
                    adm["rationale"] = reason
                    payload["admission_contract"] = adm
                    payload["downstream_migration"] = {
                        **(payload.get("downstream_migration") or {}),
                        "primary_target_node": "NONE",
                        "next_execution_directive": "DROP_CANDIDATE_SUBJECT_MATTER_MISMATCH",
                    }
                return payload, False, reason
        return payload, True, "SUBJECT_MATTER_ALIGNED_OR_GENERAL"
