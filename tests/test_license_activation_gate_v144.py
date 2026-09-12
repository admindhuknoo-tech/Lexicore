import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import licensing


def _iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')


def _keys():
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public_pem


def _envelope(private, *, fp='f'*64, now=None, expires_days=0, status='ACTIVE'):
    now = now or datetime(2026, 9, 11, tzinfo=timezone.utc)
    payload = {
        'product': 'LexiCore', 'license_id': 'LC-TEST', 'plan': 'desktop-perpetual', 'status': status,
        'device_fingerprint_hash': fp, 'issued_at': _iso(now),
        'expires_at': _iso(now + timedelta(days=expires_days)) if expires_days else '',
        'license_model': 'OFFLINE_DEVICE_LOCK_V1',
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return {'payload': payload, 'signature': base64.b64encode(private.sign(raw)).decode('ascii')}


def test_signed_license_verifies_and_rejects_tamper():
    private, public = _keys()
    env = _envelope(private)
    assert licensing.verify_signed_envelope(env, public)['license_id'] == 'LC-TEST'
    env['payload']['plan'] = 'tampered'
    try:
        licensing.verify_signed_envelope(env, public)
    except ValueError as exc:
        assert 'INVALID_LICENSE_SIGNATURE' in str(exc)
    else:
        raise AssertionError('tampered signed license was accepted')


def test_offline_license_is_bound_to_exact_device_hash(tmp_path):
    private, public = _keys()
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    env = _envelope(private, now=now)
    ok = licensing.LicenseManager(data_dir=tmp_path, public_key_pem=public, now=lambda: now, fingerprint=lambda: 'f'*64)
    assert ok.install_license(env).allowed is True
    other = licensing.LicenseManager(data_dir=tmp_path, public_key_pem=public, now=lambda: now, fingerprint=lambda: 'a'*64)
    blocked = other.local_status()
    assert blocked.allowed is False
    assert blocked.message == 'DEVICE_MISMATCH'


def test_installation_id_contains_only_device_hash():
    iid = licensing.installation_id('a'*64)
    assert iid == 'LEXICORE-DEVICE-V1-' + ('a'*64)
    assert licensing.installation_id_to_fingerprint(iid) == 'a'*64


def test_perpetual_offline_license_has_no_revalidation_or_grace_requirement(tmp_path):
    private, public = _keys()
    issued = datetime(2026, 9, 1, tzinfo=timezone.utc)
    env = _envelope(private, now=issued, expires_days=0)
    mgr = licensing.LicenseManager(data_dir=tmp_path, public_key_pem=public, now=lambda: issued+timedelta(days=5000), fingerprint=lambda: 'f'*64)
    assert mgr.install_license(env).allowed is True
    state = mgr.local_status()
    assert state.allowed is True
    assert state.status == 'ACTIVE'
    assert state.message == 'LICENSE_ACTIVE_OFFLINE'


def test_optional_expiry_fails_closed(tmp_path):
    private, public = _keys()
    issued = datetime(2026, 9, 1, tzinfo=timezone.utc)
    env = _envelope(private, now=issued, expires_days=30)
    mgr = licensing.LicenseManager(data_dir=tmp_path, public_key_pem=public, now=lambda: issued, fingerprint=lambda: 'f'*64)
    assert mgr.install_license(env).allowed is True
    expired = licensing.LicenseManager(data_dir=tmp_path, public_key_pem=public, now=lambda: issued+timedelta(days=31), fingerprint=lambda: 'f'*64)
    state = expired.local_status()
    assert state.allowed is False
    assert state.message == 'LICENSE_EXPIRED'


def test_wrong_device_license_is_not_persisted(tmp_path):
    private, public = _keys()
    env = _envelope(private, fp='a'*64)
    mgr = licensing.LicenseManager(data_dir=tmp_path, public_key_pem=public, fingerprint=lambda: 'b'*64)
    state = mgr.install_license(env)
    assert state.allowed is False
    assert state.message == 'DEVICE_MISMATCH'
    assert not (tmp_path/'license.json').exists()


def test_pytest_bootstrap_keeps_license_gate_disabled_by_default():
    assert __import__('os').environ.get('LEXICORE_LICENSE_REQUIRED') == '0'


def test_desktop_launcher_enables_commercial_license_gate(monkeypatch, tmp_path):
    monkeypatch.setenv('LEXICORE_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('LEXICORE_LICENSE_REQUIRED', raising=False)
    import desktop_launcher
    desktop_launcher.configure_runtime_environment()
    assert __import__('os').environ['LEXICORE_LICENSE_REQUIRED'] == '1'


def test_license_gate_test_default_is_restored_after_desktop_launcher():
    assert __import__('os').environ.get('LEXICORE_LICENSE_REQUIRED') == '0'


def test_app_has_fail_closed_offline_license_api_gate():
    text = Path('app.py').read_text(encoding='utf-8')
    assert 'def commercial_license_gate' in text
    assert "'/api/license/status'" in text
    assert "'/api/license/install'" in text
    assert "'/api/license/remove'" in text
    assert "'/api/license/activate'" not in text
    assert "'/api/license/revalidate'" not in text
    assert "error='LICENSE_REQUIRED'" in text


def test_offline_activation_ui_precedes_profile_onboarding():
    html = Path('static/index.html').read_text(encoding='utf-8')
    assert 'id="licenseModal"' in html
    assert 'id="licenseInstallationId"' in html
    assert 'id="licenseFileInput"' in html
    assert 'installDesktopLicense()' in html
    assert 'licenseActivationToken' not in html
    assert 'revalidateDesktopLicense' not in html
    assert 'if(allowed)await loadProfile()' in html
    assert "window.addEventListener('DOMContentLoaded',()=>{loadDesktopLicense();" in html


def test_build_requires_only_public_key_and_admin_issuer_is_not_desktop_runtime():
    build = Path('build_desktop.bat').read_text(encoding='utf-8')
    spec = Path('LexiCoreDesktop.spec').read_text(encoding='utf-8')
    issuer = Path('license_admin/issue_license.py').read_text(encoding='utf-8')
    assert 'license_public_key.pem' in build
    assert 'license_public_key.pem' in spec
    assert 'PRIVATE_KEY' not in spec
    assert 'Ed25519PrivateKey' in issuer
    assert 'OFFLINE_DEVICE_LOCK_V1' in issuer
