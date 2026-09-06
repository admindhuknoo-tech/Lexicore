@echo off
setlocal

echo [1/5] Python compile check...
py -m compileall -q .
if errorlevel 1 exit /b 1

echo [2/5] Structural release audit...
py tools\release_audit.py
if errorlevel 1 exit /b 1

echo [3/5] Embedded OCR readiness...
call ocr_check.bat
if errorlevel 1 exit /b 1

echo [4/5] Smoke/regression tests...
py -m pytest tests -q
if errorlevel 1 exit /b 1

echo [5/5] Schema/runtime gate complete.
echo.
echo LexiCore release gate: PASS
endlocal
