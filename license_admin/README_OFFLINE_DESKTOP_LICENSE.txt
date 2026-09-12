LexiCore Desktop Offline Device-Locked License

ADMIN GUI (recommended)
1. Generate production keypair once on an administrator-only workstation:
   py license_admin\generate_keys.py --out-dir C:\LexiCore-License-Authority

2. Copy ONLY license_public_key.pem into the LexiCore project root before build.
   Never copy license_private_key.pem into the project or installer.

3. Run the administrator GUI:
   run_license_authority.bat

4. Customer installs LexiCore and sends the Installation ID shown on first run.

5. In LexiCore License Authority, enter:
   - customer/user/firm name
   - email or WhatsApp
   - Installation ID
   - plan: Trial 30 Days / Annual 365 Days / Perpetual
   Click GENERATE LICENSE.

6. The signed .lic file is written under:
   C:\LexiCore-License-Authority\issued\
   The issuance ledger is stored at:
   C:\LexiCore-License-Authority\license_ledger.csv

7. Send only the generated .lic file to the customer. The customer imports it
   through the Offline Activation screen.

CLI FALLBACK
py license_admin\issue_license.py --private-key C:\LexiCore-License-Authority\license_private_key.pem --installation-id LEXICORE-DEVICE-V1-<64hex> --output C:\LexiCore-License-Authority\issued\customer.lic

Security rules:
- A license is valid only for the Installation ID/device fingerprint it was issued for.
- Reinstalling LexiCore on the same physical device remains allowed if its stable fingerprint is unchanged.
- license_private_key.pem is ADMIN ONLY and must never be placed in the project, desktop build, installer, or customer files.
- LexiCore Desktop requires no license server and no internet after license issuance.
