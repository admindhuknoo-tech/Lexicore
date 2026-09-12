# LexiCore v1.5.8 — Case Domain Classifier Stabilization

Changed production file: `services/case_domain_classifier.py`.

Key invariants:
- substantive merits domain remains PRIMARY;
- civil procedure is preserved as a secondary lane when pleading anchors exist;
- religious-court vocabulary is treated as a forum lane when an inheritance merits domain is visible;
- material criminal damage can coexist as a secondary issue without falsely converting the whole matter into a criminal proceeding;
- inheritance + land/property signals are preserved independently;
- generic inheritance vocabulary remains fail-closed as GENERAL_LEGAL until specific doctrine/relationship/posture evidence exists.

Targeted regression executed in the patch workspace: 5 passed.
