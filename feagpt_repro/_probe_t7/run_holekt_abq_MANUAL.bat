@echo off
REM ============================================================
REM  verify_hole_kt - Abaqus manual job - run OUTSIDE WorkBuddy
REM  (double-click this file in Explorer, or run from a normal cmd)
REM  The open-hole Kt verification coupon: solve -> extract odb.json
REM  (Its odb.json was cleared when an in-agent solve attempt died;
REM   this hand run puts the real field back on disk.)
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\AI FEA Modeling DataSets\feagpt_repro
set ABAQUS="D:\Program Files\SIMULIA\Commands\abaqus.bat"
set CASE=verify_hole_kt
set ROOT=%BASE%\outputs\_verify_hole_abaqus\%CASE%
set FAILCOUNT=0

echo ============ %CASE% ============
cd /d "%ROOT%"
if not exist "%CASE%.inp" (
  echo [ERR] input deck missing: %ROOT%\%CASE%.inp
  set /a FAILCOUNT+=1
) else (
  echo === [1/2] solving %CASE% ===
  call %ABAQUS% job=%CASE% cpus=1 interactive ask_delete=OFF
  if errorlevel 1 (
    echo [ERR] solver exited with an error. Check %CASE%.dat / %CASE%.msg
    set /a FAILCOUNT+=1
  ) else (
    echo === [2/2] extracting odb.json ===
    call %ABAQUS% python "%BASE%\feagpt\abaqus_odb.py" "%ROOT%\%CASE%.odb" "%ROOT%\%CASE%.odb.json"
    if not exist "%ROOT%\%CASE%.odb.json" (
      echo [ERR] odb.json was not produced
      set /a FAILCOUNT+=1
    ) else (
      echo [OK] %CASE% done
    )
  )
)

echo.
echo ============ SUMMARY ============
if %FAILCOUNT% GTR 0 (
  echo %FAILCOUNT% job(s) FAILED - tell WOONZI which ones
) else (
  echo === ALL DONE - 1/1 ok ===
  echo output: %ROOT%\%CASE%.odb.json
)
pause
exit /b %FAILCOUNT%
