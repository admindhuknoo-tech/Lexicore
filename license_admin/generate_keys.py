"""Generate LexiCore offline desktop Ed25519 licensing keys.

Run this only on the administrator/licensing workstation. Keep the private key
outside the desktop project and installer. Copy only the public key into the
LexiCore build root as license_public_key.pem.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', required=True, help='Private administrator-only directory')
    args = parser.parse_args()
    out = Path(args.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    priv_path = out / 'license_private_key.pem'
    pub_path = out / 'license_public_key.pem'
    if priv_path.exists() or pub_path.exists():
        raise SystemExit('Refusing to overwrite an existing licensing keypair.')
    private = Ed25519PrivateKey.generate()
    priv_path.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    pub_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    try:
        priv_path.chmod(0o600)
    except Exception:
        pass
    print(f'PRIVATE (ADMIN ONLY): {priv_path}')
    print(f'PUBLIC (COPY TO DESKTOP BUILD): {pub_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
