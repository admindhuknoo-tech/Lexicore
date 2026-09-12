from pathlib import Path

import tools.build_release as br


def _p(tmp_path: Path, rel: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('x', encoding='utf-8')
    return p


def test_sensitive_and_runtime_artifacts_are_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(br, 'ROOT', tmp_path)
    blocked = [
        '.env',
        '.git/config',
        'backups/user.zip',
        'uploads/evidence.pdf',
        'instance/runtime.dat',
        'lexicore.db',
        'runtime.sqlite3',
        'desktop.log',
        'license_private_key.pem',
        'server-signing.key',
        'certificate.p12',
        'certificate.pfx',
        'nested/private_key.pem',
        'BUILD_MANIFEST.json',
        'PACKAGE_SHA256SUMS.txt',
        'LEXICORE_PATCH_OLD/file.py',
        'LEXICORE_ROLLBACK_OLD/file.py',
    ]
    for rel in blocked:
        assert br.include(_p(tmp_path, rel)) is False, rel


def test_public_key_and_env_template_remain_distributable(tmp_path, monkeypatch):
    monkeypatch.setattr(br, 'ROOT', tmp_path)
    allowed = [
        '.env.example',
        'license_public_key.pem',
        'app.py',
        'license_server/server.py',
    ]
    for rel in allowed:
        assert br.include(_p(tmp_path, rel)) is True, rel


def test_manifest_source_is_not_a_release_record():
    assert 'BUILD_MANIFEST.json' in br.EXCLUDE_FILES
    assert br.ARTIFACT_HYGIENE_REVISION == 'v1.4.9'


def test_release_audit_ignores_local_virtual_environments():
    audit_text = (Path(__file__).resolve().parents[1] / 'tools' / 'release_audit.py').read_text(encoding='utf-8')
    assert "'.venv-release'" in audit_text
    assert "part.startswith('.venv')" in audit_text
    assert '_audit_path_excluded(p)' in audit_text
