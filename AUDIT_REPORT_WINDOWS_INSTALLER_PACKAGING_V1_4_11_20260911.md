# LexiCore v1.4.11 — Windows Installer Packaging

Scope: packaging/build pipeline only. No SAL, evidence, tempus, positive-law verification, Candidate Law Governor, canonical reasoning, persistence, exporter semantics, or offline device-lock semantics are changed.

## Changes
- Adds an Inno Setup 6 installer definition for the existing `dist\\LexiCore` PyInstaller onedir bundle.
- Adds `build_installer.bat` with fail-closed checks for the built executable and bundled `license_public_key.pem`.
- Creates Start Menu shortcut and optional Desktop shortcut.
- Installs application binaries under Program Files; writable LexiCore runtime data remains outside the install directory through the existing desktop launcher.
- Corrects `build_desktop.bat` so `pytest` is installed before the mandatory non-smoke regression gate.

## Expected flow
1. `build_desktop.bat`
2. `build_installer.bat`
3. output: `dist\\installer\\LexiCore-Desktop-Setup-v1.4.11.exe`

The production private signing key is never packaged.
