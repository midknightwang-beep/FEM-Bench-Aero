# W5d 跨模型榜单（同卷 · 同 prompt · 可复现）

> 生成：`make_w5d_leaderboard.py`（2026-10-27T20:28:07）。**本表不含「排名第一」**——三列口径会给出不同结论，只列事实与归因（R56）。

> 考卷 `reports/papers/tasks_v6c.jsonl`（sha `9c1faa3a731f…`）；SYS prompt sha `ce225186cafa…`（两模型逐字相同）；可比性闸：`通过 `

## 1. 主榜（同 harness）

| 口径 | C-032 `glm-5.3-flash` | C-033 `deepseek-v4-pro` | 能否相减 |
|---|---|---|---|
| **任务级 TSR**（分母 25） | **23/25 = 92.0%**，CI95 [80.0, 100.0] | **22/25 = 88.0%**，CI95 [76.0, 100.0] | ✅ Δ -4.0 pp（两份 CI95 重叠 ⇒ 差值只作观察、不作显著结论） |
| **字段级命中率**（Δ vs 族级众数地板） | 99.34%（Δ+13.4 pp，**PASS**） | 90.94%（Δ+5.0 pp，**BELOW**） | ✅（地板 85.93% 同一） |
| **条件 MSR**（分母 = 产出 spec 的非澄清题） | 20/22 = 90.9% | 20/21 = 95.2% | **❌ 不可相减** |
| exam SFR | 20/22 = 90.9% | 20/21 = 95.2% | ✅（分母各自定义） |
| 三栏 boundary / extrapolation / interpolation | 6/6 · 11/13 · 6/6 | 6/6 · 11/13 · 5/6 | 只报不判 |
| FPR 编造 / 澄清题 | 0/4 = 0.0% | 1/4 = 25.0% | ✅ |
| first-pass / turns（同 ≤3 轮预算） | 3 · 1:3 / 2:50 / 3:2 | 2 · 1:2 / 2:48 / 3:5 | ✅ |
| unresolved（模型侧无输出） | — | ['L3_open_hole_panel_400x200_d20_cfrp45s_d40'] | 并列，不进分母（R54） |

**★ MSR 一句说清**：**分母不同（22 vs 21）⇒ 不出 Δ、不得据此排名**（R54）；A 排除 []，B 排除 ['L3_open_hole_panel_400x200_d20_cfrp45s_d40']。按 pct 看 **C-033 更高，但它的 TSR 更低**——这就是「分母小的 pct 更好看」。

## 2. 逐题 2×2（归因优先于排名）

| 格 | 条数 | 题 |
|---|---:|---|
| both_pass | 22 | `fuselage_barrel_d1600_l1600_str8_frm3`<br>`fuselage_barrel_d2000_l2000_str12_frm4`<br>`naca4412_wingbox_n_ribs3_chord1000`<br>`naca4412_wingbox_n_ribs3_chord800`<br>`naca4412_wingbox_n_ribs5_chord800`<br>`naca4412_wingbox_n_ribs7_chord800`<br>`naca4412_wingbox_recombination_algorithm3`<br>`naca4412_wingbox_size_skin2`<br>`naca4412_wingbox_size_skin4`<br>`naca4412_wingbox_size_span1600`<br>`naca4412_wingbox_size_span2400`<br>`naca4412_wingbox_size_span2400_skin2`<br>`naca4412_wingbox_size_span3000_skin1p5`<br>`naca4412_wingbox_str3`<br>`naca4412_wingbox_str3_T`<br>`naca4412_wingbox_str5`<br>`naca4412_wingbox_sweep40_taper040`<br>`naca4412_wingbox_taper090`<br>`open_hole_panel_400x200_d20_offcentre`<br>`open_hole_panel_400x200_d40_offcentre`<br>`open_hole_panel_600x300_d60`<br>`stiffened_panel_600x600_str3` |
| only_a | 1 | `naca4412_wingbox` |
| only_b | 0 | — |
| neither | 2 | `naca4412_wingbox_web1_offcentre`<br>`open_hole_panel_400x200_d20_cfrp45s_d40` |

⇒ **`only_b = 0`**：C-033 没有任何一条 C-032 做错而它做对的题 ⇒ **不是互补，是纯损失**；换模型不是提分路径。

## 3. 共同失败题的字段集（判「同因」还是「异因」）

**字段集完全相同**（同一批字段错 ⇒ 更像题面/prompt 诱导）：
- `L3_naca4412_wingbox_web1_offcentre`：`['extra.end_torque', 'extra.torque_axis_dof']`（A spec_fail / B spec_fail）

**字段集不同**（⇒ 模型个性，不是题面缺陷）：

| 题 | A 类别 / B 类别 | 共同错 | 仅 A 错 | 仅 B 错 |
|---|---|---|---|---|
| `L3_open_hole_panel_400x200_d20_cfrp45s_d40` | spec_fail / no_output | — | ['params.layup'] | — |

> 类别不同（如 `spec_fail` vs `no_output`）时「仅 X 错」为空是**正常**的：无 spec 的候选没有字段级失败明细，不是「它也对了」。

## 4. 失败分层（full MSR 必须带这一列，否则不可比）

| | full MSR | model | solver | contract | 分母 |
|---|---|---:|---:|---:|---:|
| C-032 | 41/51 = 80.4% | 10 | 0 | 0 | 51 |
| C-033 | 42/50 = 84.0% | 8 | 0 | 0 | 50 |

> **full MSR 同样不可直减**：分母 51 vs 50（差的是 unresolved 题的归属），所以 80.4% 与 84.0% 不能直接比大小；要比重先用 SFR 或逐题 2×2。

## 5. 历史对照（prompt v1）——**只列事实，禁止与本榜相减**

| | exam TSR | exam MSR | 字段级 | 与本榜可比？ |
|---|---|---|---|---|
| C-029（glm-5.3-flash） | 23/25 = 92.0% | 19/22 = 86.4% | 99.34% | **❌ prompt 未记录（旧批次无 prompt_sha256）⇒ 无法证明 harness 相同（R53）** |
| C-031（deepseek-v4-pro） | 20/25 = 80.0% | 20/22 = 90.9% | 87.42% | **❌ prompt 未记录（旧批次无 prompt_sha256）⇒ 无法证明 harness 相同（R53）** |

## 6. 能说什么 / 不能说什么（引用前先看这张表）

**可以说：**

- C-032（glm-5.3-flash）exam TSR **23/25 = 92.0%**、C-033（deepseek-v4-pro）**22/25 = 88.0%**——**同卷（`tasks_sha256` 相同）+ 同 prompt（`prompt_sha256` 相同）**
- 逐题 2×2：both 22 / only_a 1 / only_b 0 / neither 2
- 两模型 `spec_pass` = 20 vs 20（相同）
- 字段级命中率：C-032 99.34%（Δ13.4 pp，PASS） vs C-033 90.94%（Δ5.0 pp，BELOW）

**不能说：**

- 「C-033 的 88.0% 是能力上限」——2×2 里 only_b = 0，没有任何一条 A 错 B 对
- 「两模型一样强」——TSR 差 4.0 pp，且失败模式不同（见共享失败字段集）
- 「差距全部来自建模能力」——`spec_pass` 20 vs 20，差异不在建模能力这一层
- 「用 MSR 单独排名」——**分母不同（22 vs 21）⇒ 不出 Δ、不得据此排名**（R54）；A 排除 []，B 排除 ['L3_open_hole_panel_400x200_d20_cfrp45s_d40']
- 「C-033 有显著增量」——字段级 Δ5.0 pp < 10 pp 判据（BELOW）
- 「dev 也一致」——dev 是开发集，不进对外结论（R15）；只作参考

## 7. 限制（写任何对外材料时必须带）

- exam n=25 ⇒ CI 宽（C-032 TSR CI95 [80.0, 100.0]）；族 n<10 不单列结论
- MSR 是条件通过率（分母 22 vs 21）⇒ 不可直减（R54）
- C-033 字段级 BELOW（Δ5.0 pp）⇒ 任务级单列会夸大
- C-033 仍有 FPR 25.0%（1/4）与 1 条问错字段 ⇒ prompt v3 待修
- C-029/C-031 是 prompt v1 历史，`prompt_sha256` 未记录 ⇒ 与本榜**不可相减**（R53）

## 8. 第三方复现命令

```bash
cd feagpt_repro && PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 --out candidates_l3_v6c_glm_p2 --limit 55 --model glm-5.3-flash --max-turns 3
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 --out candidates_l3_v6c_ds_p2 --limit 55 --model deepseek-v4-pro --max-turns 3
python score_baseline.py --candidates candidates_l3_v6c_<m> --tasks reports/papers/tasks_v6c.jsonl --report reports/baseline_scorecard_L3_v6c_<m>.json --trivial reports/trivial_baselines_L3_v6c.json
python msr_l3.py --candidates candidates_l3_v6c_<m> --tasks reports/papers/tasks_v6c.jsonl --report reports/baseline_scorecard_L3_v6c_<m>.json
python bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c_<m>.json --out reports/bootstrap_ci_L3_v6c_<m>.json
python _diag_model_diff.py --a reports/baseline_scorecard_L3_v6c_p2.json --b reports/baseline_scorecard_L3_v6c_ds_p2.json --out reports/diagnostics/model_diff_v6c_p2_glm_vs_ds.json --md reports/diagnostics/model_diff_v6c_p2_glm_vs_ds.md
python _diag_dev_reversal.py   # W5d-0：dev 反向定位
python make_w5d_leaderboard.py  # 本文件
```

> 期望：`check_claims` 全过（25 claims / 41 语义项）、负控 48/48、两份成绩单数字与本表逐项一致（S-42 机器核对）。
