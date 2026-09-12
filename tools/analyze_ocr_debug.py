"""Analyze LexiCore OCR JSONL telemetry produced with LEXICORE_OCR_DEBUG=1."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

SUCCESS_EVENTS = {"PAGE_NATIVE", "PAGE_DONE"}
TIMEOUT_EVENTS = {"RAPID_TIMEOUT", "TESSERACT_TIMEOUT"}
RENDER_EVENTS = {"PAGE_ERROR"}
BUDGET_EVENTS = {"GLOBAL_BUDGET_EXHAUSTED"}


def load_events(path: Path):
    events = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
    return events


def analyze(events):
    if not events:
        return {"runs": [], "message": "No telemetry events found"}

    by_run = defaultdict(list)
    for event in events:
        by_run[event.get("run_id") or "unknown"].append(event)

    summaries = []
    for run_id, run_events in by_run.items():
        pages = defaultdict(list)
        for ev in run_events:
            if isinstance(ev.get("page"), int):
                pages[ev["page"]].append(ev)

        document_start = next((e for e in run_events if e.get("event") == "DOCUMENT_START"), {})
        document_done = next((e for e in reversed(run_events) if e.get("event") == "DOCUMENT_DONE"), {})
        expected_total = int(document_start.get("pages_total") or document_done.get("pages_total") or len(pages))

        page_rows = []
        category_counter = Counter()
        for page_num in range(1, expected_total + 1):
            logs = pages.get(page_num, [])
            event_names = [e.get("event") for e in logs]
            event_set = set(event_names)
            engines = [e.get("engine") for e in logs if e.get("engine")]
            errors = [e.get("error") for e in logs if e.get("error")]

            if "PAGE_NATIVE" in event_set:
                category = "native_success"
            elif "PAGE_DONE" in event_set:
                category = "ocr_success"
            elif any(e in event_set for e in BUDGET_EVENTS):
                category = "budget_exhausted"
            elif "CIRCUIT_SKIP" in event_set or "RAPID_INFLIGHT_SKIP" in event_set:
                if "TESSERACT_SUCCESS" in event_set:
                    category = "fallback_success"
                else:
                    category = "circuit_or_inflight_skip"
            elif any(e in event_set for e in TIMEOUT_EVENTS):
                if "TESSERACT_SUCCESS" in event_set or "RAPID_SUCCESS" in event_set:
                    category = "fallback_success"
                else:
                    category = "engine_timeout"
            elif "PAGE_ERROR" in event_set:
                category = "page_or_render_error"
            elif "PAGE_FAILED" in event_set:
                category = "empty_or_no_ocr_text"
            elif logs:
                category = "attempted_unclassified"
            else:
                category = "not_attempted"

            category_counter[category] += 1
            page_rows.append({
                "page": page_num,
                "category": category,
                "events": event_names,
                "engines": engines,
                "errors": errors,
            })

        rapid_elapsed = [float(e["elapsed"]) for e in run_events if e.get("event") in {"RAPID_SUCCESS", "RAPID_TIMEOUT", "RAPID_ERROR"} and e.get("elapsed") is not None]
        tess_elapsed = [float(e["elapsed"]) for e in run_events if e.get("event") in {"TESSERACT_SUCCESS", "TESSERACT_EMPTY", "TESSERACT_TIMEOUT", "TESSERACT_ERROR"} and e.get("elapsed") is not None]
        render_elapsed = [float(e["elapsed"]) for e in run_events if e.get("event") == "RENDER_DONE" and e.get("elapsed") is not None]

        summary = {
            "run_id": run_id,
            "file": document_start.get("file"),
            "pages_total": expected_total,
            "categories": dict(sorted(category_counter.items())),
            "event_counts": dict(Counter(e.get("event") for e in run_events)),
            "timing": {
                "rapid_avg_seconds": round(mean(rapid_elapsed), 3) if rapid_elapsed else None,
                "rapid_max_seconds": round(max(rapid_elapsed), 3) if rapid_elapsed else None,
                "tesseract_avg_seconds": round(mean(tess_elapsed), 3) if tess_elapsed else None,
                "tesseract_max_seconds": round(max(tess_elapsed), 3) if tess_elapsed else None,
                "render_avg_seconds": round(mean(render_elapsed), 3) if render_elapsed else None,
                "render_max_seconds": round(max(render_elapsed), 3) if render_elapsed else None,
                "document_ocr_elapsed_seconds": document_done.get("elapsed"),
            },
            "final": {
                "pages_native": document_done.get("pages_native"),
                "pages_ocr": document_done.get("pages_ocr"),
                "pages_failed": document_done.get("pages_failed"),
                "characters_ocr": document_done.get("characters_ocr"),
                "total_timeout_exceeded": document_done.get("total_timeout_exceeded"),
            },
            "pages": page_rows,
        }
        summaries.append(summary)
    return {"runs": summaries}


def print_human(report):
    for run in report.get("runs", []):
        print(f"Run: {run['run_id']}")
        if run.get("file"):
            print(f"File: {run['file']}")
        print(f"Pages total: {run['pages_total']}")
        print("Categories:")
        for key, value in run["categories"].items():
            print(f"  {key}: {value}")
        print("Timing:")
        for key, value in run["timing"].items():
            print(f"  {key}: {value}")
        print("Final:")
        for key, value in run["final"].items():
            print(f"  {key}: {value}")
        unresolved = [p for p in run["pages"] if p["category"] not in {"native_success", "ocr_success", "fallback_success"}]
        if unresolved:
            print("Unresolved pages:")
            for p in unresolved:
                err = f" | errors={p['errors']}" if p["errors"] else ""
                print(f"  page {p['page']}: {p['category']} | events={p['events']}{err}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Analyze LexiCore OCR debug JSONL")
    parser.add_argument("log_file", nargs="?", default="ocr_debug.jsonl")
    parser.add_argument("--json", dest="json_out", default="ocr_debug_summary.json")
    args = parser.parse_args()
    path = Path(args.log_file)
    if not path.exists():
        raise SystemExit(f"Telemetry file not found: {path}")
    report = analyze(load_events(path))
    Path(args.json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print_human(report)
    print(f"Summary JSON: {args.json_out}")


if __name__ == "__main__":
    main()
