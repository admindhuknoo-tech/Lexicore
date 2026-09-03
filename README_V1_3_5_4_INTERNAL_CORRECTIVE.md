# LexiCore v1.3.5.4 — Internal Corrective

This corrective stays on version **1.3.5.4**. It does not create another micro-version.

## Scope

1. Gemini REST transport hardened:
   - API key moved to `x-goog-api-key` header.
   - request pacing added to reduce burst/rate-limit failures.
   - retry policy is selective for 408/409/429/5xx.
   - HTTP failures are classified by status instead of generic `HTTP_ERROR`.
   - structured-output 400 responses get one plain JSON-prompt retry.
   - provider HTTP detail is retained in diagnostics without exposing the API key.
2. Case PDF/DOCX pipeline diagnostics now surface the first sanitized AI failure detail.
3. BPR executive summary rejects common OCR/BAP pass-through noise and prefers a source-grounded factual capsule.
4. Case export re-applies active-domain filtering so incidental BW/other seed regulations cannot leak back into a BPR/Tipikor report.
5. Action Plan deduplication is issue-based so the same evidentiary gap does not appear twice at different priorities.
6. Regression coverage added for HTTP classification, BPR regulatory pruning, executive-summary noise, and semantic action-plan deduplication.

## Database

No schema change. `schema_version` remains **3**.

## Release gate

Run:

```bat
release_check.bat
```

Expected after this corrective: all tests pass. With the added tests the suite should report **45 passed** in the current baseline.

Then rerun the BAP benchmark. For Full-Document AI, inspect the exported metadata:

- `segments_total > 0`
- ideally `segments_read > 0`
- if not, `AI Pipeline` must now show a specific category such as `HTTP_429_RATE_LIMIT`, `HTTP_403_AUTH_OR_PERMISSION`, `HTTP_400_BAD_REQUEST`, or `HTTP_5xx_UPSTREAM`, plus a sanitized failure detail.
