# LexiCore RC18 — Generalized Case Analysis Architectural Closure

## Decision
One integrated correction. No new domain-specific classifier branch and no parallel tempus engine.

## Production changes
- `services/material_tempus_extractor.py`
  - event/date ownership strength now uses corroborating event cues and explicit lifecycle anchors;
  - a uniquely strongest material event date may be selected while equal-strength competing dates remain fail-closed;
  - statute-year and procedural-date ownership guards remain intact.
- `services/general_case_orchestrator.py`
  - derives document procedural posture from structural source markers, not legal-domain labels;
  - exposes canonical material-tempus result to the Case Analysis result;
  - normalizes generated template leakage only when it contradicts source posture;
  - preserves source text, evidence/source ledgers, official verification and Regulatory Corpus output;
  - collapses repeated NONE pseudo-conflicts to one `NO_MATERIAL_NORM_CONFLICT_IDENTIFIED` status.
- `routes/case_analysis.py`
  - applies general orchestration after reasoning/professional guards and before readiness/Working Paper projection.

## Frozen
- OCR/document ingestion.
- Regulatory Corpus retrieval.
- Positive-law identity/status/provision verification.
- Evidence/source ledgers.
- Case Readiness formula.

## Acceptance
A new legal domain must not require adding a new `if domain == ...` branch in this package. Unknown domains may remain GENERAL but must still produce facts/evidence/tempus/legal-source needs through the existing core.
