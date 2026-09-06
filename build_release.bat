@echo off
setlocal
call release_check.bat
if errorlevel 1 exit /b 1

echo.
echo Building clean full-project release...
py tools\build_release.py
if errorlevel 1 exit /b 1

echo.
echo LexiCore clean release build: PASS
endlocal
