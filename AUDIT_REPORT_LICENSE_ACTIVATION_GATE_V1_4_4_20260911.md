# LexiCore v1.4.4 — Commercial Desktop License & Activation Gate

Scope: deployment/security layer only. No SAL, evidence admission, positive-law, tempus, retrieval, canonical reasoning, or legal export semantics changed.

Implemented:
- one-device activation using SHA-256 multi-source device fingerprint;
- activation token transmitted only to activation server and not persisted locally;
- Ed25519 signed local license envelope; desktop contains public verification key only;
- fail-closed API gate in commercial desktop runtime;
- scheduled revalidation with signed offline-grace boundary;
- desktop deactivation plus admin reset/revoke reference endpoints;
- HTTPS requirement for non-local activation endpoints;
- first-run activation UI occurs before user/firm profile onboarding;
- PyInstaller build requires `license_public_key.pem` and never packages a private signing key.

Reference activation service lives under `license_server/` and must be deployed separately behind TLS. Private key, token pepper, and admin key remain server-only.
