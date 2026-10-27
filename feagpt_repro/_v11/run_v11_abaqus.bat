@echo off
chcp 65001 >nul
setlocal
REM ============================================================================
REM  v1.1 新几何（9 条内插留出）—— Abaqus 双码交叉验证（gate 3）
REM
REM  为什么必须手工跑：WorkBuddy 的沙箱会注入 tsbx.dll，abaqus 在 agent 内必然
REM  在 pre.exe 阶段 __fastfail（典型签名：约 19 秒后 "Input File Processor" 报错，
REM  .dat 里却没有错误、ODB 是空骨架）。dangerouslyDisableSandbox 也无效。
REM  ⇒ 只能在**普通 cmd**窗口里手工执行本文件。
REM
REM  用法：双击，或在 cmd 里执行
REM      cd /d "F:\AI FEA Modeling DataSets\feagpt_repro\_v11"
REM      run_v11_abaqus.bat
REM
REM  跑完会发生什么：
REM    * _v11\runs_abaqus\<case>\ 里出现 .odb / .odb.json / .results.json / .truth.json
REM    * FEM-Bench-Aero\_xval\<case>\ 出现 9 个新目录（Abaqus 树，**不得发布**）
REM    * verify_dataset 的 pairing 从 "55 paired + 9 modeling-only" 变成 "64 paired"
REM
REM  绝不要并行跑两个 abaqus / ccx：会静默空转、rc 仍为 0，结果却是空的。
REM ============================================================================

cd /d "F:\AI FEA Modeling DataSets\feagpt_repro"
set PY=C:\Users\22207\.workbuddy\binaries\python\envs\default\Scripts\python.exe
set ABQ="D:\Program Files\SIMULIA\Commands\abaqus.bat"

echo.
echo [1/3] 检查 abaqus 可用性……
call %ABQ% information=release
if errorlevel 1 (
  echo [FAIL] 找不到 abaqus，请检查 ABQ 变量里的路径
  goto :end
)

echo.
echo [2/3] 逐条求解（9 条，串行！）……
for %%C in (
  naca4412_wingbox_size_skin2p5
  naca4412_wingbox_n_ribs6_chord1000
  naca4412_wingbox_str4
  naca4412_wingbox_size_chord900
  naca4412_wingbox_taper070
  open_hole_panel_400x200_d30
  open_hole_panel_500x250_d45
  stiffened_panel_700x600_str4
  fuselage_barrel_d2000_l1800_str8_frm3
) do (
  echo.
  echo ---- %%C ----
  "%PY%" run_pipeline.py --spec "_v11\staging\%%C\%%C.spec.json" --out _v11\runs_abaqus --solver abaqus
  if errorlevel 1 echo [FAIL] %%C 求解失败，先停下来看日志，不要继续
)

echo.
echo [3/3] 打包进 _xval 树 + 复跑配对校验……
"%PY%" make_dataset.py --solver abaqus --cases _v11\runs_abaqus --root ..\FEM-Bench-Aero
"%PY%" verify_dataset.py --root ..\FEM-Bench-Aero

echo.
echo 期望结果：pairing 显示 "64 paired, 0 modeling-only"、VERDICT: PASS
echo 若仍是 "9 modeling-only"，说明某条 abaqus 没跑成，回看上面的 [FAIL]。

:end
echo.
pause
endlocal
