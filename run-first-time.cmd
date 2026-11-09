@echo off
rem Double-click to run the first full pipeline pass. Output is also saved to .out\monthly\run-log.txt
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-first-time.ps1"
echo.
echo Finished. Log: .out\monthly\run-log.txt
pause
