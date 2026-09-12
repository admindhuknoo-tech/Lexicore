# LexiCore v1.3.8 — Matter-Centric Lifecycle Navigation

## Scope
Selective information-architecture update only. No legal reasoning, SAL, evidence, tempus, retrieval, candidate-law, persistence, exporter, or API semantics were changed.

## Navigation lifecycle
The existing modules are presented in the operational order:

1. Client / Intake & Matter
2. Contract / Engagement Review
3. Regulatory Corpus
4. Case Analysis
5. Legal Research
6. Norm Conflict Analysis
7. Compliance & Risk
8. Legal Drafting / Output

`Norm Conflict Analysis` remains a legal antinomy module. It is intentionally **not** renamed to a client conflict-of-interest check because the existing implementation does not perform that function.

## Behavior
- Client / Intake & Matter is the default landing workspace.
- Dashboard metric cards follow the same lifecycle order.
- Case Analysis companion links use semantic labels rather than stale hard-coded sequence numbers, allowing Research and Norm Conflict to operate as companion tools without implying a rigid backend pipeline.
- Backend services remain modular; only navigation/orchestration presentation changes.

## Freeze boundary
Untouched: SAL, semantic admission, source ownership, evidence admission, applicable-law gates, tempus, canonical legal reasoning chain, candidate-law governor, regulatory retrieval, persistence schema, export semantics.
