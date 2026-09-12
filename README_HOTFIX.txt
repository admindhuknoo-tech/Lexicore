LexiCore SAL v1.0 SSoT — Bare Evidence Reference Hotfix

Purpose:
- Ensures short evidence-reference phrases such as "bukti kerugian" are typed as DOCUMENT_REFERENCE.
- Such statements remain LEAD_ONLY and cannot enter Alleged Act or Evidence Map.
- No reasoning refactor. No fallback added.

Apply:
Extract this ZIP into the LexiCore project root and allow replacement of:
  services\semantic_admission.py

Verify:
  py -m pytest tests\test_sal_v1_single_source_truth.py -q
Expected:
  7 passed
