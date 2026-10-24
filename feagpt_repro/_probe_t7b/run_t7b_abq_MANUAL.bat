@echo off
REM ============================================================
REM  T7 build-out (D30) - Abaqus manual job - run OUTSIDE WorkBuddy
REM  Double-click this file in Explorer, or run from a normal cmd.
REM  Three composite open-hole coupons: solve -> extract odb.json
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM
REM  Cases (ccx already solved):
REM    cfrp45s      [45/-45]s  2.0mm  d20  (material axis, val)
REM    cfrpqi       [0/45/-45/90]s 2.0mm d20  (quasi-isotropic, val)
REM    cfrp45s_d40  [45/-45]s  2.0mm  d40  (material + lambda, test)
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\AI FEA Modeling DataSets\feagpt_repro
set ABAQUS="D:\Program Files\SIMULIA\Commands\abaqus.bat"
set FAILCOUNT=0
set OKCOUNT=0

for %%K in (cfrp45s cfrpqi cfrp45s_d40) do (
  if "%%K"=="cfrp45s"     set CASE=open_hole_panel_400x200_d20_cfrp45s
  if "%%K"=="cfrpqi"      set CASE=open_hole_panel_400x200_d20_cfrpqi
  if "%%K"=="cfrp45s_d40" set CASE=open_hole_panel_400x200_d20_cfrp45s_d40
  call :RUNONE %%K
)

echo.
echo ============ SUMMARY ============
if %FAILCOUNT% GTR 0 (
  echo %FAILCOUNT% job(s) FAILED, %OKCOUNT% ok - tell WOONZI which ones
) else (
  echo === ALL DONE - %OKCOUNT%/3 ok ===
)
pause
exit /b %FAILCOUNT%

:RUNONE
set K=%~1
set ROOT=%BASE%\_probe_t7b\outputs_abaqus_%K%\%CASE%
echo.
echo ============ %CASE% ============
cd /d "%ROOT%"
if not exist "%CASE%.inp" (
  echo [ERR] input deck missing: %ROOT%\%CASE%.inp
  set /a FAILCOUNT+=1
  goto :eof
)
REM the sandbox left an empty odb skeleton behind - clear it so Abaqus writes fresh
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
