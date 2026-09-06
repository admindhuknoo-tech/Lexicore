"""Remove known regression/test artifacts from a LexiCore working tree.

Safe by construction: only known historical duplicate paths under exporters/
and test_lexicore_* files under backups/ are removed. Real user backups and
future legitimate exporter modules are not matched.
"""
from __future__ import annotations
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXPORTERS = ROOT / "exporters"
BACKUPS = ROOT / "backups"

KNOWN_EXPORTER_DEBRIS = (
    "app.py", "database.py", "version.py",
    "README.md", "README_V1_3_13_4.md", "AUDIT_REPORT_V1_3_13_4.md",
    "static", "services", "tests", "tools", "__pycache__",
)

removed = []
for rel in KNOWN_EXPORTER_DEBRIS:
    path = EXPORTERS / rel
    if not path.exists():
        continue
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(str(path.relative_to(ROOT)))

if BACKUPS.exists():
    for path in BACKUPS.glob("test_lexicore_*"):
        if path.is_file():
            path.unlink()
            removed.append(str(path.relative_to(ROOT)))

print(f"Artifact hygiene cleanup PASS | removed={len(removed)}")
for item in removed:
    print(f" - {item}")
