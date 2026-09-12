"""Generate an Ed25519 keypair for the LexiCore license server."""
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

private = Ed25519PrivateKey.generate()
private_pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
public_pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
Path('license_private_key.pem').write_bytes(private_pem)
Path('license_public_key.pem').write_bytes(public_pem)
print('Generated license_private_key.pem (SERVER ONLY) and license_public_key.pem (DESKTOP BUILD).')
