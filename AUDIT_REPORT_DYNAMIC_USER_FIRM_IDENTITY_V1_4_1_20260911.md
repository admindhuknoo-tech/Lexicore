# LexiCore v1.4.1 — Dynamic User/Firm Identity Deployment Gate

Date: 2026-09-11
Baseline: v1.4.0 (`CLIENT_INTAKE_LEGAL_POSITION_DRAFT_LINK`)
Scope: deployment/presentation identity only.

## Objective
Remove `ELF - Erfan's Law Firm` as a hard-coded commercial user identity while preserving `LexiCore` as the stable product brand. Add one local user/firm profile that becomes the single source of truth for application identity and document exports.

## Implementation
- Added `identity_profile.py` as the canonical dynamic identity provider.
- Added singleton SQLite table `app_profile`; schema version raised from 11 to 12 with idempotent migration.
- Added `GET/PUT /api/profile`.
- Added first-run/user-editable Profile UI for professional name, firm name, credentials, office address, phone, email, and watermark text.
- Application header/sidebar/busy state now hydrate from the active profile.
- Client communication sign-off reads the active identity dynamically.
- Legal Drafting working-note identity reads the active identity dynamically.
- Generic draft/workspace DOCX exports use the active profile and author metadata.
- Case Analysis PDF/DOCX masthead, header/footer, and author metadata use the active profile.
- Commercial production files contain no hard-coded `ELF - Erfan's Law Firm` identity.
- Neutral fallback: `Pengguna LexiCore` when profile setup has not yet been completed.

## Non-goals / Frozen Core
No change to SAL, evidence admission, positive-law verification, tempus, canonical legal reasoning, regulatory retrieval, Candidate Law Governor, or Case Analysis substantive logic.

## Validation
- Python compilation: PASS.
- Inline JavaScript syntax (`node --check`): PASS.
- Targeted identity/lifecycle/export regression: 24 PASS.
- Structural release audit: PASS (`v1.3.14-rc18`, templates=43, regulations=48).
- Full non-smoke regression: 448 PASS in 27.01s; the container wrapper timed out immediately after pytest printed the completed 448/448 summary, so this is recorded as completed test output with runner shutdown timeout rather than a test failure.
