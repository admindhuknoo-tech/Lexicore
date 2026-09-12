"""One-shot diagnostic trace for the R22 exact-identity recovery path.

This script is diagnostic only. It does not change LexiCore verification state.
Run from the project root:

    set LEXICORE_OFFICIAL_TRACE=1
    set LEXICORE_TRACE_EXPECTED=UU:31:1999
    python run_trace.py
"""
from __future__ import annotations

import os
import json
from pathlib import Path

os.environ.setdefault("LEXICORE_OFFICIAL_TRACE", "1")
os.environ.setdefault("LEXICORE_TRACE_EXPECTED", "UU:31:1999")
os.environ.setdefault("LEXICORE_TRACE_FILE", "trace_r22_baseline.json")

from services.official_verification_trace import OfficialVerifierTrace
from services.regulatory_retrieval import _recover_expected_official_fulltext


def run_diagnostic_trace() -> int:
    OfficialVerifierTrace.clear()
    expected = "UU:31:1999"
    requested = ["Pasal 9", "Pasal 2 ayat (1)", "Pasal 3", "Pasal 18"]
    result = _recover_expected_official_fulltext(
        expected,
        requested,
        preferred_source_id="bpk",
        timeout=4,
        time_budget_seconds=8.0,
    )
    trace_path = Path(os.environ["LEXICORE_TRACE_FILE"])
    entries = OfficialVerifierTrace.get_trace()
    pre = next((x for x in entries if x.get("step") == "4_pre_recovery"), None)
    print("\n" + "=" * 80)
    print("TRACE SUMMARY - R22 BASELINE")
    print("=" * 80)
    print(f"Expected: {expected}")
    print(f"Exact lock: {(pre or {}).get('data', {}).get('exact_lock', False)}")
    print(f"Exact candidates found: {(pre or {}).get('data', {}).get('exact_count', 0)}")
    print(f"Recovery status: {result.get('resolver_status', 'unknown')}")
    print(f"Recovery exact_lock: {result.get('recovery_exact_lock', False)}")
    print(f"Resolved identity: {result.get('resolved_identity_key') or ''}")
    print(f"Attempted URLs: {len(result.get('recovery_attempted_urls') or result.get('attempted_urls') or [])}")
    print(f"Trace entries: {len(entries)}")
    print(f"Trace file: {trace_path.resolve()}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_diagnostic_trace())
