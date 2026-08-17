@echo off
setlocal
cd /d "%~dp0"

echo Welling United Red - Update Website
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py update_welling.py
) else (
    python update_welling.py
)

echo.
pause
