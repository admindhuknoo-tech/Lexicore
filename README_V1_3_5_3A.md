# LexiCore v1.3.5.3a — Tempus Export Regression Corrective

Corrective patch for the v1.3.5.3 release-gate failure in `Regulasi & Tempus`.

- Uses exact `event_date_candidate` when available.
- Same-year regulation with only `event_year_candidate` is **not** falsely excluded; it is labeled `TEMPUS_REQUIRES_EXACT_DATE`.
- A regulation effective after an exact material event date is labeled `POST_TEMPUS_EXCLUDED`.
- Regression fixture now models the BAP benchmark material date `2022-09-27`.
- Adds a guard test preventing false same-year exclusion when the exact event date is unknown.
- No database/schema migration.
