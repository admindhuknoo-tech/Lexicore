# LexiCore v1.4.8 — Orphaned Export-Contract Duplicate Removal

Date: 2026-09-11
Baseline: v1.4.7 Test License-Gate Isolation
Scope: filesystem/test-layer hygiene only; no reasoning-chain, exporter-rendering,
or licensing semantics changed.

## Requested benchmark (two Case Analysis outputs)

The two reference outputs (`0731` — Eksepsi Elya Dwi Admoko / Tipikor+perbankan,
`0729` — Duplik Perkara No. 44 / perdata-pertanahan-waris) were already the subject
of a full producer → orchestration → persistence → UI → exporter → benchmark → test
audit, documented in `AUDIT_REPORT_CONTRACT_MIGRATION_V2*` and closed in
`AUDIT_REPORT_FINAL_CORRECTIVE_CONTRACT_MIGRATION_V2_3_1`. That closure defines an
explicit Definition of Done for the 11-stage canonical reasoning contract
(Issue → Applicable Law → Legal Elements → Alleged Act → Evidence → Counter-Evidence
→ Element Test → Causation → Risk → Procedural/Merits Classification → Recommended
Action) and freezes it: wording, retrieval coverage, or new domains should not
reopen it absent a reproducible invariant violation. This audit did not find one on
the current baseline, so that freeze is respected and not reopened here.

What this audit adds is a **new** defect class the prior contract-migration series
did not check: duplicate copies of exporter-contract source files living outside
the canonical `exporters/` package.

## Defect

Two implementation files and one test file were orphaned copies of the canonical
reader-facing export contract, left behind by an earlier consolidation:

- `extractors/exporters/common.py` — a stale duplicate of `exporters/common.py`.
- `retrieval/exporters/common.py` — a second stale duplicate.
- `extractors/tests/test_reader_export_final_sanitizer_dedup_v126.py` — a duplicate
  of the canonical `tests/test_reader_export_final_sanitizer_dedup_v126.py`, still
  asserting the pre-RC18 capitalized `"Keterkaitan Materi Perkara"` residue label.
  It **fails** against the current exporter (`keterkaitan materi perkara`,
  lowercase, per the RC18 reader-normalization contract) — exactly the drift the
  v1.4.7 license-gate-isolation report warned installations about, just not yet
  cleaned out of this tree.

Neither `extractors/exporters/` nor `retrieval/exporters/` had an `__init__.py`,
so `from exporters.common import ...` inside their sibling test files always
resolved to the canonical top-level module (verified via
`sys.modules['exporters.common'].__file__` at import time) — the duplicates were
unreachable, not merely redundant. The risk is latent rather than active: a future
change that turns those folders into real packages, or that alters `sys.path`,
could start shadowing the canonical contract with a stale one, and nothing in
`tools/release_audit.py` would have caught it — its exporter-hygiene check only
inspects the contents of `exporters/` itself, not the rest of the tree.

A fourth file, `retrieval/tests/test_reader_export_final_render_lock_v127.py`, was
orphaned but **not** stale — it exercises real, still-current render-lock/dedup
behavior in `exporters/common.py` with no canonical counterpart under `tests/`, so
its coverage was invisible to the regression suite `tools/release_audit.py` and CI
are meant to run.

## Correction (cross-layer contract migration)

Treating this as a migration across the filesystem/package layer, the test layer,
and the release-gate layer, not a cosmetic cleanup:

1. **Filesystem/package layer** — removed the two unreachable duplicate
   implementation files and their now-empty `extractors/exporters/` and
   `retrieval/exporters/` directories. `exporters/common.py` remains the single
   source of truth, unchanged.
2. **Test layer** — removed the stale, now-failing duplicate
   `extractors/tests/test_reader_export_final_sanitizer_dedup_v126.py` (the
   canonical, passing copy under `tests/` already covers this contract). Promoted
   `retrieval/tests/test_reader_export_final_render_lock_v127.py` into
   `tests/test_reader_export_final_render_lock_v127.py` so its 5 render-lock/dedup
   assertions become part of the canonical regression suite instead of dead weight.
3. **Release-gate layer** — extended `tools/release_audit.py` with a new
   invariant: any file literally named `common.py`, `case_pdf.py`, `case_docx.py`,
   or `terminology_mapper.py` found anywhere in the tree outside `exporters/`
   fails the structural audit. This is a preventive control, not just a one-time
   fix — it closes the detection gap that let the two duplicates accumulate
   unnoticed in the first place. Verified by deliberately reintroducing a copy at
   `extractors/exporters/common.py`: the audit fails with a clear message, and
   passes again once removed.

## Validation in this workspace

Network and several runtime dependencies (`pytest`, `PyMuPDF`/`fitz`, `rapidocr`,
`onnxruntime`, `flask-cors`) are unavailable in this packaging container, so a full
`pytest`/Flask-smoke run could not be executed here. In their place:

- A dependency-free harness (`run_tests_no_pytest2.py`, not part of the shipped
  package) imported every test module and called every `test_*` function, using
  minimal `monkeypatch`/`tmp_path` stand-ins for the two pytest fixtures actually
  used by this suite: **394 passed, 0 failed, 0 errors**, 17 skipped (Flask-route,
  OCR, and desktop-runtime tests that need the missing packages above).
- `python tools/release_audit.py` → **PASS** (`v1.3.14-rc18`, templates=43,
  regulations=48), including the new orphaned-duplicate guard (confirmed to both
  fail and pass correctly, see above).
- `python -m py_compile` succeeds across the full tree (the audit's own AST-parse
  gate covers this).

The user's full environment (with `pytest`, `PyMuPDF`, `rapidocr`, `onnxruntime`,
`flask-cors` installed) should still run `python -m pytest -q` and
`python tools/release_audit.py` before treating this as release-ready; this report
does not substitute for that.

## Security/licensing posture

Not in scope for this correction and not touched: `licensing.py`,
`license_server/`, `desktop_launcher.py`, and the `commercial_license_gate`
before-request hook in `app.py` were read for verification only. Confirmed
consistent with the v1.4.7 report's claim — `licensing_required()` defaults to
disabled unless `LEXICORE_LICENSE_REQUIRED` is set, `desktop_launcher.py` sets it
to `1` for the commercial desktop runtime, `app.py` fails closed (`403
LICENSE_REQUIRED`) for protected `/api/` routes when no valid signed license is
present, and `tests/conftest.py` isolates the pytest baseline from that switch.
No changes were made to any of these files.
