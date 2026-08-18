@echo off
setlocal
cd /d "%~dp0"

echo Welling United Red - Update Website
echo.

echo Pulling latest updater code...
git pull --ff-only
if errorlevel 1 goto :fail

echo.
echo Mirroring AttendanceRecords from Supabase...
set "WELLING_XLSX=%USERPROFILE%\OneDrive\Documents\Dan\Football\Welling United Red OBDSFL 26-27.xlsx"
if not exist "%WELLING_XLSX%" (
    echo Workbook not found: %WELLING_XLSX%
    goto :fail
)

where py >nul 2>nul
if %errorlevel%==0 (
    py mirror_attendance_records.py "%WELLING_XLSX%"
) else (
    python mirror_attendance_records.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
echo Backfilling legacy friendly MatchdayRecords...
where py >nul 2>nul
if %errorlevel%==0 (
    py backfill_legacy_matchday_records.py "%WELLING_XLSX%"
) else (
    python backfill_legacy_matchday_records.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py update_welling.py
) else (
    python update_welling.py
)
if errorlevel 1 goto :fail

echo.
echo Refreshing attendance sheets from Squad Active flag...
where py >nul 2>nul
if %errorlevel%==0 (
    py refresh_attendance_views.py "%WELLING_XLSX%"
) else (
    python refresh_attendance_views.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
echo Refreshing squad rotation / selection model...
where py >nul 2>nul
if %errorlevel%==0 (
    py refresh_squad_selection.py "%WELLING_XLSX%"
) else (
    python refresh_squad_selection.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

goto :done

:fail
echo.
echo UPDATE FAILED.

:done
echo.
pause
