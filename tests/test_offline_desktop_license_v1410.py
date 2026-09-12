from pathlib import Path


def test_desktop_licensing_has_no_runtime_server_dependency():
    text = Path('licensing.py').read_text(encoding='utf-8')
    forbidden = ['urllib.request', 'LEXICORE_LICENSE_SERVER_URL', '/v1/activate', '/v1/validate', '/v1/deactivate', 'OFFLINE_GRACE_EXPIRED']
    for token in forbidden:
        assert token not in text


def test_desktop_ui_describes_standalone_offline_activation():
    text = Path('static/index.html').read_text(encoding='utf-8')
    assert 'Aktivasi Offline LexiCore Desktop' in text
    assert 'LexiCore Desktop berjalan standalone' in text
    assert 'Installation ID' in text
    assert 'Impor & Aktifkan' in text


def test_admin_private_key_tools_are_not_added_to_pyinstaller_datas():
    spec = Path('LexiCoreDesktop.spec').read_text(encoding='utf-8')
    assert 'license_admin' not in spec
    assert 'license_private_key.pem' not in spec


def test_build_still_fails_without_public_verification_key():
    build = Path('build_desktop.bat').read_text(encoding='utf-8')
    assert 'if not exist license_public_key.pem' in build
    assert 'exit /b 1' in build
