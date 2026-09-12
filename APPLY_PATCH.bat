@echo off
setlocal
REM Apply after extracting this patch over the LexiCore project root.
if exist "exporters\terminology_mapper.py" del /f /q "exporters\terminology_mapper.py"
if exist "exporters\__pycache__\terminology_mapper*.pyc" del /f /q "exporters\__pycache__\terminology_mapper*.pyc" 2>nul
if exist "tests\__pycache__\test_pleading_cleaner_and_terminology_v122*.pyc" del /f /q "tests\__pycache__\test_pleading_cleaner_and_terminology_v122*.pyc" 2>nul
echo Release-hygiene cleanup applied.
echo Now run: release_check.bat
endlocal
