@echo off
setlocal
cd /d "%~dp0"
echo ========================================================================================
echo R39 DIAGNOSTIC TRACE - UU 1/2015 PASAL 2 - R38 PRODUCTION PATH
echo ========================================================================================
if not exist tools\run_r38_uu1_provision_trace.py (
  echo ERROR: tools\run_r38_uu1_provision_trace.py not found.
  exit /b 1
)
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher "py" not found.
  echo Run from the same LexiCore environment used by release_check.bat.
  exit /b 1
)
py tools\run_r38_uu1_provision_trace.py
set RC=%errorlevel%
echo.
if %RC%==0 (
  echo Trace selesai. Kirim dua file berikut untuk analisis:
  echo   trace_r38_uu1_pasal2_summary.txt
  echo   trace_r38_uu1_pasal2.json
) else (
  echo Trace gagal dengan exit code %RC%.
)
pause
exit /b %RC%
