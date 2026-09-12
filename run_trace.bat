@echo off
setlocal
set LEXICORE_OFFICIAL_TRACE=1
set LEXICORE_TRACE_EXPECTED=UU:31:1999
set LEXICORE_TRACE_FILE=trace_r22_baseline.json
python run_trace.py
endlocal
