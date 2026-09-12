# LexiCore v2.3.1 — Final Candidate Law Governor Lock

Date: 2026-09-10
Scope: Candidate-Law Retrieval / SSoT admission only.

## Reproduced failure
A materially irrelevant KPK internal personnel regulation reached the Canonical Legal Reasoning Chain in a corruption + BPR/BUMD matter:

`Perubahan Atas Peraturan Komisi Pemberantasan Korupsi Nomor 10 Tahun 2010 Tentang Tata Cara Penilaian Kinerja Individu Penasihat dan Pegawai`

## Root cause
The retrieval router correctly had an institutional hard-drop rule, but enforcement was not end-to-end:

1. Initial search rows were weighted in `services/regulatory_retrieval.py`.
2. Later exact-verification/reconstruction paths could add or reconstruct rows after the first filter.
3. `services/sal_source_of_truth._law_rows()` rebuilt `case_regulatory_snapshot.official_results` but discarded `law_weight_policy`, `candidate_law_eligible`, `query_origin`, and candidate-role metadata.
4. The SSoT compatibility check then saw the word `korupsi` in the KPK institution title and treated that as a broad corruption-family overlap.
5. The row could therefore enter `candidate_law_pool` and be selected by the canonical chain despite being internal institutional governance unrelated to the BPR/BUMD merits.

## Final lock
Two independent locks are now enforced.

### Lock A — post-merge retrieval lock
After exact-case verification rows are merged, every result is evaluated again by the frozen law-weight policy before positive-law verification.

- Non-exact rejected rows are dropped.
- Exact case citations can remain for identity/provision audit.
- Any hard institutional mismatch receives `candidate_law_eligible = false` and may not enter Candidate Law.

### Lock B — SSoT Candidate Law governor
`sal_source_of_truth` now preserves retrieval-policy metadata from official results and re-evaluates a final institutional-mismatch guard if historical/reconstructed rows arrive without it.

`candidate_law_eligible = false` and hard institutional mismatch are authoritative rejection conditions for the Candidate Law pool.

Exact citations may still exist in the regulatory snapshot for audit; that does not make them governing-law candidates.

## Invariants preserved
- Retrieval cannot mark a norm applicable.
- Retrieval cannot override tempus.
- Positive-law verifier retains identity/status/provision authority.
- SAL semantic contract is unchanged.
- Evidence and element engines are unchanged.
- Exact case citations are still auditable.
- Internal institutional mismatch cannot become governing-law material through a broad keyword overlap.

## Validation
- New final-lock regression tests: 3 passed.
- Retrieval/backlog targeted suite: 17 passed.
- Full non-smoke regression: 383 passed.
- Python compile: PASS.
- Smoke suite was not runnable in this container because Flask is not installed; no smoke PASS is claimed here.
