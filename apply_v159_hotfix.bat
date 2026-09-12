@echo off
setlocal
py tools\apply_v159_smoke_contract_hotfix.py
if errorlevel 1 exit /b %errorlevel%
echo.
echo Hotfix applied. Now run: release_check.bat
