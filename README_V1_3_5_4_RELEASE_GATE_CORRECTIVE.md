# LexiCore v1.3.5.4 — Release Gate Corrective

Corrects the hard-domain regulatory seed gate without changing the release version or database schema.

## Fix
`civil_contract` matching now recognizes formal KUHPerdata titles such as `Kitab Undang-Undang Hukum Perdata`, `Hukum Perdata`, and `BW`, in addition to `KUHPerdata`, `Burgerlijk`, `Perikatan`, etc.

This fixes the regression where a valid KUHPerdata seed was removed together with unrelated POJK and employment regulations for a civil/land case.

## Expected release gate
Run:

    release_check.bat

Expected: all tests PASS.
