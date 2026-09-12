# LexiCore v1.3.9 — Client Authority Lifecycle & Draft Gate

## Scope
Selective lifecycle/orchestration correction based on legal-service practice. This release does not refactor the legal reasoning core.

## Lifecycle
User-facing module order:
1. Client / Intake & Matter
2. Legal Drafting / Authority
3. Contract Review
4. Case Analysis
5. Regulatory Corpus
6. Compliance & Risk
7. Legal Research
8. Norm Conflict Analysis

`Contract Review` remains contract analysis. It is no longer labeled or positioned as an attorney-client engagement gate.

## Client legal-service branch
Client now offers `Layanan Jasa Hukum` in addition to existing client update, document request, and legal notice flows.

Branches:
- `Konseling / Konsultasi Hukum`: produces a lawyer-review draft that expressly states consultation does not itself grant authority to act.
- `Permintaan Menjadi Kuasa Hukum`: routes directly to Draft and selects the existing `Surat Kuasa Khusus` template. Client name is projected as Pemberi Kuasa; Penerima Kuasa remains intentionally blank for professional completion. The draft prompt requires explicit scope and forbids assuming substitution, settlement, appeal, or other special powers.

## Safety / semantic boundary
A request to become counsel is not persisted or interpreted as signed authority. No new authority flag is added to Case Analysis, SAL, evidence, positive-law verification, or reasoning. Contract Review remains an optional work module.

## Production files changed
- `static/index.html`
- `client_communication.py`

## Regression coverage
- lifecycle order and dashboard order
- legal-service branch visibility
- representation request → Surat Kuasa draft route
- consultation non-authority wording
- preserved Norm Conflict semantics
