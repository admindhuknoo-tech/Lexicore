"""Read-only Adversarial Viewpoint Splitter for LexiCore UI/export.

Presentation projection only. This module never reclassifies SAL statements and
never mutates routing/admissibility. It renders speaker/viewpoint metadata already
frozen upstream in the SAL contract and Route Token Ledger.
"""
from __future__ import annotations

from typing import Any, Dict, List

from services.contract_enforcer import LexiCoreContractEnforcer


def _clean(v: Any) -> str:
    return " ".join(str(v or "").split()).strip()


def _statement_id(row: Dict[str, Any]) -> str:
    sal = row.get("sal_contract") or {}
    return _clean(row.get("statement_id") or sal.get("statement_id"))


def _semantic_type(row: Dict[str, Any]) -> str:
    sal = row.get("sal_contract") or {}
    env = sal.get("semantic_envelope") or {}
    return _clean(row.get("sal_semantic_type") or env.get("semantic_type") or "UNCLASSIFIED").upper()


def _admissibility(row: Dict[str, Any]) -> str:
    sal = row.get("sal_contract") or {}
    adm = sal.get("admission_contract") or {}
    return _clean(row.get("sal_admissibility_state") or adm.get("admissibility_state") or "UNRESOLVED").upper()


def _target_node(row: Dict[str, Any]) -> str:
    sal = row.get("sal_contract") or {}
    migration = sal.get("downstream_migration") or {}
    return _clean(migration.get("primary_target_node") or "Document Audit")


def _viewpoint_meta(row: Dict[str, Any]) -> Dict[str, str]:
    sal = row.get("sal_contract") or {}
    return LexiCoreContractEnforcer.adversarial_context_from_payload(sal)


def _trace_label(speaker_role: str, semantic_type: str, epistemic_status: str = "") -> str:
    # Labels describe provenance/viewpoint, not truth.
    if speaker_role == "PROSECUTOR":
        return "[Dalil Penuntutan / PROSECUTOR]" if "ALLEGATION" in epistemic_status else "[Posisi JPU / Belum Terverifikasi]"
    if speaker_role == "DEFENSE_COUNSEL":
        return "[Dalil Pembelaan / DEFENSE_COUNSEL]" if "REBUTTAL" in epistemic_status or semantic_type in {"PARTY_ARGUMENT", "COUNTER_ARGUMENT"} else "[Posisi PH / Belum Terverifikasi]"
    if semantic_type == "PRIMARY_EVIDENCE":
        return "[Sumber Netral / Bukti Primer]"
    return "[Sumber Netral / Belum Terverifikasi]"


def build_adversarial_viewpoint_splitter(result: Dict[str, Any], limit_per_side: int = 20) -> Dict[str, Any]:
    """Build a read-only UI/export model from SAL-governed statements.

    Invariants:
    - no raw-source bypass: every displayed statement must have a Route Token.
    - no semantic upgrade: semantic_type/admissibility are copied as-is.
    - no ownership guessing in the renderer: UNKNOWN remains unresolved/neutral.
    """
    pools = result.get("sal_governed_pools") or {}
    route_ledger = pools.get("route_token_ledger") or {}
    source = result.get("source_ledger") or []

    groups: Dict[str, List[Dict[str, Any]]] = {"prosecution": [], "defense": [], "neutral": []}
    blocked = 0

    for row in source:
        if not isinstance(row, dict):
            continue
        sid = _statement_id(row)
        if not sid or sid not in route_ledger:
            blocked += 1
            continue
        meta = _viewpoint_meta(row)
        speaker = meta.get("speaker_role") or "UNKNOWN"
        sem = _semantic_type(row)
        epistemic = meta.get("epistemic_status") or _clean(row.get("sal_epistemic_status") or "UNSPECIFIED")
        item = {
            "statement_id": sid,
            "text": _clean(row.get("statement") or (row.get("sal_contract") or {}).get("text_payload")),
            "speaker_role": speaker,
            "position": meta.get("position") or "NEUTRAL",
            "stance": meta.get("stance") or "UNSPECIFIED",
            "semantic_type": sem,
            "epistemic_status": epistemic,
            "admissibility_state": _admissibility(row),
            "target_node": _target_node(row),
            "allowed_consumers": list((route_ledger.get(sid) or {}).get("allowed_consumers") or []),
            "trace_label": _trace_label(speaker, sem, epistemic),
            "source_index": row.get("source_index"),
        }
        if speaker == "PROSECUTOR":
            groups["prosecution"].append(item)
        elif speaker == "DEFENSE_COUNSEL":
            groups["defense"].append(item)
        else:
            groups["neutral"].append(item)

    for key in groups:
        groups[key] = groups[key][: max(1, int(limit_per_side))]

    model = {
        "contract_version": "ADV-VIEW-1.1",
        "projection_policy": "READ_ONLY_SAL_ROUTE_TOKEN_LEDGER_NO_RECLASSIFICATION",
        "status": "READY" if route_ledger else "UNRESOLVED_SOURCE_OWNERSHIP",
        "prosecution": groups["prosecution"],
        "defense": groups["defense"],
        "neutral": groups["neutral"],
        "blocked_without_route_token": blocked,
        "legend": {
            "PROSECUTOR": "Posisi JPU",
            "DEFENSE_COUNSEL": "Posisi PH",
            "UNKNOWN": "Sumber Netral / Belum Terverifikasi",
        },
    }
    result["adversarial_viewpoint_splitter"] = model
    return model
