# LexiCore v1.4.12 — License Authority GUI

Scope: administrator-side offline license issuance workflow only.

## Changes
- Adds `license_admin/gui.py`, a Tkinter administrator GUI for issuing device-bound `.lic` files.
- Supports three bounded plans: Trial 30 days, Annual 365 days, and Desktop Perpetual.
- Records issuance metadata in administrator-local `license_ledger.csv`.
- Adds `run_license_authority.bat` for simple launch on the licensing workstation.
- Refactors `license_admin/issue_license.py` to expose a reusable issuance function while preserving the existing CLI.
- Updates offline licensing documentation.

## Security boundary
- `license_private_key.pem` remains administrator-only and is never copied into the desktop project/installer.
- The GUI writes customer licenses only under the selected License Authority directory.
- Desktop remains offline/standalone; no runtime license server is introduced.
- License remains bound to exactly one Installation ID/device fingerprint.

## Frozen core
No SAL, evidence admission, tempus, positive-law verification, Candidate Law Governor, retrieval, canonical reasoning, persistence, legal output semantics, or customer Desktop licensing verification semantics are changed.
