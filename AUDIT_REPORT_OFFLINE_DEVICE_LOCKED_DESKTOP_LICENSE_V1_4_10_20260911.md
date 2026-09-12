# LexiCore v1.4.10 — Offline Device-Locked Desktop License

Date: 2026-09-11
Baseline: v1.4.9.1 release-audit isolation
Scope: desktop licensing/deployment only; no legal reasoning core change.

## Commercial desktop policy

Desktop licensing no longer depends on a runtime activation server. First run displays a SHA-256 Installation ID derived from the existing stable device fingerprint. The license authority issues an Ed25519-signed license envelope for that exact device. LexiCore verifies signature, product, ACTIVE status, optional expiry, and exact device fingerprint locally before exposing protected APIs.

The private signing key is never bundled. `build_desktop.bat` still fails when `license_public_key.pem` is missing. Reinstall on the same physical device is permitted when the stable fingerprint remains unchanged; copying the license to another device fails closed with `DEVICE_MISMATCH`.

## Removed from Desktop runtime

- activation token dependency
- `LEXICORE_LICENSE_SERVER_URL`
- `/v1/activate`, `/v1/validate`, `/v1/deactivate` calls
- 72-hour revalidation
- 14-day offline grace
- remote revoke/reset requirement

Those concepts are not needed for the standalone Desktop edition. Web Apps remains a separate online deployment target.

## New offline authority tools

- `license_admin/generate_keys.py`
- `license_admin/issue_license.py`
- `license_admin/README_OFFLINE_DESKTOP_LICENSE.txt`

## Frozen boundary

No SAL, evidence admission, tempus, positive-law verification, Candidate Law Governor, retrieval, canonical reasoning, persistence semantics, or substantive legal output is modified by this release.
