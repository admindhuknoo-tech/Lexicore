"""R36 diagnostic trace for UU 7/2017 Pasal 3.

DIAGNOSTIC ONLY. This script does not change LexiCore verification state,
configuration, caches, scheduler, budget, identity rules, or provision rules.

Run from LexiCore project root:
    py tools/run_r36_uu7_provision_trace.py

Optional:
    py tools/run_r36_uu7_provision_trace.py --timeout 8
    py tools/run_r36_uu7_provision_trace.py --detail-url <official-detail-url>

Outputs in project root:
    trace_r36_uu7_pasal3.json
    trace_r36_uu7_pasal3_summary.txt
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import sys

# Ensure project root is importable when this script is executed as tools\script.py on Windows.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from legal_sources import (
    FullTextLinkParser,
    _canonical_identity_keys_from_text,
    _extract_pdf_text,
    _fulltext_link_score,
    _official_url,
    fetch_official_document,
    resolve_official_fulltext,
)

EXPECTED = "UU:7:2017"
PROVISION = "Pasal 3"
DEFAULT_DETAIL_URL = "https://peraturan.bpk.go.id/Details/37644/uu-no-7-tahun-2017"


def _html_text(body: bytes) -> str:
    raw = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else str(body or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def _pasal3_probe(text: str) -> dict:
    text = text or ""
    patterns = [
        r"\bPasal\s*3\b",
        r"\bPasal[\s\u00A0]+3\b",
        r"\bPasal\s+3\s*[\(\.:]",
    ]
    matches = []
    for pat in patterns:
        m = re.search(pat, text, re.I | re.M)
        matches.append({"pattern": pat, "found": bool(m), "position": (m.start() if m else None)})
    positions = [x["position"] for x in matches if x["position"] is not None]
    pos = min(positions) if positions else None
    context = ""
    if pos is not None:
        context = text[max(0, pos - 250): min(len(text), pos + 800)]
    return {
        "contains_Pasal_3": pos is not None,
        "Pasal_3_position": pos,
        "patterns": matches,
        "Pasal_3_context": context,
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
        out.append({"score": score, "url": url, "label": label or ""})
    out.sort(key=lambda x: x["score"], reverse=True)
    for idx, row in enumerate(out):
        row["rank"] = idx
        row["production_selected_max_candidates_2"] = idx < 2
    return out


def _inspect_attachment(row: dict, timeout: int) -> dict:
    url = row["url"]
    fetched = fetch_official_document(url, timeout=timeout)
    body = fetched.get("body") or b""
    ctype = str(fetched.get("content_type") or "")
    body_is_pdf = bytes(body).lstrip().startswith(b"%PDF-")
    is_pdf = "pdf" in ctype.lower() or url.lower().split("?", 1)[0].endswith(".pdf") or body_is_pdf
    pdf_complete = bool(body_is_pdf and b"%%EOF" in bytes(body[-65536:]))
    text = _extract_pdf_text(body) if is_pdf else (_html_text(body) if "html" in ctype.lower() else "")
    identities = _canonical_identity_keys_from_text(text) if text else []
    probe = _pasal3_probe(text)
    return {
        **{k: row.get(k) for k in ("rank", "score", "url", "label", "production_selected_max_candidates_2")},
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
        "primary_identity": identities[0] if identities else None,
        **probe,
        "error": fetched.get("error"),
    }


def _classify(trace: dict) -> str:
    attachments = trace.get("attachments") or []
    selected = [a for a in attachments if a.get("production_selected_max_candidates_2")]
    any_pasal3 = [a for a in selected if a.get("contains_Pasal_3")]
    if any_pasal3 and any(a.get("primary_identity") != EXPECTED for a in any_pasal3):
        return "A_PDF_HAS_PASAL3_BUT_PRIMARY_IDENTITY_MISMATCH"
    if not any(a.get("contains_Pasal_3") for a in selected):
        later = [a for a in attachments if not a.get("production_selected_max_candidates_2") and a.get("contains_Pasal_3")]
        if later:
            return "B_CORRECT_ATTACHMENT_OUTSIDE_TOP2"
    aligned_selected = [a for a in selected if a.get("primary_identity") == EXPECTED]
    if aligned_selected and not any(a.get("contains_Pasal_3") for a in aligned_selected):
        return "C_ALIGNED_PDF_TEXT_DOES_NOT_CONTAIN_PASAL3"
    resolver = trace.get("production_resolver") or {}
    if resolver.get("resolver_status") == "DETAIL_HTML_TEXT":
        return "D_PRODUCTION_FELL_BACK_TO_DETAIL_HTML"
    if any_pasal3 and any(a.get("primary_identity") == EXPECTED for a in any_pasal3):
        return "E_ATTACHMENT_IS_GOOD_CHECK_PROVISION_VERIFIER_WIRING"
    return "UNCLASSIFIED_REVIEW_TRACE"


def run(detail_url: str, timeout: int) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    detail = fetch_official_document(detail_url, timeout=timeout)
    body = detail.get("body") or b""
    detail_text = _html_text(body) if "html" in str(detail.get("content_type") or "").lower() else ""
    detail_ids = _canonical_identity_keys_from_text(detail_text) if detail_text else []
    candidates = _collect_candidates(detail.get("final_url") or detail_url, body)

    production = resolve_official_fulltext(
        detail.get("final_url") or detail_url,
        body,
        detail.get("content_type") or "",
        requested_provisions=[PROVISION],
        timeout=timeout,
        max_candidates=2,
        expected_identity_key=EXPECTED,
    )

    attachment_traces = [_inspect_attachment(c, timeout) for c in candidates]

    trace = {
        "trace_version": "R36_DIAGNOSTIC_ONLY_V1",
        "started_at": started,
        "expected_identity_key": EXPECTED,
        "requested_provision": PROVISION,
        "detail_url": detail_url,
        "detail_fetch": {
            "reachable": bool(detail.get("reachable")),
            "http_status": detail.get("http_status"),
            "final_url": detail.get("final_url"),
            "content_type": detail.get("content_type"),
            "content_length": len(body),
            "detail_text_length": len(detail_text),
            "identity_candidates": detail_ids[:20],
            "primary_identity": detail_ids[0] if detail_ids else None,
            "contains_Pasal_3": _pasal3_probe(detail_text)["contains_Pasal_3"],
            "error": detail.get("error"),
        },
        "candidate_links_found": len(candidates),
        "candidate_links": candidates,
        "production_resolver": {
            "resolved": bool(production.get("resolved")),
            "resolver_status": production.get("resolver_status"),
            "resolved_source_url": production.get("source_url"),
            "resolved_identity_key": production.get("resolved_identity_key"),
            "identity_candidates": production.get("identity_candidates") or [],
            "identity_aligned": production.get("identity_aligned"),
            "candidate_links_found": production.get("candidate_links_found"),
            "attempted_urls": production.get("attempted_urls") or [],
            "resolved_text_length": len(production.get("text") or ""),
            **_pasal3_probe(production.get("text") or ""),
        },
        "attachments": attachment_traces,
    }
    trace["diagnostic_classification"] = _classify(trace)
    return trace


def _summary(trace: dict) -> str:
    r = trace["production_resolver"]
    lines = [
        "=" * 88,
        "R36 DIAGNOSTIC TRACE — UU 7/2017 PASAL 3 (NO PATCH / NO STATE MUTATION)",
        "=" * 88,
        f"Expected identity : {trace['expected_identity_key']}",
        f"Provision         : {trace['requested_provision']}",
        f"Detail URL        : {trace['detail_url']}",
        f"Candidate links   : {trace['candidate_links_found']}",
        "",
        "PRODUCTION RESOLVER (max_candidates=2)",
        f"  status          : {r.get('resolver_status')}",
        f"  resolved        : {r.get('resolved')}",
        f"  source_url      : {r.get('resolved_source_url')}",
        f"  identity        : {r.get('resolved_identity_key')}",
        f"  aligned         : {r.get('identity_aligned')}",
        f"  text_length     : {r.get('resolved_text_length')}",
        f"  contains Pasal3 : {r.get('contains_Pasal_3')}",
        f"  attempted_urls  : {len(r.get('attempted_urls') or [])}",
        "",
        "ATTACHMENTS",
    ]
    for a in trace.get("attachments") or []:
        flag = "TOP2" if a.get("production_selected_max_candidates_2") else "later"
        lines += [
            f"  #{a.get('rank')} [{flag}] score={a.get('score')}",
            f"    label         : {a.get('label')}",
            f"    url           : {a.get('url')}",
            f"    reachable     : {a.get('reachable')} status={a.get('http_status')}",
            f"    content_type  : {a.get('content_type')}",
            f"    bytes         : {a.get('content_length')}",
            f"    pdf_eof       : {a.get('pdf_complete_eof')}",
            f"    text_length   : {a.get('extracted_text_length')}",
            f"    primary_id    : {a.get('primary_identity')}",
            f"    identities    : {a.get('identity_candidates')}",
            f"    contains P3   : {a.get('contains_Pasal_3')} pos={a.get('Pasal_3_position')}",
        ]
    lines += ["", f"CLASSIFICATION: {trace.get('diagnostic_classification')}", "=" * 88]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail-url", default=DEFAULT_DETAIL_URL)
    ap.add_argument("--timeout", type=int, default=8)
    args = ap.parse_args()
    trace = run(args.detail_url, max(1, min(20, args.timeout)))
    json_path = Path("trace_r36_uu7_pasal3.json")
    txt_path = Path("trace_r36_uu7_pasal3_summary.txt")
    json_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = _summary(trace)
    txt_path.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"JSON trace  : {json_path.resolve()}")
    print(f"Text summary: {txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
