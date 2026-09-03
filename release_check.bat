@echo off
setlocal

echo [1/3] Python compile check...
py -m compileall -q .
if errorlevel 1 exit /b 1

echo [2/3] Smoke/regression tests...
py -m pytest tests -q
if errorlevel 1 exit /b 1

echo [3/3] Schema/runtime gate complete.
echo.
echo LexiCore release gate: PASS
endlocal
