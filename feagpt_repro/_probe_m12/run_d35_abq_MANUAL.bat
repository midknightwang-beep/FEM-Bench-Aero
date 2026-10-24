@echo off
REM ============================================================
REM  D35 (2026-10-24) - wing-box SWEEP x TAPER interaction anchor
REM  CASE: naca4412_wingbox_sweep30_taper080
REM  Run OUTSIDE WorkBuddy (double-click in Explorer is fine).
REM
REM  ccx has already solved it:  max|u| = 4.7050 mm, max vM = 12.58 MPa,
REM  5302 active nodes, minJ 0.561, 0 triangles.
REM
REM  This job: solve -> extract odb.json.
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM
REM  Why this case (D35):
REM    D34 proved the model cannot bend the sweep axis enough on the
REM    two cases that move BOTH planform knobs (13.3 % / 15.7 %),
REM    while every taper-neutral point sits at -3.2 %.  Root cause was
REM    structural: train held ZERO cases with sweep>0 AND taper!=1, so
REM    the interaction column s^2*(taper-1) was identically zero and
REM    could not be estimated.  No basis change fixes that, only a
REM    sample does.  This case is that sample: sweep 30 deg (top of
REM    train's envelope) x tip ratio 0.8 (interior of train's set).
REM
REM    Measured physics check (ccx side, _probe_m12):
REM      log-additive decomposition puts the interaction at
REM      -12.6 % (20x0.6)  -7.8 % (30x0.8)  -25.9 % (40x0.4)
REM      i.e. consistently negative -- exactly the direction that made
REM      the old model over-predict those two test points.
REM
REM  A solver failure has one likely cause: the sandbox left an empty
REM  .odb skeleton behind.  This script deletes it before solving.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\AI FEA Modeling DataSets\feagpt_repro
set ABAQUS="D:\Program Files\SIMULIA\Commands\abaqus.bat"
set CASE=naca4412_wingbox_sweep30_taper080
set ROOT=%BASE%\_probe_m12\outputs_abaqus_sweep30_taper080\%CASE%

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
