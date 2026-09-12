# LexiCore v1.4.7 — Test License-Gate Isolation

Date: 2026-09-11
Baseline: v1.4.6 Mobile Profile Onboarding
Scope: pytest/release-test isolation only; no production licensing semantics changed.

## Defect

When the commercial desktop launcher test called `configure_runtime_environment()`, it could set `LEXICORE_LICENSE_REQUIRED=1` directly in `os.environ`. If the variable did not already exist, pytest's `monkeypatch.delenv(..., raising=False)` had no previous value to restore. The commercial gate therefore leaked into later smoke tests, causing ordinary API endpoints to return `403 LICENSE_REQUIRED` instead of their expected 200/400/422 responses.

This explains the broad failure pattern in which unrelated endpoints (AI status, dashboard, regulations, drafting, case analysis, compliance, communications, OCR status, exports) all failed with the same 403 response.

## Correction

`tests/conftest.py` now forces `LEXICORE_LICENSE_REQUIRED=0` as part of the same deterministic test bootstrap that already overrides database, backup, AI provider, and API-key settings. Dedicated licensing tests explicitly remove/enable that variable when validating commercial desktop behavior. Because the variable now exists before each licensing test begins, pytest's monkeypatch teardown reliably restores the test baseline after the launcher enables the gate.

Two regression assertions were added to `tests/test_license_activation_gate_v144.py`: one verifies the default test baseline is disabled, and one verifies it is restored after the launcher test.

The patch also carries the canonical v1.4.6 `tests/test_reader_export_final_sanitizer_dedup_v126.py` so installations with the older capitalized `Keterkaitan Materi Perkara` assertion are synchronized with the later reader-normalization contract (`keterkaitan materi perkara`). This is test-contract synchronization only; exporter behavior is not changed.

## Security posture

The production commercial license gate remains fail-closed. `desktop_launcher.py` still sets `LEXICORE_LICENSE_REQUIRED=1` for commercial desktop runtime, and `app.py` still returns `403 LICENSE_REQUIRED` for protected API calls when no valid signed license is present. The correction applies only to pytest bootstrap isolation.

## Validation in build workspace

- `python -m pytest -q tests/test_license_activation_gate_v144.py tests/test_reader_export_final_sanitizer_dedup_v126.py` → **15 passed**
- `python tools/release_audit.py` → **PASS** (`v1.3.14-rc18`, templates=43, regulations=48)
- `python -m py_compile tests/conftest.py tests/test_license_activation_gate_v144.py` → **PASS**

Full Flask smoke execution was not available in the packaging container because that container does not include the project Flask runtime dependency. The user's Windows environment already has those dependencies; the release verification command is provided with the patch.
