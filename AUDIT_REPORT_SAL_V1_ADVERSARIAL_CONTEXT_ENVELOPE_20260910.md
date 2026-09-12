# LexiCore SAL v1.0 — Adversarial Context Envelope

## Scope
Selective contract migration only. No taxonomy redesign, no parallel orchestrator, no change to positive-law/tempus/evidence fail-closed gates.

## Implemented
- Header-first binary speaker ownership: PROSECUTOR/PROSECUTION/ALLEGATION and DEFENSE_COUNSEL/DEFENSE/REBUTTAL.
- Frozen SAL JSON schema remains unchanged. Ownership is encoded in existing `provenance` and `domain_posture` strings and projected into governed route tokens/pool rows.
- Prosecutor unilateral accusatory declarations are demoted from FACT_ASSERTION to PARTY_ARGUMENT.
- Defense unilateral jurisdiction/error-in-persona/nullity declarations are demoted from FACT_ASSERTION to COUNTER_ARGUMENT.
- Evidence Map remains prohibited for both classes.
- Neutral factual documents remain unaffected.
- No raw-source fallback was added.

## Benchmark intent
The same case may be analyzed from paired PH and JPU documents without collapsing either speaker's proposition into an objective fact.
