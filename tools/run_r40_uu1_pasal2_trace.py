"""R40 diagnostic: post-fulltext provision-state propagation for UU 1/2015 Pasal 2.

DIAGNOSTIC ONLY. No production source is modified. The script runs two views:
A. a single exact official candidate through _verify_positive_law_results();
B. the real retrieve_for_case_dynamic() pipeline for a minimal case citation.

It monkey-patches only in-memory call wrappers so it can record canonical state
transitions without changing the resolver, identity gates, status/tempus rules,
scheduler, max_candidates, persistent DB, or report code.

Outputs in project root:
  trace_r40_uu1_pasal2.json
  trace_r40_uu1_pasal2_summary.txt
"""
from __future__ import annotations

import copy
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import services.regulatory_retrieval as rr
import services.positive_law_verification as plv

EXPECTED = "UU:1:2015"
PROVISION = "Pasal 2"
DETAIL_URL = "https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015"

# Minimal case text reproducing the exact qualified citation / electoral-ethics route.
CASE_TEXT = (
    "Dalam perkara etik DKPP, Teradu menyatakan melaksanakan tugas berdasarkan "
    "Pasal 3 Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum jo. "
    "Pasal 2 Undang-Undang Nomor 1 Tahun 2015 tentang Penetapan Peraturan Pemerintah "
    "Pengganti Undang-Undang Nomor 1 Tahun 2014 tentang Pemilihan Gubernur, Bupati, "
    "dan Walikota Menjadi Undang-Undang. Perkara diperiksa pada tahun 2021."
)


def _safe(obj: Any) -> Any:
    """JSON-safe deep copy with large text bodies summarized."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in {"body", "text", "fulltext", "source_text"} and isinstance(v, (str, bytes, bytearray)):
                out[k + "_length"] = len(v)
                if isinstance(v, str):
                    out[k + "_head"] = v[:500]
                continue
            out[k] = _safe(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_safe(x) for x in obj]
    if isinstance(obj, set):
        return sorted(_safe(x) for x in obj)
    if isinstance(obj, (bytes, bytearray)):
        return {"bytes_length": len(obj)}
    return obj


def _pv_state(v: dict | None) -> dict:
    v = v or {}
    return {
        "identity_confirmed": v.get("identity_confirmed"),
        "identity": _safe(v.get("identity")),
        "case_nexus_status": v.get("case_nexus_status"),
        "provision_text_location": _safe(v.get("provision_text_location")),
        "provision_text_verification": _safe(v.get("provision_text_verification")),
        "provision_verification": _safe(v.get("provision_verification")),
        "legal_status": v.get("legal_status"),
        "tempus_status": v.get("tempus_status"),
        "final_status": v.get("final_status"),
        "fulltext_reconciliation": _safe(v.get("fulltext_reconciliation")),
        "provision_source_url": v.get("provision_source_url"),
        "provision_source_status": v.get("provision_source_status"),
        "diagnostic": v.get("diagnostic"),
    }


def _verified_count(v: dict | None) -> int:
    pv = (v or {}).get("provision_verification") or {}
    return int(pv.get("verified_count") or 0)


def _candidate_row() -> dict:
    row = {
        "title": "UU No. 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota",
        "url": DETAIL_URL,
        "source_id": "bpk",
        "source_name": "BPK",
        "authoritative": True,
        "query": "Undang-Undang Nomor 1 Tahun 2015 tentang Pemilihan Gubernur, Bupati, dan Walikota",
        "query_origin": "EXACT_CASE_REGULATION",
        "case_nexus_domains": ["electoral_ethics"],
        "case_nexus_status": "CASE_NEXUS_UNCERTAIN",
        "relevance_score": 1.0,
        "requested_provisions": [PROVISION],
        "provision_binding_provenance": {
            "case_bound": True,
            "exact_case_text": [PROVISION],
            "qualified_case_citation": ["Pasal 2 UU 1 Tahun 2015"],
            "instrument_key": EXPECTED,
        },
    }
    row["document_classification"] = rr.classify_legal_document_candidate(row)
    return row


def _instrument_key(row: dict) -> str | None:
    try:
        return rr._expected_identity_key_for_fulltext(row)
    except Exception:
        return None


def _rows_for_expected(rows: list[dict]) -> list[dict]:
    matched = []
    for idx, row in enumerate(rows or []):
        key = _instrument_key(row)
        v = row.get("positive_law_verification") or {}
        ident = (v.get("identity") or {}).get("key") if isinstance(v.get("identity"), dict) else None
        if key == EXPECTED or ident == EXPECTED or "1 Tahun 2015" in str(row.get("title") or ""):
            matched.append({
                "index": idx,
                "expected_identity_key": key,
                "title": row.get("title"),
                "url": row.get("url"),
                "query_origin": row.get("query_origin"),
                "requested_provisions": _safe(row.get("requested_provisions")),
                "provision_binding_provenance": _safe(row.get("provision_binding_provenance")),
                "fulltext_resolution": _safe(row.get("fulltext_resolution")),
                "positive_law_verification": _pv_state(v),
            })
    return matched


def run() -> dict:
    trace: dict[str, Any] = {
        "trace_version": "R40_POST_FULLTEXT_PROVISION_STATE_V1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "expected_identity": EXPECTED,
        "provision": PROVISION,
        "detail_url": DETAIL_URL,
        "checkpoints": [],
        "errors": [],
    }

    # Runtime wrappers around the same production functions used by
    # _verify_positive_law_results. They only record inputs/outputs.
    original_resolve = rr.resolve_official_fulltext
    original_verify = rr.verify_document_candidate
    original_status = rr.apply_post_verification_status_semantics

    def wrapped_resolve(*args, **kwargs):
        out = original_resolve(*args, **kwargs)
        if kwargs.get("expected_identity_key") == EXPECTED:
            text = out.get("text") or ""
            trace["checkpoints"].append({
                "checkpoint": 3,
                "name": "FULLTEXT_RESOLUTION",
                "state": {
                    "resolved": out.get("resolved"),
                    "resolver_status": out.get("resolver_status"),
                    "source_url": out.get("source_url"),
                    "resolved_identity_key": out.get("resolved_identity_key"),
                    "text_identity_key": out.get("text_identity_key"),
                    "identity_aligned": out.get("identity_aligned"),
                    "legal_role": out.get("legal_role"),
                    "relationship_verified": out.get("relationship_verified"),
                    "incorporated_identity_key": out.get("incorporated_identity_key"),
                    "text_length": len(text),
                    "contains_literal_Pasal_2": "Pasal 2" in text,
                    "attempted_urls": _safe(out.get("attempted_urls")),
                },
            })
        return out

    def wrapped_verify(candidate, *, source_text, snapshot):
        out = original_verify(candidate, source_text=source_text, snapshot=snapshot)
        if _instrument_key(candidate) == EXPECTED:
            trace["checkpoints"].append({
                "checkpoint": 4,
                "name": "VERIFY_DOCUMENT_CANDIDATE",
                "input": {
                    "url": candidate.get("url"),
                    "query_origin": candidate.get("query_origin"),
                    "requested_provisions": _safe(candidate.get("requested_provisions")),
                    "provision_binding_provenance": _safe(candidate.get("provision_binding_provenance")),
                    "source_text_length": len(source_text or ""),
                    "snapshot": _safe(snapshot),
                },
                "state": _pv_state(out),
            })
        return out

    def wrapped_status(result, candidate):
        before = copy.deepcopy(result)
        out = original_status(result, candidate)
        if _instrument_key(candidate) == EXPECTED:
            trace["checkpoints"].append({
                "checkpoint": 5,
                "name": "POST_STATUS_SEMANTICS",
                "before": _pv_state(before),
                "state": _pv_state(out),
            })
        return out

    rr.resolve_official_fulltext = wrapped_resolve
    rr.verify_document_candidate = wrapped_verify
    rr.apply_post_verification_status_semantics = wrapped_status

    try:
        # CP1: exact row that enters canonical positive-law verification.
        row = _candidate_row()
        trace["checkpoints"].append({
            "checkpoint": 1,
            "name": "INPUT_ROW",
            "state": {
                "expected_identity_key": _instrument_key(row),
                "query_origin": row.get("query_origin"),
                "requested_provisions": _safe(row.get("requested_provisions")),
                "provision_binding_provenance": _safe(row.get("provision_binding_provenance")),
                "case_nexus_status": row.get("case_nexus_status"),
                "url": row.get("url"),
            },
        })

        # CP2 is the parent-detail verification state, captured by the final row
        # only if fulltext resolution does not run. We mark the expected pre-state
        # explicitly without inventing a separate verifier.
        trace["checkpoints"].append({
            "checkpoint": 2,
            "name": "PRE_FULLTEXT_EXPECTED_GATE",
            "state": {
                "expected_identity_key": EXPECTED,
                "requested_provisions": [PROVISION],
                "note": "Observed next from production _verify_positive_law_results; no simulated verification result is injected.",
            },
        })

        phase_a = rr._verify_positive_law_results(
            [copy.deepcopy(row)],
            snapshot={"procedural_date_candidate": "2021-04-03"},
            max_documents=10,
            time_budget_seconds=30.0,
        )
        phase_a_row = phase_a[0] if phase_a else {}
        phase_a_v = phase_a_row.get("positive_law_verification") or {}

        # CP6/7: state after nested postfetch contract and enriched_by_index.
        # The nested contract is not separately importable, so the production
        # returned row is the authoritative observation point after it.
        trace["checkpoints"].append({
            "checkpoint": 6,
            "name": "POSTFETCH_CONTRACT_OBSERVED_IN_RETURNED_ROW",
            "state": _pv_state(phase_a_v),
        })
        trace["checkpoints"].append({
            "checkpoint": 7,
            "name": "ENRICHED_BY_INDEX_RETURN",
            "state": {
                "title": phase_a_row.get("title"),
                "canonical_instrument_key": _instrument_key(phase_a_row),
                "requested_provisions": _safe(phase_a_row.get("requested_provisions")),
                "fulltext_resolution": _safe(phase_a_row.get("fulltext_resolution")),
                "positive_law_verification": _pv_state(phase_a_v),
            },
        })
        trace["phase_a_single_exact_candidate"] = _safe(phase_a_row)

        # Phase B: actual discovery/binding/dedupe/verification path used by case analysis.
        dynamic = rr.retrieve_for_case_dynamic(
            text=CASE_TEXT,
            title="R40 UU 1/2015 Pasal 2 diagnostic",
            provision_refs=[PROVISION],
            qualified_queries=["Pasal 2 Undang-Undang Nomor 1 Tahun 2015"],
            online=True,
            retrieval_mode="online",
            domain_classification={
                "domains": [
                    {"id": "electoral_ethics", "label": "Pemilu / Pilkada / Etik Penyelenggara", "confidence": 99, "role": "PRIMARY", "score": 99}
                ]
            },
        )
        all_expected = _rows_for_expected(dynamic.get("official_results") or [])
        trace["checkpoints"].append({
            "checkpoint": 8,
            "name": "REAL_CASE_PIPELINE_ROWS_FOR_UU_1_2015",
            "state": {
                "row_count": len(all_expected),
                "rows": all_expected,
                "retrieval_funnel": _safe(dynamic.get("retrieval_funnel")),
                "verification_diagnostics": _safe(dynamic.get("verification_diagnostics")),
            },
        })
        trace["phase_b_dynamic_retrieval"] = {
            "official_results_count": dynamic.get("official_results_count"),
            "rows_for_expected": all_expected,
            "retrieval_funnel": _safe(dynamic.get("retrieval_funnel")),
        }

        # Deterministic diagnosis based on the first point where canonical 1/1 is lost.
        cp4 = [x for x in trace["checkpoints"] if x.get("checkpoint") == 4]
        cp5 = [x for x in trace["checkpoints"] if x.get("checkpoint") == 5]
        cp4_count = max((_verified_count({"provision_verification": (x.get("state") or {}).get("provision_verification")}) for x in cp4), default=0)
        cp5_count = max((_verified_count({"provision_verification": (x.get("state") or {}).get("provision_verification")}) for x in cp5), default=0)
        cp6_count = _verified_count(phase_a_v)
        dynamic_counts = [
            int((((r.get("positive_law_verification") or {}).get("provision_verification") or {}).get("verified_count") or 0))
            for r in all_expected
        ]

        if cp4_count == 0:
            classification = "A_VERIFY_DOCUMENT_CANDIDATE_OR_BINDING_FAILS"
        elif cp5_count == 0:
            classification = "B_POST_STATUS_SEMANTICS_OVERWRITES_VERIFIED_PROVISION"
        elif cp6_count == 0:
            classification = "C_POSTFETCH_CONTRACT_OR_FINAL_ROW_OVERWRITES_VERIFIED_PROVISION"
        elif not all_expected:
            classification = "D_DYNAMIC_RETRIEVAL_LOSES_EXPECTED_INSTRUMENT_ROW"
        elif max(dynamic_counts or [0]) == 0:
            classification = "E_SINGLE_CANDIDATE_IS_1_1_BUT_REAL_PIPELINE_ROWS_ARE_0_1_CHECK_BINDING_DEDUPE_OR_ROW_SELECTION"
        elif len(set(dynamic_counts)) > 1:
            classification = "F_DUPLICATE_UU1_ROWS_HAVE_DIVERGENT_PROVISION_STATE"
        else:
            classification = "G_CANONICAL_PIPELINE_IS_1_1_CHECK_CASE_SNAPSHOT_OR_REPORT_PROJECTION"

        trace["diagnosis"] = {
            "classification": classification,
            "phase_a_cp4_verified_count": cp4_count,
            "phase_a_cp5_verified_count": cp5_count,
            "phase_a_final_verified_count": cp6_count,
            "phase_b_expected_row_verified_counts": dynamic_counts,
            "phase_b_expected_row_count": len(all_expected),
        }

    except Exception as exc:
        trace["errors"].append({
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        })
    finally:
        rr.resolve_official_fulltext = original_resolve
        rr.verify_document_candidate = original_verify
        rr.apply_post_verification_status_semantics = original_status

    trace["finished_at"] = datetime.now(timezone.utc).isoformat()
    return trace


def _write_summary(trace: dict) -> str:
    lines = []
    lines.append("=" * 96)
    lines.append("R40 POST-FULLTEXT PROVISION STATE TRACE — UU 1/2015 PASAL 2")
    lines.append("=" * 96)
    lines.append(f"Expected identity : {trace.get('expected_identity')}")
    lines.append(f"Provision         : {trace.get('provision')}")
    lines.append("")
    for cp in trace.get("checkpoints") or []:
        no = cp.get("checkpoint")
        name = cp.get("name")
        lines.append(f"CHECKPOINT {no} — {name}")
        state = cp.get("state") or {}
        if no in {4,5,6}:
            pv = state.get("provision_verification") or {}
            lines.append(f"  identity_confirmed : {state.get('identity_confirmed')}")
            lines.append(f"  case_nexus_status  : {state.get('case_nexus_status')}")
            lines.append(f"  provision status   : {pv.get('status')}")
            lines.append(f"  verified/requested : {pv.get('verified_count',0)}/{pv.get('requested_count',0)}")
            lines.append(f"  verified           : {pv.get('verified')}")
            lines.append(f"  unverified         : {pv.get('unverified')}")
        elif no == 3:
            for k in ("resolved","resolver_status","source_url","resolved_identity_key","text_identity_key","identity_aligned","legal_role","text_length","contains_literal_Pasal_2"):
                lines.append(f"  {k:23}: {state.get(k)}")
        elif no == 8:
            lines.append(f"  UU 1/2015 rows      : {state.get('row_count')}")
            for row in state.get("rows") or []:
                pv = ((row.get("positive_law_verification") or {}).get("provision_verification") or {})
                lines.append(f"    row #{row.get('index')} | {pv.get('verified_count',0)}/{pv.get('requested_count',0)} | {row.get('url')}")
        else:
            lines.append("  " + json.dumps(state, ensure_ascii=False, default=str)[:1800])
        lines.append("")
    diag = trace.get("diagnosis") or {}
    lines.append("DIAGNOSIS")
    lines.append(f"  classification               : {diag.get('classification')}")
    lines.append(f"  CP4 verified_count           : {diag.get('phase_a_cp4_verified_count')}")
    lines.append(f"  CP5 verified_count           : {diag.get('phase_a_cp5_verified_count')}")
    lines.append(f"  Phase A final verified_count : {diag.get('phase_a_final_verified_count')}")
    lines.append(f"  Phase B row counts           : {diag.get('phase_b_expected_row_verified_counts')}")
    if trace.get("errors"):
        lines.append("")
        lines.append("ERRORS")
        for err in trace["errors"]:
            lines.append("  " + str(err.get("error")))
            lines.append(str(err.get("traceback") or ""))
    lines.append("=" * 96)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print("=" * 96)
    print("R40 POST-FULLTEXT PROVISION STATE TRACE — UU 1/2015 PASAL 2")
    print("DIAGNOSTIC ONLY / PRODUCTION FUNCTIONS OBSERVED IN-MEMORY / NO STATE MUTATION")
    print("=" * 96)
    result = run()
    summary = _write_summary(result)
    print(summary)
    json_path = PROJECT_ROOT / "trace_r40_uu1_pasal2.json"
    txt_path = PROJECT_ROOT / "trace_r40_uu1_pasal2_summary.txt"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    txt_path.write_text(summary, encoding="utf-8")
    print(f"JSON trace  : {json_path}")
    print(f"Text summary: {txt_path}")
    sys.exit(1 if result.get("errors") else 0)
