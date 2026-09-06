# LexiCore v1.3.14-rc4 — Trace/Material Separation & Export Integrity

RC4 corrects three regressions without weakening the professional evidence guards:

1. `source_ledger` is again a broad audit trace (`DETERMINISTIC_EXTRACTIVE`), including pleading structure such as PERMOHONAN/REKONVENSI. It is not used directly as lawyer-facing evidence.
2. `material_source_ledger` and `evidence_rows` remain the strict projection that excludes counsel address/identity, procedural metadata, prayers, legal argument, bare fragments and other non-merits noise.
3. Every Case Analysis PDF/DOCX receives a `Konteks Perkara / Sumber` section so a fail-closed Evidence Map cannot accidentally produce a content-empty report.
4. Regulatory discovery and merits reporting are separated: `regulation_reportable()` preserves candidate visibility for compatibility/diagnostics; `regulation_merits_reportable()` is the strict lawyer-facing gate used by exporters.

Core legal invariants remain unchanged: no silent correction, no argument-as-fact, no metadata-as-evidence, no article-before-instrument identity, no applicable-law conclusion before status/tempus/nexus verification.
