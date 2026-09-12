import os
from pathlib import Path


def test_desktop_launcher_uses_loopback_and_external_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv('LEXICORE_DATA_DIR', str(tmp_path / 'LexiCoreData'))
    for key in ('LEXICORE_DB_PATH','LEXICORE_BACKUP_DIR','LEXICORE_UPLOAD_DIR','LEXICORE_EXPORT_DIR','LEXICORE_HOST','LEXICORE_DEBUG'):
        monkeypatch.delenv(key, raising=False)
    import desktop_launcher as dl
    root = dl.configure_runtime_environment()
    assert root == (tmp_path / 'LexiCoreData').resolve()
    assert os.environ['LEXICORE_HOST'] == '127.0.0.1'
    assert os.environ['LEXICORE_DEBUG'] == '0'
    assert Path(os.environ['LEXICORE_DB_PATH']).parent == root
    assert Path(os.environ['LEXICORE_UPLOAD_DIR']).parent == root
    assert Path(os.environ['LEXICORE_BACKUP_DIR']).parent == root


def test_app_upload_folder_accepts_external_runtime_dir():
    text = Path('app.py').read_text(encoding='utf-8')
    assert "LEXICORE_UPLOAD_DIR" in text
    assert "LEXICORE_DATA_DIR" in text


def test_desktop_build_assets_exist_and_use_waitress():
    launcher = Path('desktop_launcher.py').read_text(encoding='utf-8')
    req = Path('requirements-desktop.txt').read_text(encoding='utf-8')
    spec = Path('LexiCoreDesktop.spec').read_text(encoding='utf-8')
    assert 'from waitress import serve' in launcher
    assert '127.0.0.1' in launcher
    assert 'waitress' in req.lower()
    assert "['desktop_launcher.py']" in spec
    assert "name='LexiCore'" in spec


def test_desktop_deployment_hands_off_to_license_gate():
    doc = Path('DEPLOYMENT_DESKTOP.md').read_text(encoding='utf-8')
    assert 'paid-license activation gate' in doc
    assert 'LICENSE_DEPLOYMENT.md' in doc
