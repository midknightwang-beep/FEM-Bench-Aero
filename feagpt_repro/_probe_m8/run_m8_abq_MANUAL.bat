@echo off
REM ============================================================
REM  D31 (2026-10-24) - wing-box SIZE axis - Abaqus manual job
REM  Run OUTSIDE WorkBuddy (double-click in Explorer is fine).
REM
REM  Eight size-axis cases.  ccx has already solved all of them.
REM  This job: solve -> extract odb.json for each.
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM
REM  Batch design (D31):
REM    train (train range: span [1600,2400], skin [2,4])
REM      size_span1600            span 1600  skin 3.0
REM      size_span2400            span 2400  skin 3.0
REM      size_skin2               span 2000  skin 2.0
REM      size_skin4               span 2000  skin 4.0
REM    val   (one axis outside the range)
REM      size_span3000            span 3000  skin 3.0
REM      size_skin1p5             span 2000  skin 1.5
REM    test  (two axes at once)
REM      size_span3000_skin1p5    span 3000  skin 1.5
REM      size_span2400_skin2      span 2400  skin 2.0  (interaction point)
REM
REM  A solver failure has one likely cause: the sandbox left an empty
REM  .odb skeleton behind.  This script deletes it before solving.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\AI FEA Modeling DataSets\feagpt_repro
set ABAQUS="D:\Program Files\SIMULIA\Commands\abaqus.bat"
set FAILCOUNT=0
set OKCOUNT=0

for %%K in (size_span1600 size_span2400 size_skin2 size_skin4 size_span3000 size_skin1p5 size_span3000_skin1p5 size_span2400_skin2) do (
  set CASE=naca4412_wingbox_%%K
  set TAG=%%K
  call :RUNONE
)

echo.
echo ============ SUMMARY ============
if %FAILCOUNT% GTR 0 (
  echo %FAILCOUNT% job(s) FAILED, %OKCOUNT% ok - tell WOONZI which ones
) else (
  echo === ALL DONE - %OKCOUNT%/8 ok ===
)
pause
exit /b %FAILCOUNT%

:RUNONE
set ROOT=%BASE%\_probe_m8\outputs_abaqus_%TAG%\%CASE%
echo.
echo ============ %CASE% ============
cd /d "%ROOT%"
if not exist "%CASE%.inp" (
  echo [ERR] input deck missing: %ROOT%\%CASE%.inp
  set /a FAILCOUNT+=1
  goto :eof
)
if exist "%CASE%.odb" del /q "%CASE%.odb"
if exist "%CASE%.odb.json" del /q "%CASE%.odb.json"

echo === [1/2] solving %CASE% ===
call %ABAQUS% job=%CASE% cpus=1 interactive ask_delete=OFF
if errorlevel 1 (
  echo [ERR] solver exited with an error. Check %CASE%.dat / %CASE%.msg
  set /a FAILCOUNT+=1
  goto :eof
)
echo === [2/2] extracting odb.json ===
call %ABAQUS% python "%BASE%\feagpt\abaqus_odb.py" "%ROOT%\%CASE%.odb" "%ROOT%\%CASE%.odb.json"
if not exist "%ROOT%\%CASE%.odb.json" (
  echo [ERR] odb.json was not produced
  set /a FAILCOUNT+=1
) else (
  echo [OK] %CASE% done
  set /a OKCOUNT+=1
)
goto :eof
