# LexiCore v1.4.0 — Client Intake Legal Position & Draft Link

Scope: client intake/lifecycle only. No SAL, evidence admission, tempus, positive-law gate, retrieval, Case Analysis reasoning, or exporter semantics changed.

## Implemented
- Added mandatory client address/domicile field to Client Intake.
- Added legal-position selector: Tersangka, Terdakwa, Penggugat, Tergugat, plus unclassified/other.
- Added a direct *draft starter* control driven by legal position:
  - Tersangka → Permohonan Praperadilan (starter; stage must be verified).
  - Terdakwa → Eksepsi Pidana (starter; can be changed to Pledoi when procedurally appropriate).
  - Penggugat → Gugatan Perdata.
  - Tergugat → Jawaban Tergugat.
- Draft starter never auto-generates/finalizes a document. It only opens the selected Draft template and carries client name, address, matter, and legal position.
- Representation Request → Surat Kuasa Khusus remains the authority path and now carries address + legal position into the draft context.
- Client communication persistence now stores `client_address` and `legal_position`; schema version advanced idempotently to 11.
- Consultation communication can surface the recorded address/legal position while preserving the warning that consultation is not itself a power of attorney.

## Boundary
Legal position is intake metadata, not a legal conclusion. Draft mapping is a workflow shortcut, not an assertion that the selected document is procedurally proper. Professional verification remains mandatory.

## Validation
- Python compile: PASS.
- JavaScript syntax (3 script blocks): PASS.
- Targeted lifecycle/intake regression: 10 PASS.
- Structural release audit: PASS.
- Full non-smoke suite traversed all tests without a displayed failure, but the container runner did not terminate cleanly before timeout; therefore not recorded as a clean full-suite PASS.
