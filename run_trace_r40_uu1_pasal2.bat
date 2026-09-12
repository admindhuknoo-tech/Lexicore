@echo off
setlocal
cd /d %~dp0
echo ========================================================================================
echo R40 POST-FULLTEXT PROVISION STATE TRACE - UU 1/2015 PASAL 2
echo ========================================================================================
py tools\run_r40_uu1_pasal2_trace.py
if errorlevel 1 python tools\run_r40_uu1_pasal2_trace.py
pause
