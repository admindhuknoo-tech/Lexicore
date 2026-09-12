# LexiCore Final Corrective Contract Migration V2.3.1

## Scope
This corrective release closes exactly the three freeze blockers observed in the 09:49 benchmark. No new reasoning feature or parallel pipeline is introduced.

## Cross-layer migration
Every change is evaluated against the canonical contract:
Issue → Applicable Law → Legal Elements → Alleged Act → Evidence → Counter-Evidence → Element Test → Causation → Risk → Procedural/Merits Classification → Recommended Action.

### Gate 1 — Document Posture Ownership
- BAP/Pemeriksaan Tersangka is resolved before decision/order markers.
- Reader-facing document_type becomes `Berita Acara Pemeriksaan Tersangka`.
- Prevents `penetapan tersangka` / ceremonial wording from making a BAP a judicial decision.

### Gate 2 — Evidence Proposition Admissibility
- Element-specific evidence is re-gated even when supplied by an upstream mapper.
- Questions, summons metadata, generic approval, repayment/collateral context and accusation labels cannot prove a criminal element by topical overlap alone.
- Criminal proposition rules cover unlawful act/abuse, mens rea/benefit, state loss, causation and personal attribution.

### Gate 3 — Issue → Law → Element Strict Ownership
- Deterministic issue ownership prevents a causation element from falling into a tempus issue.
- Banking/POJK rules may remain contextual but are rejected as governing law for Tipikor offence elements unless a criminal/Tipikor norm is present.
- Hard lineage violations make `semantic_status=FAIL`, while ordinary missing/unverified gates remain `HOLD`.

## Consumer migration
- Persistence remains through the existing `attach_reasoning_contract` path.
- PDF/DOCX common exporter now prints structural and semantic contract status separately and surfaces hard violations.
- Web UI shows both structural and semantic status.

## Definition of Done
Core reasoning is frozen when both benchmark families (civil inheritance/land and criminal BAP/Tipikor) have:
1. structural contract PASS;
2. semantic status PASS or HOLD only for missing/unverified evidence/law;
3. zero hard semantic violations;
4. correct document posture;
5. no evidence proposition mismatch;
6. no issue/law/element ownership mismatch.

After this point, wording, retrieval coverage, source availability, UI polish, or new legal domains do not reopen core reasoning unless one of the frozen invariants is reproducibly violated.
