"""Build a clean LexiCore full-project release archive using stdlib only."""
from __future__ import annotations
import hashlib, json, shutil, sys, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import release_metadata, PRODUCT_NAME, LEXICORE_VERSION

# v1.4.9 commercial release artifact hygiene.
# Keep this boundary conservative: generated/local state and secrets must never
# become part of the distributable project archive. Public verification material
# such as license_public_key.pem remains explicitly allowed.
ARTIFACT_HYGIENE_REVISION = "v1.4.9"
EXCLUDE_DIRS = {
    '.git', '.pytest_cache', '__pycache__', 'backups', 'dist', '.venv', 'venv',
    'uploads', 'instance',
}
EXCLUDE_PREFIXES = ('LEXICORE_PATCH_', 'LEXICORE_ROLLBACK_')
EXCLUDE_SUFFIXES = ('.pyc', '.pyo', '.log', '.sqlite', '.sqlite3', '.db')
EXCLUDE_FILES = {
    '.env',
    'BUILD_MANIFEST.json',
    'PACKAGE_SHA256SUMS.txt',
    'license_private_key.pem',
}
PRIVATE_KEY_SUFFIXES = ('.key', '.p12', '.pfx')
PRIVATE_KEY_NAME_MARKERS = ('private_key', 'private-key', 'signing_key', 'signing-key')


def _looks_like_private_key(path: Path) -> bool:
    name = path.name.lower()
    if name == 'license_public_key.pem':
        return False
    if name.endswith(PRIVATE_KEY_SUFFIXES):
        return True
    return name.endswith('.pem') and any(marker in name for marker in PRIVATE_KEY_NAME_MARKERS)


def include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS or part.startswith(EXCLUDE_PREFIXES) for part in rel.parts):
        return False
    if path.name in EXCLUDE_FILES or path.name.endswith(EXCLUDE_SUFFIXES):
        return False
    if _looks_like_private_key(path):
        return False
    return path.is_file()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    safe_ver = LEXICORE_VERSION.replace('+', '_')
    out = dist / f'{PRODUCT_NAME}_{safe_ver}_FULL_PROJECT.zip'

    with tempfile.TemporaryDirectory(prefix='lexicore-release-') as td:
        stage = Path(td) / f'{PRODUCT_NAME}_{safe_ver}'
        stage.mkdir(parents=True)
        records = []
        for src in sorted(ROOT.rglob('*')):
            if not include(src):
                continue
            rel = src.relative_to(ROOT)
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            records.append({'path': rel.as_posix(), 'sha256': sha256(dst), 'bytes': dst.stat().st_size})

        # BUILD_MANIFEST.json is intentionally not listed as its own hashed file:
        # a manifest cannot contain a stable hash of its final serialized self.
        # The source-tree manifest is excluded above and this fresh manifest is
        # generated only after all distributable records are finalized.
        manifest = {
            'release': release_metadata(),
            'artifact_hygiene_revision': ARTIFACT_HYGIENE_REVISION,
            'built_at_utc': datetime.now(timezone.utc).isoformat(),
            'file_count': len(records),
            'manifest_self_entry': False,
            'files': records,
        }
        (stage / 'BUILD_MANIFEST.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8'
        )

        if out.exists():
            out.unlink()
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(stage.rglob('*')):
                if p.is_file():
                    z.write(p, p.relative_to(stage.parent))

    print(out)
    print('sha256=' + sha256(out))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
