@echo off
setlocal
cd /d "%~dp0"
if not exist tools\run_r36_uu7_provision_trace.py (
  echo ERROR: tools\run_r36_uu7_provision_trace.py not found.
  exit /b 1
)
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher "py" not found.
  echo Run from the same LexiCore environment used by release_check.bat.
  exit /b 1
)
py tools\run_r36_uu7_provision_trace.py
exit /b %errorlevel%
