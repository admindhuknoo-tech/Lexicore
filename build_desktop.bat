@echo off
setlocal
cd /d %~dp0

if not exist license_public_key.pem (
  echo ERROR: license_public_key.pem belum tersedia. Generate production keypair pada License Authority, lalu copy HANYA public key ke root build LexiCore.
  exit /b 1
)

echo [1/5] Creating desktop build environment...
if not exist .venv-desktop py -3 -m venv .venv-desktop
call .venv-desktop\Scripts\activate.bat
if errorlevel 1 exit /b 1

echo [2/5] Installing desktop and build-test dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
python -m pip install pytest
if errorlevel 1 exit /b 1

echo [3/5] Running structural release audit...
python tools\release_audit.py
if errorlevel 1 exit /b 1

echo [4/5] Running non-smoke regression suite...
python -m pytest -q --ignore=tests\test_smoke.py
if errorlevel 1 exit /b 1

echo [5/5] Building Windows onedir package...
if exist build rmdir /s /q build
if exist dist\LexiCore rmdir /s /q dist\LexiCore
pyinstaller --noconfirm LexiCoreDesktop.spec
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\LexiCore\LexiCore.exe
endlocal
