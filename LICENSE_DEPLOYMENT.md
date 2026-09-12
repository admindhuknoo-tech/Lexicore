# LexiCore Desktop — Offline Device-Locked License v1.4.10

This layer is outside the frozen legal-reasoning core. It only controls access to the local desktop API.

## Commercial flow

1. Generate an Ed25519 keypair on an administrator-only workstation with `license_admin/generate_keys.py`.
2. Keep `license_private_key.pem` outside the project and installer.
3. Copy only `license_public_key.pem` into the LexiCore desktop build root.
4. Build with `build_desktop.bat`; the build fails if the public key is missing.
5. First launch shows an Installation ID derived from the local SHA-256 device fingerprint.
6. The customer sends that Installation ID to the license authority.
7. Issue a signed `.lic`/JSON envelope with `license_admin/issue_license.py` for exactly that Installation ID.
8. The customer imports the file. LexiCore verifies Ed25519 signature, product, ACTIVE status, optional expiry, and exact device fingerprint locally.
9. After successful verification, `license.json` is stored under the LexiCore local data directory.

No runtime activation server, internet connection, periodic revalidation, or offline grace is required by Desktop.

## 1 license = 1 device

The license payload contains only the SHA-256 device fingerprint hash, never raw MachineGuid/BIOS values. Copying the signed license to another device fails closed with `DEVICE_MISMATCH`.

Reinstall on the same physical device is permitted when the stable fingerprint remains unchanged. A license issued for one device is not transferable to another device by editing the file because any modification invalidates the Ed25519 signature.

## Optional expiry

The default issuer creates a perpetual device-bound license. Use `--expires-days N` when a time-limited desktop license is desired. Expiry is signed and verified locally.

## Security boundary

- Desktop: `license_public_key.pem` only.
- License authority: `license_private_key.pem` only on the administrator workstation.
- Private key must never enter the project root, release archive, installer, or customer machine.
- The commercial desktop API remains fail-closed until a valid local signed license is present.

## Web Apps

Web Apps authentication/subscription is a separate online deployment target and does not change this standalone Desktop license model.
