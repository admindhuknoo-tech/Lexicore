@echo off
setlocal
cd /d %~dp0

if not exist dist\LexiCore\LexiCore.exe (
  echo ERROR: dist\LexiCore\LexiCore.exe belum ada.
  echo Jalankan build_desktop.bat terlebih dahulu.
  exit /b 1
)

if not exist dist\LexiCore\license_public_key.pem (
  echo ERROR: dist\LexiCore\license_public_key.pem tidak ditemukan.
  echo Build komersial harus membawa public verification key.
  exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
  echo ERROR: Inno Setup 6 belum ditemukan.
  echo Install Inno Setup 6, lalu jalankan build_installer.bat kembali.
  exit /b 1
)

if not exist dist\installer mkdir dist\installer

echo Building LexiCore Windows installer...
"%ISCC%" installer\LexiCore.iss
if errorlevel 1 exit /b 1

echo.
echo Installer complete: dist\installer\LexiCore-Desktop-Setup-v1.4.13.exe
endlocal
