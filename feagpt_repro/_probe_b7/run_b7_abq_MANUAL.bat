@echo off
REM ============================================================
REM  batch-7 Abaqus manual job - run OUTSIDE WorkBuddy
REM  (double-click this file in Explorer, or run from a normal cmd)
REM  Four open-hole coupons, each: solve -> extract odb.json
REM  When you see "ALL DONE", tell WOONZI and he takes over.
REM ============================================================
setlocal enabledelayedexpansion
set BASE=F:\AI FEA Modeling DataSets\feagpt_repro
set ABAQUS="D:\Program Files\SIMULIA\Commands\abaqus.bat"
set ROOT=%BASE%\outputs_b7_abaqus
set FAILCOUNT=0

for %%C in (open_hole_panel_600x300_d30 open_hole_panel_400x200_d50 open_hole_panel_600x300_d60 open_hole_panel_400x200_d40_offcentre) do (
  echo.
  echo ============ %%C ============
  cd /d "%ROOT%\%%C"
  if not exist "%%C.inp" (
    echo [ERR] input deck missing: %ROOT%\%%C\%%C.inp
    set /a FAILCOUNT+=1
  ) else (
    echo === [1/2] solving %%C ===
    call %ABAQUS% job=%%C cpus=1 interactive ask_delete=OFF
    if errorlevel 1 (
      echo [ERR] solver exited with an error. Check %%C.dat / %%C.msg
      set /a FAILCOUNT+=1
    ) else (
      echo === [2/2] extracting odb.json ===
      call %ABAQUS% python "%BASE%\feagpt\abaqus_odb.py" "%ROOT%\%%C\%%C.odb" "%ROOT%\%%C\%%C.odb.json"
      if not exist "%ROOT%\%%C\%%C.odb.json" (
        echo [ERR] odb.json was not produced
        set /a FAILCOUNT+=1
      ) else (
        echo [OK] %%C done
      )
    )
  )
)

echo.
echo ============ SUMMARY ============
if %FAILCOUNT% GTR 0 (
  echo %FAILCOUNT% job(s) FAILED - tell WOONZI which ones
) else (
  echo === ALL DONE - 4/4 ok ===
  echo outputs: %ROOT%\open_hole_panel_*\*.odb.json
)
pause
exit /b %FAILCOUNT%
