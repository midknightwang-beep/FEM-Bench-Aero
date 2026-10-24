#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# verify_abq_whitelist.sh  —  batch6 abaqus 解封复测（D28, 2026-10-06）
#
# 背景：WorkBuddy 自更新到 sandbox 5.7.10（2026-10-06 20:14）后，沙箱向 Abaqus
#       pre.exe 注入 tsbx.dll，pre.exe 随即 __fastfail 0xc0000409，abaqus 100% 失败
#       （与内存无关：1 单元最小模型同样崩）。
#       处置：把 Abaqus 可执行文件加进 tsbx_rules.json 的 white_process（8→13 条）。
#
# ⚠️ 必须在**沙箱启用（默认）模式**下运行本脚本，否则沙箱根本不被咨询、日志无新行。
#    即：不要加 dangerouslyDisableSandbox。
#
# 用法：cd feagpt_repro && bash _probe_b6/verify_abq_whitelist.sh
# 退出码：0 = 已解封（可继续 batch6 abaqus 四条）；1 = 仍未解封
# ---------------------------------------------------------------------------
set -u

ABQ="D:/Program Files/SIMULIA/Commands/abaqus.bat"
PROBE="/f/AI FEA Modeling DataSets/feagpt_repro/_probe_b6/mini_abq"
WORK="/d/abq_verify"
SBOXLOG_ROOT="/c/Users/22207/.workbuddy/logs/sandbox"
RULES="/e/WorkBuddy/resources/app.asar.unpacked/cli/vendor/sandbox/5.7.10/tsbx_rules.json"

sbox_lines () {  # 今日日志里 pre.exe 的 decide_command 行数
  find "$SBOXLOG_ROOT/$(date +%Y%m%d)" -name "*.log" 2>/dev/null \
    -exec grep -h "decide_command" {} \; 2>/dev/null | grep -i "pre\.exe" | wc -l
}

echo "=== 0) 白名单现状 ==="
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" - "$RULES" <<'PYEOF'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
wp=[e['path'] for e in d.get('white_process',[])]
print("white_process (%d):" % len(wp))
for p in wp: print("   ", p)
PYEOF
sha256sum "$RULES" | tr -d '\r'

BEFORE=$(sbox_lines)

echo
echo "=== 1) 跑 1 单元最小作业（沙箱启用模式）==="
rm -rf "$WORK"; mkdir -p "$WORK"
cp "$PROBE/mini.inp" "$WORK/vf.inp"
( cd "$WORK" && "$ABQ" job=vf cpus=1 interactive ask_delete=OFF ) > "$WORK/run.log" 2>&1
tail -12 "$WORK/run.log"
echo "--- .dat 关键行 ---"
grep -E "END OF USER INPUT PROCESSING|JOB TIME SUMMARY|NUMBER OF NODES IS" "$WORK/vf.dat" 2>/dev/null | tr -d '\r'
FAILED=0; grep -q "Abaqus Error" "$WORK/run.log" && FAILED=1
if [ "$FAILED" = 1 ]; then echo "--- 结果：✗ 仍失败（出现 Abaqus Error）"; else echo "--- 结果：✓ 未见 Abaqus Error"; fi

echo
echo "=== 2) 本次运行新增的 pre.exe 注入决策 ==="
NEW=$(find "$SBOXLOG_ROOT/$(date +%Y%m%d)" -name "*.log" 2>/dev/null \
      -exec grep -h "decide_command" {} \; 2>/dev/null | grep -i "pre\.exe" | tail -n +$((BEFORE+1)))
if [ -z "$NEW" ]; then
  echo "  （无新行 —— 本次注入未经 decide_command 路径，或决策被会话缓存）"
else
  echo "$NEW" | tr -d '\r' | sed -E 's/.*command=[^ ]*(pre\.exe).*action=([a-z_]+) inject=([a-z_]+).*/  action=\2 inject=\3/' | tail -6
fi

echo
echo "=== 3) 判定 ==="
if [ -n "$NEW" ] && echo "$NEW" | grep -q "inject=skip"; then
  echo "  ✓ inject=skip —— 白名单已生效，可继续 batch6 abaqus 四条。"; exit 0
fi
if [ "$FAILED" = 0 ]; then
  echo "  ✓ abaqus 已能跑通（未出现 Abaqus Error）—— 白名单/其他修复生效，可继续 batch6。"; exit 0
fi
echo "  ✗ 仍失败："
if [ -n "$NEW" ] && echo "$NEW" | grep -q "inject=inject"; then
  echo "    沙箱已重载规则但**仍注入** —— 5.7.10 不认 white_process ⇒ 转 B（手动跑）/ C（本轮留空）。"
else
  echo "    注入未经 decide_command 路径 ⇒ 白名单对该路径无效 ⇒ 转 B（手动跑）/ C（本轮留空）。"
fi
exit 1
