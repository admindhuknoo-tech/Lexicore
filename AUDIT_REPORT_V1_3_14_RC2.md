# LexiCore v1.3.14-rc2 — Evidence Hygiene Corrective

## Scope
RC2 fixes user-facing Case Analysis evidence pollution discovered in the Elya Dwi Admoko benchmark.

## Enforced rules
- Counsel identity/contact/address is metadata, never a fact proved.
- Filing/representation metadata (Surat Kuasa, clerk registration, case number/hearing metadata) is excluded from Evidence Map.
- Petitum/prayers and legal argument are excluded from factual evidence rows.
- Bare number/amount fragments are excluded.
- Evidence Map allowlist: ACTUAL_EVIDENTIARY_ITEM, EVIDENCE_ASSERTION, CASE_FACT only, with material semantic concepts.
- Raw source ledger remains internal; user-facing UI/export uses material_source_ledger.
- Legal Construction may not pair an issue with LEGAL_ARGUMENT or PLEADING_ASSERTION as material fact.
- Official regulatory search results are user-reportable only after identity confirmation + CASE_NEXUS_VERIFIED.

## Validation
- Python compileall: PASS
- Structural release audit: PASS
- Inline JavaScript syntax: PASS
- Targeted evidence hygiene checks: PASS
- Product: LexiCore Assistant
- Technical release: 1.3.14-rc2

Full Flask pytest must still be run on the user's local environment through release_check.bat.
