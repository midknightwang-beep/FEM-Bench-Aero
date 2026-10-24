@echo off
REM ============================================================
REM  D36 (2026-10-24) - wing-box PURE-SWEEP station at 35 deg
REM  CASE: naca4412_wingbox_sweep35
REM  Run OUTSIDE WorkBuddy (double-click in Explorer is fine).
REM
REM  ccx has already solved it:  max|u| = 5.4293 mm, max vM = 15.62 MPa,
REM  5687 active nodes, minJ 0.573, 0 triangles.
REM
REM  This job: solve -> extract odb.json.
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM
REM  Why this case (D36):
REM    D35 bought the sweep x taper interaction anchor and paid for it
REM    on the taper-NEUTRAL line: val sweep40 went -3.17 % -> -12.79 %
REM    and the val set 5.79 % -> 6.86 %.  Cause is structural: the
REM    model has ONE s^2 coefficient and D35 handed it two jobs.
REM
REM    A station at 35 deg (midpoint of the 30 -> 40 extrapolation) puts
REM    a measurement on the axis that is damaged, without moving either
REM    exam case (sweep40 stays val, sweep40_taper040 stays test).
REM
REM    Pre-registered BEFORE the solve (_probe_m13/):
REM        M3q ridge          predicted 5.04541 mm
REM        M5q ridge          predicted 4.98755 mm
REM        parabola 0/10/20/30 predicted 5.13694 mm
REM        measured            5.42926 mm  <-- ABOVE every estimate
REM    i.e. the whole 30..40 band is under-predicted, not one station.
REM    Per-degree slope 0.05136 (20-30) -> 0.08835 (30-35)
REM    -> 0.13402 (35-40): the axis is still accelerating, which is
REM    exactly what a quadratic in sweep cannot express.
REM
REM  A solver failure has one likely cause: the sandbox left an empty
REM  .odb skeleton behind.  This script deletes it before solving.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\AI FEA Modeling DataSets\feagpt_repro
set ABAQUS="D:\Program Files\SIMULIA\Commands\abaqus.bat"
set CASE=naca4412_wingbox_sweep35
set ROOT=%BASE%\_probe_m13\outputs_abaqus_sweep35\%CASE%

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
