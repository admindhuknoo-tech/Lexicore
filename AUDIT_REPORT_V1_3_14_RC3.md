# LexiCore v1.3.14-rc3 — Professional Legal Review Engine

## Goal
Implement a multi-pass legal review layer that behaves less like a keyword classifier and more like a disciplined lawyer review: read the document, separate facts from argument/metadata, find drafting/citation/date/name anomalies, test legal gates, attack weak reasoning, and produce prioritized recommendations.

## Integrated pipeline
1. READ_AND_CLASSIFY_DOCUMENT
2. SEPARATE_FACT_ARGUMENT_METADATA
3. CHECK_TEXT_ENTITY_DATE_CITATION_ANOMALIES
4. TEST_TEMPUS_IDENTITY_NEXUS_AND_EVIDENCE_GATES
5. ADVERSARIAL_ARGUMENT_REVIEW
6. SYNTHESIZE_STRENGTHS_WEAKNESSES
7. BUILD_PRIORITIZED_RECOMMENDATIONS

## Fail-closed rules
- no silent source correction;
- no legal conclusion from keyword/domain alone;
- no merits fact from metadata/pleading;
- no applicable-law conclusion before identity/status/tempus/nexus verification;
- every proposed correction is a candidate requiring primary-source verification.

## EKSEPSI Elya benchmark
Targeted run against the original DOCX detected:
- TEMPUS_GAP — CRITICAL;
- SK number year 2021 vs explicit date year 2011 — HIGH;
- Elya Dwi Ademoko vs Elya Dwi Atmoko name variation — HIGH;
- FORUM_VS_MERITS — HIGH;
- ERROR_IN_PERSONA_VS_ATTRIBUTION — HIGH;
- FIDUCIARY_NON_DISPOSITIVE — HIGH;
- three legal citation anomalies (1/2003, 31/2099, 20/2021);
- multiple probable text/OCR typos (piodana, undng, flafon, agugtus, jombangt, berweang, etc.);
- no verified applicable law -> HOLD_FOR_VERIFICATION.

The engine also produced an objection-specific strategic recommendation: rebuild the objection around verifiable formal/procedural defects, separate forum/indictment defects from merits, audit tempus/citations, and align the petitum with the exact objection ground.

## Validation completed in sandbox
- Python compileall: PASS
- Professional Review targeted tests: 2 PASS
- JavaScript inline syntax: PASS
- Structural release audit: PASS
- Templates: 43
- Regulations: 45

Full Flask smoke/regression suite must still be run in the user's Windows environment because Flask is not installed in this sandbox.
