# LexiCore v1.3.14 RC18 — Integrated Tempus Extraction Closure

## Baseline
OCR runtime is frozen after the Windows benchmark reached 37/37 pages. Positive-law exact verification is also frozen. This package changes only the canonical material-tempus candidate extractor and its focused regression coverage.

## Root cause addressed
The prior extractor was intentionally fail-closed but still missed defensible tempus in OCR-heavy legal documents when:
- an explicit date appeared without the literal word `tanggal`;
- OCR split an event cue and its date across adjacent lines;
- procedural dates (complaint/hearing) appeared near a material office/status event;
- one substantive conduct date coexisted with unrelated appointment/resignation chronology.

## Production change
`services/material_tempus_extractor.py`

1. Explicit Indonesian/numeric dates are now temporal anchors even without `tanggal`.
2. Adjacent OCR lines are evaluated as bounded context windows, but two already-dated sentences are never merged; this prevents cross-sentence date contamination.
3. Material events are ranked by tier:
   - Tier 2: alleged/substantive conduct/transaction events;
   - Tier 1: office/status events such as resignation, appointment, removal, office holding.
4. A unique Tier-2 date may be selected even if unrelated Tier-1 chronology exists.
5. If several competing dates remain within the highest material tier, extraction stays `MATERIAL_TEMPUS_AMBIGUOUS`.
6. Procedural, regulation, object/model, and document/stamp dates remain non-material unless independently bound to a material event.
7. Candidate provenance now includes `event_tier`, context, score, and reasons.

## Frozen invariants
- Extraction is candidate discovery only.
- It never sets `tempus_verified` or `applicable`.
- Unknown/ambiguous material time remains fail-closed.
- Positive-law identity/status/provision verification is unchanged.
- OCR code and OCR budget/scheduler are unchanged.
- Case Readiness formula is unchanged.

## Regression coverage
Focused Tempus suite validates:
- explicit date without `tanggal`;
- OCR line-break recovery;
- procedural complaint/hearing dates excluded;
- unique substantive conduct date outranks unrelated status chronology;
- competing substantive dates remain ambiguous;
- competing status dates remain ambiguous when no conduct date exists;
- regulation-only dates remain unknown;
- year-only candidate requires explicit temporal grammar;
- R30.1 credit-agreement date regression remains `2022-09-27`.

## Validation
- `python -m py_compile`: PASS
- focused material-tempus regressions: 18 PASS
- Windows `release_check.bat` remains the authoritative full-suite release gate.

## Runtime acceptance gate
Run the same 37/37 `ALL DKPP.pdf` Case Analysis and inspect Section 17 / regulation telemetry:
- material tempus must be a context-bound candidate with provenance, or explicitly AMBIGUOUS/UNKNOWN;
- `tempus_verified` may become 1 only if the downstream legal gate independently proves the instrument was legally operative at the extracted material time;
- no procedural complaint/hearing/statute date may be promoted merely because it is explicit.
