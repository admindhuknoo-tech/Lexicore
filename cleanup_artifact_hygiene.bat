@echo off
setlocal
py tools\cleanup_artifact_hygiene.py
if errorlevel 1 exit /b 1
endlocal
