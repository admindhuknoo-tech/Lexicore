@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python launcher ^(py^) tidak ditemukan.
  exit /b 1
)

py -c "import cryptography, tkinter" >nul 2>&1
if errorlevel 1 (
  echo ERROR: dependency admin license belum tersedia.
  echo Jalankan: py -m pip install cryptography
  exit /b 1
)

py license_admin\gui.py
endlocal
