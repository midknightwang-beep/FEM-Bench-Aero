#!/usr/bin/env bash
# v1.1 双码物理一致性验收（ccx vs abaqus），9 条逐条串行
# 判据按族给：翼盒 tip_force 500N clamp / 开孔板 tip_force 4000N clamp /
#             柱壳 pressure+端载 -> all / 加筋板 pressure -> all
set -u
cd "F:/AI FEA Modeling DataSets/feagpt_repro" || exit 1
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
CCX="_v11/runs"
ABQ="_v11/runs_abaqus"
OUT="F:/AI FEA Modeling DataSets/feagpt_repro/reports/diagnostics/xval_v11_9cases.log"
: > "$OUT"

run_one() {
  local case="$1" force="$2" rset="$3"
  local spec="$CCX/$case/$case.spec.json"
  echo "########## $case  (force=$force reaction-set=$rset)" | tee -a "$OUT"
  "$PY" verify_solvers.py --ccx "$CCX" --abaqus "$ABQ" --case "$case" \
      --force "$force" --reaction-set "$rset" --spec "$spec" >> "$OUT" 2>&1
  grep -E "^  VERDICT|^    \*" "$OUT" | tail -6
  echo
}

# 翼盒族：500 N 端载，clamp
for c in naca4412_wingbox_n_ribs6_chord1000 naca4412_wingbox_size_chord900 \
         naca4412_wingbox_size_skin2p5 naca4412_wingbox_str4 naca4412_wingbox_taper070; do
  run_one "$c" 500 clamp
done

# 开孔板族：4000 N 面内拉伸，clamp
run_one open_hole_panel_400x200_d30 4000 clamp
run_one open_hole_panel_500x250_d45 4000 clamp

# 柱壳：内压 0.05 + 端剪 5e4 + 端弯 5e7 -> 分布式，all
run_one fuselage_barrel_d2000_l1800_str8_frm3 0 all

# 加筋板：面压 1e-4 -> 分布式，all
run_one stiffened_panel_700x600_str4 0 all

echo "==================== SUMMARY ====================" | tee -a "$OUT"
grep -c "VERDICT: PASS" "$OUT" | sed 's/^/PASS count: /'
grep -c "VERDICT: CHECK" "$OUT" | sed 's/^/CHECK count: /'
grep -c "VERDICT: FAIL" "$OUT" | sed 's/^/FAIL count: /'
echo "log -> $OUT"
