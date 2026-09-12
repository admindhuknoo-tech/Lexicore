from __future__ import annotations

import csv
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from license_admin.gui import PLAN_OPTIONS, create_license_for_customer, safe_customer_slug
from license_admin.issue_license import PREFIX


def _make_key(authority: Path) -> None:
    authority.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    (authority / 'license_private_key.pem').write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


def test_plan_contract_is_bounded():
    assert PLAN_OPTIONS['Trial 30 Hari'] == ('desktop-trial-30d', 30)
    assert PLAN_OPTIONS['Desktop Tahunan (365 Hari)'] == ('desktop-annual', 365)
    assert PLAN_OPTIONS['Desktop Perpetual'] == ('desktop-perpetual', 0)


def test_safe_customer_slug():
    assert safe_customer_slug('Firma Hukum A/B') == 'Firma-Hukum-A-B'
    assert safe_customer_slug('   ') == 'customer'


def test_gui_service_issues_license_and_appends_ledger(tmp_path: Path):
    authority = tmp_path / 'authority'
    _make_key(authority)
    installation_id = PREFIX + ('a' * 64)
    result = create_license_for_customer(
        authority_dir=authority,
        customer_name='Firma Hukum Nusantara',
        contact='admin@example.test',
        installation_id=installation_id,
        plan_label='Trial 30 Hari',
    )
    out = Path(result['output'])
    assert out.is_file()
    assert result['license_id'] in out.name
    envelope = json.loads(out.read_text(encoding='utf-8'))
    assert envelope['payload']['device_fingerprint_hash'] == 'a' * 64
    assert envelope['payload']['plan'] == 'desktop-trial-30d'
    assert envelope['payload']['expires_at']

    ledger = authority / 'license_ledger.csv'
    rows = list(csv.DictReader(ledger.open(encoding='utf-8-sig')))
    assert len(rows) == 1
    assert rows[0]['license_id'] == result['license_id']
    assert rows[0]['customer_name'] == 'Firma Hukum Nusantara'
    assert rows[0]['installation_id'] == installation_id
    text = ledger.read_text(encoding='utf-8-sig')
    assert 'PRIVATE KEY' not in text.upper()
    assert 'BEGIN PRIVATE KEY' not in text


def test_missing_private_key_fails_closed(tmp_path: Path):
    installation_id = PREFIX + ('b' * 64)
    try:
        create_license_for_customer(
            authority_dir=tmp_path / 'authority',
            customer_name='Customer',
            contact='',
            installation_id=installation_id,
            plan_label='Desktop Perpetual',
        )
    except FileNotFoundError as exc:
        assert 'license_private_key.pem' in str(exc)
    else:
        raise AssertionError('missing private key must fail closed')
