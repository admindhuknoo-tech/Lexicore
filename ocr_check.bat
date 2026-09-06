@echo off
setlocal

echo Checking LexiCore local OCR engines...
py -c "from env_loader import load_project_env; load_project_env(); from services.document_ocr import ocr_runtime_status; s=ocr_runtime_status(load_engine=True); assert s['available'], s.get('error') or 'Tidak ada OCR engine lokal yang siap'; print('OCR overall PASS | active=',s['engine'],'| embedded=',s['embedded_available'],'| portable=',s['portable'],'| tesseract=',s['tesseract_available'],'| langs=',','.join(s.get('tesseract_languages') or [])); print('Embedded error=',s.get('embedded_error') or '-')"
if errorlevel 1 (
  echo.
  echo OCR readiness: FAIL
  echo Jalankan: py -m pip install -r requirements.txt
  echo Embedded RapidOCR adalah engine utama portable; Tesseract dapat dipakai sebagai fallback lokal.
  exit /b 1
)
echo LexiCore OCR readiness: PASS
endlocal
