# LexiCore v1.4.9 — Commercial Release Artifact Hygiene

Date: 2026-09-11  
Baseline: v1.4.8 Orphaned Export-Contract Duplicate Removal  
Scope: release/build-pipeline hygiene only. No SAL, evidence, tempus, positive-law, Candidate Law Governor, canonical reasoning, exporter semantics, persistence semantics, or production licensing semantics are changed.

## Defects closed

1. `.env` was not excluded by `tools/build_release.py`, so a developer/local environment file could be copied into a full-project release archive.
2. Runtime/local artifacts did not have an explicit deny boundary for uploads, instance state, logs, SQLite/DB files, or common private-key container formats.
3. The source-tree `BUILD_MANIFEST.json` could be copied into the staging tree, hashed as a release record, and then overwritten by the newly generated manifest. That made the recorded hash refer to the pre-build manifest rather than the final generated file.

## Correction

`tools/build_release.py` now:

- excludes `.env` while preserving `.env.example`;
- excludes `.git`, backups, uploads, instance state, dist/venv/cache trees and nested patch/rollback trees;
- excludes `.db`, `.sqlite`, `.sqlite3`, `.log`, `.key`, `.p12`, `.pfx`, explicit `license_private_key.pem`, and PEM files whose names identify private/signing keys;
- explicitly preserves `license_public_key.pem` because the commercial desktop build requires the public Ed25519 verification key;
- excludes the source-tree `BUILD_MANIFEST.json` from release records and generates one fresh manifest after the final file-record list is complete;
- records `artifact_hygiene_revision=v1.4.9` and `manifest_self_entry=false` in the generated manifest.

A manifest intentionally does not hash its own final serialized bytes. A self-hash would change the manifest content and therefore invalidate itself. The distributable manifest instead hashes every other included release file and clearly declares that no self-entry is present.

## Regression coverage

`tests/test_release_artifact_hygiene_v149.py` verifies the deny boundary for secrets/runtime state, confirms `.env.example` and `license_public_key.pem` remain distributable, and locks the fresh-manifest rule.

## Release boundary

This corrective is infrastructure/package hygiene only. It does not reopen the LexiCore Semantic Contract Freeze. The next deployment step remains: full Windows regression in the complete runtime environment, production Ed25519 signing-key generation on the license server, license-server deployment, public-key placement in the desktop build, first activation token/license creation, then commercial Windows installer build.
