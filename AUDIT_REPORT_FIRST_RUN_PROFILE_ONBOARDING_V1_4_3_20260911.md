# LexiCore v1.4.3 — First-Run Profile Onboarding Fix

## Scope
Presentation / installation-profile lifecycle only. No legal reasoning, SAL, evidence admission, tempus, retrieval, positive-law, candidate-law, or exporter semantic rules were modified.

## Defect reproduced
The user/firm profile modal was global to the single-page workspace. When the initial profile was still unconfigured, the modal could remain visually present while the user moved between Client, Draft, Contract, Case, Corpus, Risk, Research, and Conflicts. The prior suppression state used browser sessionStorage, so the prompt lifecycle was browser-session scoped rather than installation scoped.

## Corrective design
1. `app_profile` gains `onboarding_seen_at` (schema v13, idempotent migration).
2. `get_identity_profile()` exposes `onboarding_seen` and `first_run_required`.
3. `POST /api/profile` marks the first-run identity onboarding as displayed exactly once for the local installation database.
4. On DOMContentLoaded, the profile dialog auto-opens only when `first_run_required` is true.
5. Main-menu navigation closes any open profile dialog so it never rides across multiple workspace modules.
6. The explicit `Profil` button remains available for later manual edits.

## Validation
- Python compile: PASS
- JavaScript syntax (`node --check` on inline scripts): PASS
- Targeted regression: 13 passed
- Structural release audit: PASS
- Full non-smoke regression: 457 passed

## Compatibility
Existing configured profiles remain configured and do not auto-prompt. Existing v12 databases migrate to v13 without deleting profile data. If onboarding was never recorded and the profile is empty, the first run after this update shows the identity prompt once; subsequent application runs do not auto-show it unless the user opens Profile manually.
