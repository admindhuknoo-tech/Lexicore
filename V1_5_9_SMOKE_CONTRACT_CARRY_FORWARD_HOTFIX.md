# LexiCore v1.5.9 Smoke Contract Carry-Forward Hotfix

Purpose: restore the already-approved v1.5.4 smoke-test contract that was not carried forward by the v1.5.8 patch package.

This hotfix does NOT modify production code. It edits exactly one legacy assertion in `tests/test_smoke.py` in-place and aborts if the expected old assertion is not found exactly once.

Expected contract:
- primary_domain = inheritance
- posture = PERDATA_LITIGASI
- civil_procedure remains in domain_contract
- land_property remains in domain_contract
