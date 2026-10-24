@echo off
REM ============================================================
REM  D33 (2026-10-24) - wing-box SWEEP station 30 deg - Abaqus job
REM  Run OUTSIDE WorkBuddy (double-click in Explorer is fine).
REM
REM  One case.  ccx has already solved it (max|u| = 4.38434 mm).
REM  This job: solve -> extract odb.json.
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM
REM  Why this batch (D33):
REM    train currently knows sweep at {0, 10, 20} deg.  20 -> 40 is the
REM    only axis in the dataset that fails hard on extrapolation
REM    (-41.5 %, M7).  Adding 30 makes it a 4-station axis (curvature
REM    identifiable) and halves the distance 40 must be extrapolated
REM    over (20 deg -> 10 deg).  sweep40 stays val, sweep40_taper040
REM    stays test -- the exam is not deleted, it is made fair.
REM
REM  A solver failure has one likely cause: the sandbox left an empty
REM  .odb skeleton behind.  This script deletes it before solving.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\AI FEA Modeling DataSets\feagpt_repro
set ABAQUS="D:\Program Files\SIMULIA\Commands\abaqus.bat"
set CASE=naca4412_wingbox_sweep30
set ROOT=%BASE%\_probe_m10\outputs_abaqus_sweep30\%CASE%

echo ============ %CASE% ============
cd /d "%ROOT%"
if not exist "%CASE%.inp" (
  echo [ERR] input deck missing: %ROOT%\%CASE%.inp
  pause
  exit /b 1
)
if exist "%CASE%.odb" del /q "%CASE%.odb"
if exist "%CASE%.odb_f" del /q "%CASE%.odb_f"
if exist "%CASE%.lck" del /q "%CASE%.lck"
if exist "%CASE%.odb.json" del /q "%CASE%.odb.json"

echo === [1/2] solving %CASE% ===
call %ABAQUS% job=%CASE% cpus=1 interactive ask_delete=OFF
if errorlevel 1 (
  echo [ERR] solver exited with an error. Check %CASE%.dat / %CASE%.msg
  pause
  exit /b 1
)
echo === [2/2] extracting odb.json ===
call %ABAQUS% python "%BASE%\feagpt\abaqus_odb.py" "%ROOT%\%CASE%.odb" "%ROOT%\%CASE%.odb.json"
if not exist "%ROOT%\%CASE%.odb.json" (
  echo [ERR] odb.json was not produced
  pause
  exit /b 1
)

echo.
echo === ALL DONE - 1/1 ok ===
pause
exit /b 0
