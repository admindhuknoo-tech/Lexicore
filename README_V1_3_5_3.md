# LexiCore v1.3.5.3 — BAP Benchmark & Full-Document Pipeline Corrective

Corrective release focused on the 36-page BAP benchmark.

- Full-document chunk diagnostics are retained even when Gemini fails; fallback no longer reports misleading `0/0` segments for a non-empty document.
- Gemini evidence extraction and synthesis calls receive bounded retries.
- Case export uses a concise `Ringkasan Eksekutif` instead of raw `decision_summary` / BAP text.
- Orphan/noisy article references and materially irrelevant domains are pruned from `Dasar Hukum`.
- Case export carries only regulatory essentials and tempus classification; the full regulatory corpus/intelligence remains in the dedicated Regulatory Corpus workspace.
- Post-event regulations are clearly labelled `POST_TEMPUS_EXCLUDED` in the case working paper until a richer official-date verification confirms applicability.
- Cross-domain criminal/civil coexistence is `RELATIONSHIP_ONLY`; Lex Specialis candidates require an explicit antinomy signal.
- Action Plan evidence items are de-duplicated and keep their specific evidence requirement as the issue label.
- Schema remains version 3. No database migration is required.

Release gate: `release_check.bat` must PASS before freezing this version.
