# LexiCore Desktop — Standalone Commercial Deployment

LexiCore Desktop is a local/standalone application. The commercial build does not require a runtime license server.
The existing paid-license activation gate remains fail-closed, but activation is now local/offline through a signed device-bound license file. See `LICENSE_DEPLOYMENT.md` for the canonical licensing procedure.

## License model

- 1 signed license = 1 device fingerprint.
- Device fingerprint uses stable machine identifiers and only the SHA-256 hash is stored in the license.
- The installer contains only `license_public_key.pem`.
- `license_private_key.pem` remains on the administrator/licensing workstation and must never be copied into the project, installer, or customer machine.
- The customer copies the Installation ID from the first-run activation screen and receives a signed `.lic`/JSON license file.
- The license file is verified locally with Ed25519 and is rejected on another device with `DEVICE_MISMATCH`.
- No activation server, periodic revalidation, or internet connection is required.

## Administrator key generation

```bat
py license_admin\generate_keys.py --out-dir C:\LexiCore-License-Authority
```

Copy only:

```text
C:\LexiCore-License-Authority\license_public_key.pem
```

to the LexiCore project root before building.

## Issue a customer license

The customer provides the Installation ID displayed by LexiCore. Then issue:

```bat
py license_admin\issue_license.py ^
  --private-key C:\LexiCore-License-Authority\license_private_key.pem ^
  --installation-id LEXICORE-DEVICE-V1-<64hex> ^
  --output C:\LexiCore-License-Authority\issued\customer.lic
```

For a time-limited license, add `--expires-days N`. Omit it for a perpetual device-bound license.

## Build

```bat
build_desktop.bat
```

The build intentionally fails if `license_public_key.pem` is absent.
