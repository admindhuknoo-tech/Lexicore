"""Issue signed offline LexiCore Desktop licenses for exactly one device.

The module exposes :func:`issue_license_file` for the administrator GUI while
retaining the original command-line interface.
"""
from __future__ import annotations

import argparse
import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRODUCT = 'LexiCore'
PREFIX = 'LEXICORE-DEVICE-V1-'


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def fp_from_installation_id(value: str) -> str:
    value = (value or '').strip()
    if value.upper().startswith(PREFIX):
        value = value[len(PREFIX):]
    value = value.lower()
    if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('INVALID_INSTALLATION_ID')
    return value


def issue_license_file(
    *,
    private_key: str | Path,
    installation_id: str,
    output: str | Path,
    license_id: str = '',
    plan: str = 'desktop-perpetual',
    expires_days: int = 0,
) -> dict:
    """Create one device-bound signed license and return its payload metadata.

    The output path is never overwritten. ``expires_days=0`` means perpetual.
    """
    fp = fp_from_installation_id(installation_id)
    raw = Path(private_key).expanduser().read_bytes()
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError('LICENSE_PRIVATE_KEY_NOT_ED25519')
    if expires_days < 0:
        raise ValueError('INVALID_EXPIRES_DAYS')

    now = datetime.now(timezone.utc)
    resolved_license_id = (license_id or ('LC-' + secrets.token_hex(8).upper())).strip()
    payload = {
        'product': PRODUCT,
        'license_id': resolved_license_id,
        'plan': plan,
        'status': 'ACTIVE',
        'device_fingerprint_hash': fp,
        'issued_at': iso(now),
        'expires_at': iso(now + timedelta(days=expires_days)) if expires_days > 0 else '',
        'license_model': 'OFFLINE_DEVICE_LOCK_V1',
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')
    envelope = {
        'payload': payload,
        'signature': base64.b64encode(key.sign(canonical)).decode('ascii'),
    }
    out = Path(output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise FileExistsError('Refusing to overwrite an existing license file.')
    out.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding='utf-8')
    return {
        'license_id': resolved_license_id,
        'installation_id': PREFIX + fp,
        'output': str(out),
        'payload': payload,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--private-key', required=True)
    p.add_argument('--installation-id', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--license-id', default='')
    p.add_argument('--plan', default='desktop-perpetual')
    p.add_argument('--expires-days', type=int, default=0, help='0 = perpetual')
    a = p.parse_args()
    try:
        result = issue_license_file(
            private_key=a.private_key,
            installation_id=a.installation_id,
            output=a.output,
            license_id=a.license_id,
            plan=a.plan,
            expires_days=a.expires_days,
        )
    except (ValueError, FileExistsError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"license_id={result['license_id']}")
    print(f"device={result['installation_id']}")
    print(f"output={result['output']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
