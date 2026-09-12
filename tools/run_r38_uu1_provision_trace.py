"""R39/R38 diagnostic trace for UU 1/2015 Pasal 2.

DIAGNOSTIC ONLY. This script does not change LexiCore production verification
rules, status/tempus gates, scheduler, max-candidate contract, or persistent data.
It exercises the same legal_sources.resolve_official_fulltext() production path
used by Case Analysis and then independently inspects every official attachment.

Run from LexiCore project root:
    py tools/run_r38_uu1_provision_trace.py

Optional:
    py tools/run_r38_uu1_provision_trace.py --timeout 8
    py tools/run_r38_uu1_provision_trace.py --detail-url <official-detail-url>

Outputs in project root:
    trace_r38_uu1_pasal2.json
    trace_r38_uu1_pasal2_summary.txt
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from legal_sources import (
    FullTextLinkParser,
    _attachment_legal_role,
    _canonical_identity_keys_from_text,
    _contextual_candidate_order,
    _extract_pdf_text,
    _fulltext_link_score,
    _incorporated_instrument_keys_from_detail_text,
    _official_url,
    fetch_official_document,
    resolve_official_fulltext,
)

EXPECTED = "UU:1:2015"
PROVISION = "Pasal 2"
DEFAULT_DETAIL_URL = "https://peraturan.bpk.go.id/Details/37341/uu-no-1-tahun-2015"


def _html_text(body: bytes) -> str:
    raw = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else str(body or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def _provision_probe(text: str) -> dict:
    text = text or ""
    # Keep diagnostic probing slightly broader than the production verifier so
    # the trace can distinguish locator failure from attachment-selection failure.
    patterns = [
        r"\bPasal\s*2\b",
        r"\bPasal[\s\u00A0]+2\b",
        r"\bPasal\s+2\s*[\(\.:]",
    ]
    matches = []
    for pat in patterns:
        m = re.search(pat, text, re.I | re.M)
        matches.append({"pattern": pat, "found": bool(m), "position": (m.start() if m else None)})
    positions = [x["position"] for x in matches if x["position"] is not None]
    pos = min(positions) if positions else None
    context = ""
    if pos is not None:
        context = text[max(0, pos - 250): min(len(text), pos + 1000)]
    return {
        "contains_Pasal_2": pos is not None,
        "Pasal_2_position": pos,
        "patterns": matches,
        "Pasal_2_context": context,
    }


def _collect_candidates(detail_url: str, detail_body: bytes, requested=(PROVISION,)) -> list[dict]:
    raw = detail_body.decode("utf-8", "ignore")
    parser = FullTextLinkParser()
    try:
        parser.feed(raw)
    except Exception:
        pass
    out = []
    seen = set()
    for href, label in parser.links:
        url = urljoin(detail_url, href)
        if not url.startswith("http") or not _official_url(url) or url in seen:
            continue
        seen.add(url)
        score = _fulltext_link_score(url, label, requested)
        if score <= 0:
            continue
        out.append({
            "score": score,
            "url": url,
            "label": label or "",
            "legal_role_prefetch": _attachment_legal_role(url, label),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    for idx, row in enumerate(out):
        row["rank"] = idx
    return out


def _inspect_attachment(row: dict, timeout: int, incorporated_keys: list[str]) -> dict:
    url = row["url"]
    fetched = fetch_official_document(url, timeout=timeout)
    body = fetched.get("body") or b""
    ctype = str(fetched.get("content_type") or "")
    body_is_pdf = bytes(body).lstrip().startswith(b"%PDF-")
    is_pdf = "pdf" in ctype.lower() or url.lower().split("?", 1)[0].endswith(".pdf") or body_is_pdf
    pdf_complete = bool(body_is_pdf and b"%%EOF" in bytes(body[-65536:]))
    text = _extract_pdf_text(body) if is_pdf else (_html_text(body) if "html" in ctype.lower() else "")
    identities = _canonical_identity_keys_from_text(text) if text else []
    primary = identities[0] if identities else None
    role = _attachment_legal_role(url, row.get("label"))
    direct_match = bool(primary == EXPECTED)
    incorporated_match = bool(role == "ANNEX" and primary in (incorporated_keys or []))
    probe = _provision_probe(text)
    return {
        **{k: row.get(k) for k in ("rank", "score", "url", "label", "legal_role_prefetch")},
        "reachable": bool(fetched.get("reachable")),
        "official_host": bool(fetched.get("official_host")),
        "http_status": fetched.get("http_status"),
        "final_url": fetched.get("final_url"),
        "content_type": ctype,
        "content_length": len(body),
        "body_is_pdf": body_is_pdf,
        "pdf_complete_eof": pdf_complete,
        "extracted_text_length": len(text),
        "first_500_chars": text[:500],
        "identity_candidates": identities[:20],
        "primary_identity": primary,
        "legal_role_postfetch": role,
        "direct_identity_match": direct_match,
        "incorporated_identity_match": incorporated_match,
        **probe,
        "error": fetched.get("error"),
    }


def _classify(trace: dict) -> str:
    ctx = trace.get("parent_context") or {}
    r = trace.get("production_resolver") or {}
    attachments = trace.get("attachments") or []
    incorporated = set(ctx.get("incorporated_norm_ids") or [])

    if not incorporated:
        return "A_PARENT_INCORPORATION_RELATIONSHIP_NOT_EXTRACTED"

    relevant = [a for a in attachments if a.get("primary_identity") in incorporated]
    if relevant and not any(a.get("production_attempted") for a in relevant):
        return "B_INCOPORATED_ATTACHMENT_IDENTIFIED_BUT_NOT_ATTEMPTED_BY_PRODUCTION"

    if relevant and any(a.get("contains_Pasal_2") for a in relevant):
        if not any(a.get("incorporated_identity_match") for a in relevant):
            return "C_INCOPORATED_TEXT_HAS_PASAL2_BUT_LEGAL_ROLE_RELATIONSHIP_MATCH_FAILED"
        if not r.get("contains_Pasal_2"):
            return "D_GOOD_INCOPORATED_ATTACHMENT_EXISTS_CHECK_RESOLVER_SELECTION_OR_PROVISION_WIRING"

    if r.get("contains_Pasal_2") and r.get("relationship_verified"):
        return "E_PRODUCTION_RESOLVER_RECOVERS_INCOPORATED_PASAL2_CHECK_DOWNSTREAM_PROJECTION"

    aligned = [a for a in attachments if a.get("primary_identity") == EXPECTED]
    if aligned and any(a.get("contains_Pasal_2") for a in aligned):
        return "F_DIRECT_PARENT_TEXT_HAS_PASAL2_CHECK_DOWNSTREAM_PROJECTION"

    if attachments and not any(a.get("contains_Pasal_2") for a in attachments):
        return "G_NO_OFFICIAL_ATTACHMENT_CONTAINS_PASAL2_OR_EXTRACTION_INCOMPLETE"

    return "UNCLASSIFIED_REVIEW_TRACE"


def run(detail_url: str, timeout: int) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    detail = fetch_official_document(detail_url, timeout=timeout)
    body = detail.get("body") or b""
    detail_text = _html_text(body) if "html" in str(detail.get("content_type") or "").lower() else ""
    detail_ids = _canonical_identity_keys_from_text(detail_text) if detail_text else []
    parent_primary = detail_ids[0] if detail_ids else None
    incorporated_keys = _incorporated_instrument_keys_from_detail_text(detail_text, EXPECTED)
    candidates = _collect_candidates(detail.get("final_url") or detail_url, body)

    raw_tuples = [(c["score"], c["url"], c["label"]) for c in candidates]
    production_order = _contextual_candidate_order(
        raw_tuples,
        incorporated_keys=incorporated_keys,
        max_candidates=2,
    )
    production_urls = [x[1] for x in production_order]
    for c in candidates:
        c["production_selected_max_candidates_2"] = c["url"] in production_urls
        c["production_selection_order"] = (
            production_urls.index(c["url"]) if c["url"] in production_urls else None
        )

    production = resolve_official_fulltext(
        detail.get("final_url") or detail_url,
        body,
        detail.get("content_type") or "",
        requested_provisions=[PROVISION],
        timeout=timeout,
        max_candidates=2,
        expected_identity_key=EXPECTED,
    )

    attachment_traces = [_inspect_attachment(c, timeout, incorporated_keys) for c in candidates]
    attempted_urls = set(production.get("attempted_urls") or [])
    for a in attachment_traces:
        a["production_attempted"] = a.get("url") in attempted_urls
        a["production_selected_max_candidates_2"] = a.get("url") in production_urls
        a["production_selection_order"] = (
            production_urls.index(a.get("url")) if a.get("url") in production_urls else None
        )

    relationship_verified = bool(parent_primary == EXPECTED and incorporated_keys)
    trace = {
        "trace_version": "R39_DIAGNOSTIC_ONLY_UU1_PASAL2_V1",
        "started_at": started,
        "expected_identity_key": EXPECTED,
        "requested_provision": PROVISION,
        "detail_url": detail_url,
        "detail_fetch": {
            "reachable": bool(detail.get("reachable")),
            "official_host": bool(detail.get("official_host")),
            "http_status": detail.get("http_status"),
            "final_url": detail.get("final_url"),
            "content_type": detail.get("content_type"),
            "content_length": len(body),
            "detail_text_length": len(detail_text),
            "identity_candidates": detail_ids[:20],
            "primary_identity": parent_primary,
            "contains_Pasal_2": _provision_probe(detail_text)["contains_Pasal_2"],
            "error": detail.get("error"),
        },
        "parent_context": {
            "parent_identity": parent_primary,
            "expected_parent_identity": EXPECTED,
            "document_type": "ENACTMENT" if incorporated_keys else "UNKNOWN_OR_NON_ENACTMENT",
            "incorporated_norm_ids": incorporated_keys,
            "relationship_type": "ENACTED_AS_LAW" if incorporated_keys else None,
            "relationship_verified": relationship_verified,
            "relationship_source": "OFFICIAL_PARENT_DETAIL_TEXT" if relationship_verified else None,
        },
        "candidate_links_found": len(candidates),
        "candidate_links": candidates,
        "production_candidate_order_max2": production_urls,
        "production_resolver": {
            "resolved": bool(production.get("resolved")),
            "resolver_status": production.get("resolver_status"),
            "resolved_source_url": production.get("source_url"),
            "resolved_identity_key": production.get("resolved_identity_key"),
            "text_identity_key": production.get("text_identity_key"),
            "identity_candidates": production.get("identity_candidates") or [],
            "identity_aligned": production.get("identity_aligned"),
            "legal_role": production.get("legal_role"),
            "incorporated_identity_key": production.get("incorporated_identity_key"),
            "incorporation_parent_identity_key": production.get("incorporation_parent_identity_key"),
            "relationship_verified": production.get("relationship_verified"),
            "incorporated_identity_candidates": production.get("incorporated_identity_candidates") or [],
            "candidate_links_found": production.get("candidate_links_found"),
            "attempted_urls": production.get("attempted_urls") or [],
            "resolved_text_length": len(production.get("text") or ""),
            **_provision_probe(production.get("text") or ""),
        },
        "attachments": attachment_traces,
    }
    trace["diagnostic_classification"] = _classify(trace)
    return trace


def _summary(trace: dict) -> str:
    r = trace["production_resolver"]
    ctx = trace["parent_context"]
    lines = [
        "=" * 96,
        "R39 DIAGNOSTIC TRACE — UU 1/2015 PASAL 2 (R38 PRODUCTION PATH / NO STATE MUTATION)",
        "=" * 96,
        f"Expected identity : {trace['expected_identity_key']}",
        f"Provision         : {trace['requested_provision']}",
        f"Detail URL        : {trace['detail_url']}",
        f"Candidate links   : {trace['candidate_links_found']}",
        "",
        "PARENT CONTEXT (derived from official detail text)",
        f"  parent_identity          : {ctx.get('parent_identity')}",
        f"  document_type            : {ctx.get('document_type')}",
        f"  incorporated_norm_ids    : {ctx.get('incorporated_norm_ids')}",
        f"  relationship_verified    : {ctx.get('relationship_verified')}",
        f"  relationship_source      : {ctx.get('relationship_source')}",
        "",
        "PRODUCTION RESOLVER (max_candidates=2)",
        f"  status                    : {r.get('resolver_status')}",
        f"  resolved                  : {r.get('resolved')}",
        f"  source_url                : {r.get('resolved_source_url')}",
        f"  parent identity           : {r.get('resolved_identity_key')}",
        f"  actual text identity      : {r.get('text_identity_key')}",
        f"  legal_role                : {r.get('legal_role')}",
        f"  identity_aligned          : {r.get('identity_aligned')}",
        f"  incorporation_verified    : {r.get('relationship_verified')}",
        f"  incorporated_identity     : {r.get('incorporated_identity_key')}",
        f"  text_length               : {r.get('resolved_text_length')}",
        f"  contains Pasal 2          : {r.get('contains_Pasal_2')} pos={r.get('Pasal_2_position')}",
        f"  attempted_urls            : {len(r.get('attempted_urls') or [])}",
        "",
        "ATTACHMENTS",
    ]
    for a in trace.get("attachments") or []:
        flag = "TOP2" if a.get("production_selected_max_candidates_2") else "later"
        attempted = "ATTEMPTED" if a.get("production_attempted") else "not-attempted"
        lines += [
            f"  #{a.get('rank')} [{flag}/{attempted}] score={a.get('score')} order={a.get('production_selection_order')}",
            f"    label         : {a.get('label')}",
            f"    url           : {a.get('url')}",
            f"    role          : {a.get('legal_role_postfetch')}",
            f"    reachable     : {a.get('reachable')} status={a.get('http_status')}",
            f"    content_type  : {a.get('content_type')}",
            f"    bytes         : {a.get('content_length')}",
            f"    pdf_eof       : {a.get('pdf_complete_eof')}",
            f"    text_length   : {a.get('extracted_text_length')}",
            f"    primary_id    : {a.get('primary_identity')}",
            f"    identities    : {a.get('identity_candidates')}",
            f"    direct_match  : {a.get('direct_identity_match')}",
            f"    incorp_match  : {a.get('incorporated_identity_match')}",
            f"    contains P2   : {a.get('contains_Pasal_2')} pos={a.get('Pasal_2_position')}",
        ]
    lines += ["", f"CLASSIFICATION: {trace.get('diagnostic_classification')}", "=" * 96]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail-url", default=DEFAULT_DETAIL_URL)
    ap.add_argument("--timeout", type=int, default=8)
    args = ap.parse_args()
    trace = run(args.detail_url, max(1, min(20, args.timeout)))
    json_path = Path("trace_r38_uu1_pasal2.json")
    txt_path = Path("trace_r38_uu1_pasal2_summary.txt")
    json_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = _summary(trace)
    txt_path.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"JSON trace  : {json_path.resolve()}")
    print(f"Text summary: {txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
