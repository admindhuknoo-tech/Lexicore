# LexiCore v1.4.9.1 — Release Audit Virtual-Environment Isolation

Date: 2026-09-11
Baseline: v1.4.9 Commercial Release Artifact Hygiene
Scope: release-audit scanning only; no production runtime, licensing semantics, exporter semantics, or legal reasoning changed.

## Defect
On a Windows project that contains `.venv-release`, `tools/release_audit.py` recursively scanned third-party `site-packages`. Generic dependency files such as `rapidocr/.../common.py`, `reportlab/.../common.py`, and `shapely/tests/common.py` were incorrectly classified as orphaned copies of the LexiCore exporter contract.

## Correction
The release audit now has one deterministic source-scan exclusion helper. It ignores local/runtime environment trees including `.venv`, `.venv-release`, any directory beginning with `.venv`, `venv`, `env`, `node_modules`, `dist`, and `build`, in addition to existing Git/cache exclusions. The same exclusion is used by both the Python parse sweep and the orphan-exporter duplicate guard.

The exporter duplicate guard still fails closed for duplicate contract files anywhere in the actual LexiCore source tree.

## Semantic boundary
No SAL, evidence admission, positive-law verification, tempus, Candidate Law Governor, canonical reasoning, licensing behavior, persistence, exporter rendering, or application runtime code was changed.
