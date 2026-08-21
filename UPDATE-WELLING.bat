@echo off
setlocal
cd /d "%~dp0"

echo Welling Dashboard - Update
echo.

set "WELLING_XLSX=%USERPROFILE%\OneDrive\Documents\Dan\Football\Welling United Red OBDSFL 26-27.xlsx"
if not exist "%WELLING_XLSX%" (
    echo Workbook not found: %WELLING_XLSX%
    goto :fail
)

rem data/*.json are generated output. If a previous update was cancelled after
rem export but before commit, restore the published versions before rebuilding.
git restore -- data >nul 2>nul

echo Mirroring AttendanceRecords from Supabase...
where py >nul 2>nul
if %errorlevel%==0 (
    py mirror_attendance_records.py "%WELLING_XLSX%"
) else (
    python mirror_attendance_records.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
echo Cleaning rows for deleted fixtures...
where py >nul 2>nul
if %errorlevel%==0 (
    py prune_deleted_fixture_rows.py "%WELLING_XLSX%"
) else (
    python prune_deleted_fixture_rows.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
echo Cleaning removed Matchday test data...
where py >nul 2>nul
if %errorlevel%==0 (
    py cleanup_stale_matchday_data.py "%WELLING_XLSX%"
) else (
    python cleanup_stale_matchday_data.py "%WELLING_XLSX%"
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
echo Reconciling completed Matchdays from Supabase...
where py >nul 2>nul
if %errorlevel%==0 (
    py reconcile_matchday_records.py "%WELLING_XLSX%"
) else (
    python reconcile_matchday_records.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
echo Preparing MatchdayRecords for dashboard export...
where py >nul 2>nul
if %errorlevel%==0 (
    py ensure_matchday_export_columns.py "%WELLING_XLSX%"
) else (
    python ensure_matchday_export_columns.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
echo Refreshing player bios and straplines...
where py >nul 2>nul
if %errorlevel%==0 (
    py ensure_player_bios.py "%WELLING_XLSX%"
) else (
    python ensure_player_bios.py "%WELLING_XLSX%"
)
if errorlevel 1 goto :fail

echo.
echo Exporting detailed match timeline...
where py >nul 2>nul
if %errorlevel%==0 (
    py export_match_timeline.py "%WELLING_XLSX%"
) else (
    python export_match_timeline.py "%WELLING_XLSX%"
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
echo Refreshing attendance sheets...
where py >nul 2>nul
if %errorlevel%==0 (
    py refresh_attendance_views_v2.py "%WELLING_XLSX%"
) else (
    python refresh_attendance_views_v2.py "%WELLING_XLSX%"
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
