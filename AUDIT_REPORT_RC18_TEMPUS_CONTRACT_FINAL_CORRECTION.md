# LexiCore RC18 — Tempus Contract Final Correction

## Scope
One canonical production file only: `services/material_tempus_extractor.py`.

## Corrections
- Restores established `selection_basis` strings for backward compatibility.
- Multiple competing material dates in the same materiality tier fail closed even if incidental extraction scores differ.
- A strongest date may be selected only when it has an explicit lifecycle anchor and a material score margin, preserving the DKPP benchmark without domain-specific rules.
- OCR, positive-law verification, applicable-law code, corpus, and reporting are unchanged.
