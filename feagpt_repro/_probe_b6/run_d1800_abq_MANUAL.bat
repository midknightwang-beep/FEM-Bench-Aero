@echo off
REM ============================================================
REM  d1800 Abaqus manual job - run OUTSIDE WorkBuddy
REM  (double-click this file in Explorer, or run from a normal cmd)
REM  Step 1: solve the d1800 barrel job (already has .inp on disk)
REM  Step 2: extract results to odb.json (needed by the pipeline)
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM ============================================================
setlocal
set JOB=fuselage_barrel_d1800_l2000_str8_frm3
set DIR=F:\AI FEA Modeling DataSets\feagpt_repro\outputs_b6_probe_abaqus\%JOB%

cd /d "%DIR%"
if not exist "%JOB%.inp" (
  echo [ERR] input deck missing: %DIR%\%JOB%.inp
  pause
  exit /b 1
)

echo === [1/2] solving %JOB% (takes about 3-5 min) ===
call "D:\Program Files\SIMULIA\Commands\abaqus.bat" job=%JOB% cpus=1 interactive ask_delete=OFF
if errorlevel 1 (
  echo [ERR] solver exited with an error. Check %JOB%.dat / %JOB%.msg
  pause
  exit /b 1
)

echo === [2/2] extracting odb.json ===
call "D:\Program Files\SIMULIA\Commands\abaqus.bat" python "F:\AI FEA Modeling DataSets\feagpt_repro\feagpt\abaqus_odb.py" "%DIR%\%JOB%.odb" "%DIR%\%JOB%.odb.json"
if not exist "%DIR%\%JOB%.odb.json" (
  echo [ERR] odb.json was not produced
  pause
  exit /b 1
)

echo.
echo === ALL DONE ===
echo output: %DIR%\%JOB%.odb.json
pause
exit /b 0
