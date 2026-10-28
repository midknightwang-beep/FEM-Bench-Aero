# reports/ — 官方产物索引（W5a'，红线 R25/R27）

> **为什么有这个目录**：`feagpt_repro/eval_runs/` 被 `.gitignore` 排除（第 52 行），
> 官方数字放在那里 ⇒ 新 clone 只能看到命令看不到文件，重跑即覆盖（C-021 的 v4 成绩单
> 已被 v5 重打分覆盖，第六轮复评才发现）。本目录**入库**，文件名带版本，作为唯一官方出处。
> **纪律**：诊断结果不得占用官方路径（R27）；文件改名/覆盖必须更新本表与 `CLAIMS.md`。

## 1. 一句话读法

| 用途 | 文件 | 口径 |
|---|---|---|
| **官方 headline（对外唯一可引用）** | `baseline_scorecard_L3_v6c_p2.json` + `bootstrap_ci_L3_v6c_p2.json` | **C-032**（prompt v2 代，`prompt_sha256 = ce225186…`）：考卷 **v6c**（`tasks_sha256 = 9c1faa3a…`，与 C-029 **逐字节相同**）× `candidates_l3_v6c_glm_p2`（glm-5.3-flash，55/55，`n_unresolved=0`）。exam **TSR 23/25 (92.0%) / SFR 20/22 (90.9%) / MSR 20/22 (90.9%)**；三栏 boundary **6/6** · extrapolation **11/13** · interpolation **6/6**；CI95（`bootstrap_ci_L3_v6c_p2.json`）：TSR **[80.0, 100.0]**、SFR **[77.3, 100.0]**、MSR **[77.3, 100.0]**；`n=25 ⇒ underpowered=False`。**全链 MSR**：exam **20/22 (90.9%)** / dev **21/29 (72.4%)** / full **41/51 (80.4%)**，`n_solver_excluded=0`（两代都一样的分母 51）。**★★ R50 修复的效果可精确断言**：删掉「未提长桁→长桁数=0」授权 + 增「数量类字段铁律」后，**glm 的 exam 逐题类别与 C-029 完全相同**（20 spec_pass / 3 clarify_ok / 2 spec_fail）⇒ **glm 本来没被诱导，修的是对别家模型的隐患**；dev 净 **−1**（23→22）可完整拆成 **+1**（`stiffened_panel_800x600_str3` 因 R41 模板修好而读对 `length/width`）**−2**（两条柱壳 `extra.end_moment` 写成 50000 / 5e6，gold 是 5e7 ⇒ 单位换算采样波动，与 prompt 无关）。**★ MSR == SFR（41/51）不是放水**：C-029 的 4 条 solver（柱壳撞 158,548 节点阈值）在本批网格下全部算得动 ⇒ `n_solver_excluded=0`，凡 `spec_pass` 必真跑通。**★ 与 C-029 不可并列（R53）**：两代 `prompt_sha256` 不同（C-029 那批未记录 = UNKNOWN），只能作同模型 harness ablation（`diagnostics/prompt_v2_effect_glm.md`），**不得作两份成绩并列引用** |
| **上一代官方（prompt v1 代，已被 C-032 取代；保留作 R50 缺陷实证）** | `baseline_scorecard_L3_v6c.json` | **C-029**：考卷 **v6c**（55 条 L3 / exam 25 三栏）× 候选 **`candidates_l3_v6c`**（55/55，`n_unresolved=0`）。exam **TSR 23/25 (92.0%) / SFR 20/22 (90.9%)**；**n=25 ⇒ `underpowered=False`**；CI95 见 `bootstrap_ci_L3_v6c.json`（TSR **[80.0, 100.0]**、SFR **[77.3, 100.0]**、MSR **[72.7, 100.0]**）。**全链 MSR（R35 四行）**：exam **19/22 (86.4%)** → 剔 solver **19/21 (90.5%)**；dev **19/29 (65.5%)** → 剔 solver **19/26 (73.1%)**；full **38/51 (74.5%)** → 剔 solver **38/47 (80.9%)**。**4 条 solver 全是柱壳（143k / 158k×2 / 169.6k 节点 > 阈值 158,548），其中 1 条在 exam**；★ solver 桶**候选相关**（同题 `str12_frm4` 在 v6b 是 model、v6c 变 solver）⇒ **剔除口径也不可跨版本直减**。三栏：boundary **6/6**、extrapolation **11/13**、interpolation **6/6**。**与 C-028 的 68.0%、C-021 的 45.5% 一律不可相减**（R30/R39，`compare_scorecards.py` rc=3——与 C-028 同 25 条 exam id 但**题面已改**，paper sha 不同）。**涨幅必须按 bridge 四格拆**：17/25 → 18/25（判分修正）→ 18/25（考卷修复对旧候选 +0）→ 23/25（重生成），见 `diagnostics/bridge_w5c_table.md`。**`value_added` 两种尺度（R44）**：任务级 地板 T1/T1+ 均 **0.0%** → LLM 92.0%（Δ92.0 pp）；字段级 地板 **85.93%** → LLM **99.34%**（**Δ+13.4 pp**，同样过 10 pp）。**★ 「0 地板」是全或无判分的必然**：`spec_fidelity` 逐字段全对才算过 × 族内参数逐条唯一 ⇒ 最强「不读输入」策略命中 86% 字段、最好一条只差 **1** 个字段，但 25 条无一全对，族内 oracle 上界也 **0/25** |
| **第二模型 · 同 harness（supporting，不作 headline；**首例 R53 合规**跨模型对比）** | `baseline_scorecard_L3_v6c_ds_p2.json` + `bootstrap_ci_L3_v6c_ds_p2.json` | **C-033**（`deepseek-v4-pro`，`prompt_sha256 = ce225186…` **与 C-032 逐字相同**）：exam **TSR 22/25 (88.0%)**、CI95 **[76.0, 100.0]**、SFR **20/21 (95.2%)**、三栏 **6/6 · 11/13 · 5/6**；**MSR exam 20/21 (95.2%)** / dev 22/29 / full **42/50 (84.0%)**，`n_solver_excluded=0`。**★ 2×2 = both 22 / only_a 1 / only_b 0 / neither 2**；两模型 `spec_pass` **同为 20/25** ⇒ 4 pp 差不来自建模能力；**★ R50 修复对它回收 +2**（正是 C-031 编造的两条）⇒ C-031 的 80.0% 有 2 条是 prompt 下界；**⚠ R54：exam MSR 分母 21 ≠ C-032 的 22（排除的是失败题）⇒ pct 不得直减**；与 `baseline_scorecard_L3_v6c_dsv4pro.json`（C-031，prompt v1 代）**不可拼比**（R53） |
| **跨模型榜单/协议（C-034）** | `w5d_leaderboard.json` + `w5d_leaderboard.md` | **W5d**：C-032/C-033 同卷同 prompt 的**三列并排**表（任务级 / 字段级 / 失败分层）+ 2×2 + 「能说什么/不能说什么」+ 限制段。**★ 三个口径排名相反**：TSR 92.0>88.0、字段级 PASS>BELOW、条件 MSR **90.9<95.2**（分母 22 vs 21）⇒ 只引一列可得出任意结论（R56）。**★ 归因**：only_b=0、`spec_pass` 20=20 ⇒ 不是互补、不是建模能力差距 |
| **prompt 消融（C-035，已否决）** | `diagnostics/prompt_v3_ablation.json` + `.md` | **v3 / v3b 两版均否决**：exam 澄清题正确数三版完全一致（glm 3/3/3、deepseek 2/2/2），但**失败点在迁移**（多问 → 该问不问填 0 → 3 轮未收敛）⇒ 打地鼠、零收益。**prompt 已回退 v2**（sha == C-032），故 C-032/C-033/C-034 全部继续有效。S-43/NC-48 守住「写了否决却偷换 prompt」。**别再重做** |
| **dev 反向定位（W5d-0）** | `diagnostics/dev_reversal_v6c_p2.json` + `.md` | C-032 dev **23→22（净 −1）= fail→pass 1 − pass→fail 2**，闭合断言通过、与成绩单 dev TSR 交叉一致：`stiffened_800x600_str3` 由 `600/800` 纠正为 `800/600`（题面 R41 修正被兑现）；两条柱壳 `extra.end_moment` 写 `5e4`/`5e6` 而 gold `5e7`（×10⁻³/×10⁻¹ 量级偏差，与 prompt 无关）⇒ **dev 22 是已知代价，不是模型退步**（R55/S-41） |
| **第二模型（supporting，不作 headline）** | `baseline_scorecard_L3_v6c_dsv4pro.json` + `bootstrap_ci_L3_v6c_dsv4pro.json` | **C-031**：**同一份 v6c 考卷**（`tasks_sha256` 与 C-029 逐字节相同）× `candidates_l3_v6c_dsv4pro`（`deepseek-v4-pro`，55/55）。exam **TSR 20/25 (80.0%)**、SFR 20/25、dev 22/30。**用途=可重复性 + 归因**：`spec_pass` 两模型同为 20/25、2 条 `spec_fail` 同题同字段 ⇒ 失分主因是题面/prompt 而非模型；差异全在澄清题。**R48：不得因成绩高低换 headline** |
| 上一代 headline（降为 diagnostic lower bound） | `baseline_scorecard_L3_v6b.json` + `bootstrap_ci_L3_v6b.json` | **C-028（第八轮 D1 降级）**：考卷 v6b × `candidates_l3_v6`。exam **TSR 17/25 (68.0%) / SFR 14/21 / MSR 10/21**、全链 MSR 25/44；CI95 [48.0, 84.0]。三栏 5/6 · 7/13 · 5/6。**已含 8 处已知缺陷 ⇒ 只是下界，不得对外**；档案保留（D10），**不重算** |
| 上一代 headline（降为历史口径） | `baseline_scorecard_L3_v4.json` | C-021：考卷 **v4** × 候选 **v4**（`candidates_l3_v3`），exam 11 条 **TSR 5/11 (45.5%) / SFR 5/10 / MSR 4/9**，**n=11 UNDERPOWERED**；CI95 见 `bootstrap_ci_L3_v4.json`（TSR **[18.2, 72.7]**） |
| **诊断（不是模型成绩）** | `baseline_scorecard_L3_v5_rescore.json` | C-025：**旧候选**（v4 生成）打 **v5** 考卷 ⇒ exam TSR 4/11。旧候选不能评新考卷（R28），只用于验证「修题改了什么」 |
| L1 冒烟（非模型基线） | `baseline_scorecard_L1_smoke.json` | C-017：spec-copy 19 条 SFR 0/19，无 schema 约束解码时的指令遵循失败 |
| 桥接表 | `bridge_v3_v4.json` + `bridge_A/B/C_*.json`（历史）／ **`diagnostics/bridge_w5c_table.md` + `diagnostics/bridge_w5c_B/C_*.json`（当前）** | C-024：A 7/11、B 5/11、C 0/11、D 5/11；A→D = −3 wingbox 方向 +1 d2000。**W5c 四格**：17→18（判分）→18（考卷，+0）→23（重生成） |
| 负控 | **`negative_controls_58.json`（当前）**；`_57`/`_56`/`_55`/`_54`/`_53`/`_51`/`_50`/`_49`/`_48`/`_47`/`_44`/`_41`/`_39`/`_37`/`_31` **已移入 `archive/`（历史，不得引用）**（R42：数字只认最新那份） | C-019：PC-1 + NC-1..22 + NC-15b + **NC-23..56**（含 **NC-43..46**：顶层 model 写错 / 分母混类 / prompt 盲填授权 / MSR 口径未声明；**NC-47 四向**：榜单缺字段级列、分母不等却硬填可减、dev 翻转未闭合、翻转列表清空；**NC-48 三向**：消融判采纳但 sha 未换 / 判否决却已换 / 缺 decision；**NC-49 四向**（R58/S-44）：INDEX 的 ⓪ 段指回 C-029 / NC 区间回退 / 去掉历史标记 / 锚点缺失；**NC-50 两向**（R59/S-45）：C-019 记录 mtime 过期 / 文件时间反序；**NC-51 两向**（R60/S-46）：dataset 命令裸 `python` / 缺 `PY=`；**NC-52 两向**（R61/S-47）：求解锁逻辑被抹掉 / 残留 `.solve.lock`；**NC-53 四向**（R62/S-48）：C-003 的 field 计数漂移 / scalar-disp 退回旧值 / field 构成不闭合 / 删掉「不说 N/N」分母；**NC-54 十向**（R63/S-49 + R64/S-50 + R63/S-51）：C-001 规模漂移 / C-002 minJ 写错 / C-004 通过数减 1 / C-005 删 dup 锚点 / 删整行 C-036 / 对外表分母混写 55 / 删「分母口径」列 / 手改一格数字 / 协议文件写死三元组 / 协议文件写死负控数）；**NC-55 三向**（R65/S-52）：当前卷不一致 / 已发布 NL 被改写 / 跨版改老行；**NC-56 四向**（R66/S-53）：L2 双口径缺 `clarify_informative` 块 / 掩码过期 / 允许相减 / 只报一侧分）= **58/58** |
| T1 检索地板 | `trivial_baselines_L3.json`（v4）/ `trivial_baselines_L3_v6b.json` / **`trivial_baselines_L3_v6c.json`（当前）** | `value_added` 的对照项：v4 exam T1 = 0/11；v6c exam **T0 0/25 · T1 0/25 · T2 25/25**。**R40：T1 已 leave-one-out**，`t1_leave_one_out=true`、`T1_self_hit` 0 条（旧版 train 12/13 全是 `T1_nn == task_id`，地板是稻草人）。**R44 新增两档**：`T1plus_family`（**逐字段族级众数**，不读输入的最强策略，众数只在 train 池取）exam **0/25**、但**字段命中率 85.93%**、缺口 min **1** / 中位 **3** / max **5** 字段；`T1plus_family_oracle`（族内 train 池覆盖力**上界**，需知道答案才能选 ⇒ 只报不判）exam **0/25** |
| MSR 明细 | `msr_l3_v4.json` / `msr_l3_v5_rescore.json` ／ 当前版本直接并入成绩单 `msr` + `exam.msr` 节 | 逐任务门禁 + 失败分层（env/contract/model/**solver**，R16/R35）；v4 = 11/21、exam 4/9。**R35：原始口径（含 solver）与剔除口径必须并列** ⇒ `exam_msr` / `exam_msr_excl_solver` / `dev_msr` / `dev_msr_excl_solver` 四行 + 全链 `msr` / `msr_excl_solver`，并标 `solver_in_exam` / `solver_in_dev`。**顶层 `msr` 键 W5c 起才落值**（此前一直是 null，NC-36 抓到）。**R45：九个字段必须全非空** —— `exam_msr` / `exam_msr_excl_solver` / `dev_msr` / `dev_msr_pct` / `dev_msr_excl_solver` / `msr` / `msr_excl_solver` + 别名 `full_msr_excl_solver`(≡`msr_excl_solver`, 38/47) / `full_msr_excl_solver_pct`；别名由同一变量写出（`full_msr_excl_solver` / `dev_msr_pct` 此前是**缺键**，S-31 守） |
| bootstrap CI | `bootstrap_ci_L3_v4.json` / `_v5_rescore.json` / `_v6b.json` / **`_v6c.json`（当前）** | exam 任务重采样（B=4000, seed=20261025）：TSR/SFR/MSR 点估计 + CI95 + by_family + **by_stratum（三栏，只报不判）**。v6c：TSR 92.0% **[80.0, 100.0]**、SFR 90.9% **[77.3, 100.0]**；分族 open_hole 75.0% **[25.0, 100.0]**、wingbox 94.4% **[83.3, 100.0]** |
| 考卷快照 | `papers/tasks_v4.jsonl` / `tasks_v5.jsonl` / `tasks_v6.jsonl`（作废留档）/ `tasks_v6b.jsonl` / **`tasks_v6c.jsonl`（当前考卷，sha `9c1faa3a…`）** + `nl_human_*.jsonl` + `SHA256SUMS` | v4 = `git show 28e66bb:` 逐字节；v5 = tag `v1.0-l3-v5`；v6b = tag `v1.0-l3-v6b`（历史卷）；v6 原稿不删（D10）；**v6c = v6b + 10 行（C-030）**；sha256 见 `papers/SHA256SUMS` |
| 自检输出 | `check_claims.json` | `check_claims.py` 的逐条结果（sha256 + mtime） |

## 2. 复现命令（一条一条贴，照抄可跑）

> **★ 前置：复现是两步**（W5a' clean-clone 实测）。`git clone` 只有考卷+候选+产物，
> **数据集本体 `FEM-Bench-Aero/modeling/` 不在 git**（发布策略：由 `fetch_data.py` 解包分发）。
> 缺 gold 时 `spec_fidelity` 会把**全部候选判成 spec_fail**，成绩单显示 `0/11`——看起来像模型全错。
> 现已加 `require_dataset()` 前置闸（rc=2 硬报错，NC-26 咬它），但解包这一步必须做：
>
> ```bash
> python fetch_data.py --src "F:/FEA_Archive_20261024/FEM-Bench-Aero-v1.0-data.tar.gz"
> # [OK] SHA256 校验通过；modeling 目录条数 55（manifest 期望 55）
> ```
>
> 解包后 `score_baseline.py` 才能复现 C-021 的 5/11（已实测：clone + fetch_data ⇒ 与 main 工作区逐项一致）。

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"   # gmsh 在这个 venv

# ⓪ 前置闸（考卷 v6c 通用，**与 headline 无关**）——先跑这三条就够
"$PY" r32_audit.py --tasks reports/papers/tasks_v6c.jsonl --scope exam --out reports/r32_audit_v6c_exam.json   # 必须 rc=0（R33）
"$PY" audit_contract.py --tasks reports/papers/tasks_v6c.jsonl --out reports/contract_audit_v6c.json            # gold 55/55 可建（§7.4）
# ★ --out 是相对 --out-dir 的：旧写法 `--out reports/xxx.json` 会落到 eval_runs/reports/（R37 踩过）
"$PY" trivial_baselines.py --levels L3 --tasks reports/papers/tasks_v6c.jsonl --out trivial_baselines_L3_v6c.json --out-dir reports

# ⓪v11 v1.1 数据层校验（**必须走 $PY = 项目 venv**：系统 python 缺 numpy/gmsh，见 R60/S-46）
"$PY" verify_dataset.py --root ../FEM-Bench-Aero        # ✅ 2026-10-28 双码闭合后：64 paired / VERDICT: PASS
"$PY" eval_dataset.py   --root ../FEM-Bench-Aero        # 含 D12 复现断言
"$PY" dedup_dataset.py  --root ../FEM-Bench-Aero        # 目标 0 重复
"$PY" check_forms.py --json reports/check_forms_v11.json # 串行；R61 全局锁已落（并发会抛错，不会静默空转）
"$PY" _v11/verify_v11_interpolation.py --strict         # 内插夹逼 7/7；不依赖 gold
# ⓪-hist（**historical，不是当前 headline**）：C-029 / prompt v1 代 / `candidates_l3_v6c`
#   当前 headline 见 §1（C-032，prompt v2 代）。本段只服务于 prompt_v2_effect_glm 消融复现；
#   两代 prompt sha 不同（C-029 那批未记录 = UNKNOWN）⇒ 按 R53 **不得把 C-029 与 C-032 并列作成绩**。
"$PY" score_baseline.py --candidates candidates_l3_v6c \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c.json \
  --trivial reports/trivial_baselines_L3_v6c.json --label "C-029 v6c (paper v6c, candidates v6c)"
"$PY" msr_l3.py --candidates candidates_l3_v6c \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c.json      # 全链 ccx，串行，约 25–40 min
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c.json --out reports/bootstrap_ci_L3_v6c.json

# ⓪b 第二模型（C-031，**prompt v1 代 = historical**，同考卷 v6c × candidates_l3_v6c_dsv4pro）
#    supporting 非 headline（R48）；**与 C-032/C-033 不可拼比**（R53）——首次 R53 合规的跨模型对比是 C-033
node _probe_models.js --out reports/diagnostics/models_available.json    # 实测可用模型 id（35 个，R13 不猜）
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 \
  --out candidates_l3_v6c_dsv4pro --limit 55 --model deepseek-v4-pro --max-turns 3      # 9 min
"$PY" score_baseline.py --candidates candidates_l3_v6c_dsv4pro \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_dsv4pro.json \
  --trivial reports/trivial_baselines_L3_v6c.json --label "C-031 v6c x dsv4pro (paper v6c, candidates dsv4pro)"
"$PY" msr_l3.py --candidates candidates_l3_v6c_dsv4pro --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_dsv4pro.json      # 全链 ccx，串行
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c_dsv4pro.json --out reports/bootstrap_ci_L3_v6c_dsv4pro.json
"$PY" _diag_model_diff.py --a reports/baseline_scorecard_L3_v6c.json \
  --b reports/baseline_scorecard_L3_v6c_dsv4pro.json \
  --out reports/diagnostics/model_diff_v6c_dsv4pro.json --md reports/diagnostics/model_diff_v6c_dsv4pro.md   # 先过 R30 闸，不可比 rc=3

# ===== prompt v2 代（W5c-6d，R50 修复后重跑；**当前官方 headline = C-032**）=====
# 先看 SYS prompt 的 sha（不跑模型，防「改完不知 sha 变没变」）
node gen_candidates_v2.js --print-prompt-sha        # 期望 ce225186…（v1 那代未记录 = UNKNOWN）
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 \
  --out candidates_l3_v6c_glm_p2 --limit 55 --model glm-5.3-flash --max-turns 3        # C-032，约 14 min
"$PY" score_baseline.py --candidates candidates_l3_v6c_glm_p2 \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_p2.json \
  --trivial reports/trivial_baselines_L3_v6c.json --label "C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2)"
"$PY" msr_l3.py --candidates candidates_l3_v6c_glm_p2 --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_p2.json      # 全链 ccx，串行，约 37 min
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c_p2.json --out reports/bootstrap_ci_L3_v6c_p2.json
# prompt 消融（同模型同卷，唯一变量 = prompt；R53：只能作 ablation，不能并列作成绩）
"$PY" _diag_model_diff.py --a reports/baseline_scorecard_L3_v6c.json \
  --b reports/baseline_scorecard_L3_v6c_p2.json --allow-incomparable \
  --out reports/diagnostics/prompt_v2_effect_glm.json --md reports/diagnostics/prompt_v2_effect_glm.md

# 第二模型同 harness（C-033，与 C-032 才构成有效跨模型对比）
node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 \
  --out candidates_l3_v6c_ds_p2 --limit 55 --model deepseek-v4-pro --max-turns 3        # C-033
"$PY" score_baseline.py --candidates candidates_l3_v6c_ds_p2 \
  --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_ds_p2.json \
  --trivial reports/trivial_baselines_L3_v6c.json --label "C-033 v6c x dsv4pro prompt-v2 (paper v6c, candidates ds_p2)"
"$PY" msr_l3.py --candidates candidates_l3_v6c_ds_p2 --tasks reports/papers/tasks_v6c.jsonl \
  --report reports/baseline_scorecard_L3_v6c_ds_p2.json      # 全链 ccx，串行
"$PY" bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c_ds_p2.json --out reports/bootstrap_ci_L3_v6c_ds_p2.json
"$PY" _diag_model_diff.py --a reports/baseline_scorecard_L3_v6c_p2.json \
  --b reports/baseline_scorecard_L3_v6c_ds_p2.json \
  --out reports/diagnostics/model_diff_v6c_p2_glm_vs_ds.json --md reports/diagnostics/model_diff_v6c_p2_glm_vs_ds.md

# ===== W5d 榜单 + W5d-0 dev 反向定位（R55/R56）=====
"$PY" _diag_dev_reversal.py          # dev 23 + 1 - 2 = 22，闭合断言
"$PY" _diag_prompt_ablation.py   # prompt 消融（v2/v3/v3b 三版 × 2 模型 × 7 条）
"$PY" make_w5d_leaderboard.py        # 三列并排；MSR 分母不等时不出 Δ
"$PY" check_claims.py                # S-41 / S-42



# ① 上一代官方 headline（C-021，考卷 v4 × 候选 v4）
"$PY" score_baseline.py --candidates candidates_l3_v3 \
  --tasks reports/papers/tasks_v4.jsonl \
  --report reports/baseline_scorecard_L3_v4.json \
  --trivial reports/trivial_baselines_L3.json --label "C-021 official"
"$PY" msr_l3.py --candidates candidates_l3_v3 \
  --tasks reports/papers/tasks_v4.jsonl \
  --report reports/baseline_scorecard_L3_v4.json      # 全链 ccx，串行，约 10–30 min

# ② 诊断（C-025，旧候选 × v5 考卷）
"$PY" score_baseline.py --candidates candidates_l3_v3 \
  --tasks reports/papers/tasks_v5.jsonl \
  --report reports/baseline_scorecard_L3_v5_rescore.json

# ③ 负控 + CLAIMS 自检（每个 W 块收口必跑）
PYTHONIOENCODING=utf-8 "$PY" negative_controls.py
"$PY" check_claims.py            # 结构（R25/R26/R27）+ 语义计数（R29），默认都开

# ④ 跨口径比较闸（R30/R39）：不同口径/不同题面的两份成绩单必须被拒（rc=3）
"$PY" compare_scorecards.py --a reports/baseline_scorecard_L3_v6b.json \
  --b reports/baseline_scorecard_L3_v6c.json   # 同 25 条 exam id 但 paper sha 不同 ⇒ 必须 rc=3
```

## 3. 版本对照表

| 版本 | 考卷 | 候选目录 | 生成器 | 状态 |
|---|---|---|---|---|
| v3 | 考卷 v3（b2e9b74） | `candidates_l3_v2` | gen_candidates_v2.js | 历史（C-020 superseded） |
| **v4** | 考卷 v4（28e66bb，`papers/tasks_v4.jsonl`） | `candidates_l3_v3` | gen_candidates_v2.js | **官方（C-021）** |
| v5 | 考卷 v5（tag `v1.0-l3-v5`，`papers/tasks_v5.jsonl`） | 同 v4（**只重打分**） | — | **诊断（C-025）** |
| v6（作废） | 考卷 v6（tag `v1.0-l3-v6`，`papers/tasks_v6.jsonl`）：内插名额 2/2/1/1 ⇒ 三族 train 被抽空 | — | — | **作废**（T1 地板只有 1/4 族可算）；原稿留档不删（D10） |
| **v6b** | 考卷 v6b（tag `v1.0-l3-v6b`，`papers/tasks_v6b.jsonl`，55 条 L3 / exam 25 三栏，内插全翼盒） | `candidates_l3_v6` | gen_candidates_v2.js | **已跑出成绩但降级为 diagnostic lower bound（C-027 + C-028）**；含 8 处已知缺陷，不得对外 |
| **v6c** | 考卷 v6c（`papers/tasks_v6c.jsonl`，sha `9c1faa3a…`）：v6b → v6c **只改 10 行**（4 条 NL 补 R32 缺项 + 6 条 `split_v2` 改 `interpolation_test`），L1/L2 110 条与其余 45 条 L3 **逐字节不变** | `candidates_l3_v6c` | gen_candidates_v2.js（SYS prompt 补键名表，R34） | **官方考卷（C-030）**；R32 审计 4→**0 违规**，`_verify_tasks_v6c.py` 20/20 PASS |
| **v6c × dsv4pro** | **同一份** `papers/tasks_v6c.jsonl`（sha `9c1faa3a…` 与 v6c **逐字节相同**） | `candidates_l3_v6c_dsv4pro` | gen_candidates_v2.js `--model deepseek-v4-pro --max-turns 3 --limit 55`（9 min） | **supporting 第二模型（C-031）**：exam TSR **20/25 (80.0%)**、SFR 20/25、dev 22/30；**`spec_pass` 与 C-029 同为 20/25，2 条 `spec_fail` 同题同字段**；唯一差异是 3 条澄清题（glm 澄清 3/3 vs 本模型编造 3/3）。**不作 headline（R48：不得事后择优）** |
| **v6c × dsv4pro（prompt v2）** | 同 `papers/tasks_v6c.jsonl`（sha `9c1faa3a…`） | `candidates_l3_v6c_ds_p2` | gen_candidates_v2.js（`prompt_sha256 ce225186…`） | **C-033 = 当前第二模型（同 harness，R53 合规）**：exam 22/25 (88.0%)、MSR 20/21（条件分母）、full 42/50 |
| **W5d 榜单（C-034）** | 同 `papers/tasks_v6c.jsonl` | `candidates_l3_v6c_glm_p2` + `candidates_l3_v6c_ds_p2` | gen_candidates_v2.js（`ce225186…`） | **协议层产物**：三列并排 + 2×2 + 禁用句式 + 限制；不含新模型成绩 |

> `papers/tasks_v4.jsonl` 是 `git show 28e66bb:feagpt_repro/tasks/tasks.jsonl` 的逐字节快照。
> 用它（而不是 `_bridge_v3/tasks/`）才能复现 C-021 的 dev TSR 11/19 与「问错字段 0」；
> 用 `_bridge_v3/tasks/` 打出来是 dev 10/19、问错字段 1（exam 恰好同为 5/11），**不可混用**。

## 4. 红线对照

| 红线 | 落点 |
|---|---|
| R25 官方 artifact 必须入库（非 `eval_runs/`） | 本目录；`check_claims.py` 检查 git 追踪 |
| R26 CLAIMS 自检必须进 CI | `check_claims.py`（结构 + **`--semantic` 语义计数**，rc=1）+ NC-23..29 |
| R27 官方 vs 诊断必须分文件 | `_v4` / `_v5_rescore` 两个文件；`check_claims` 检查同路径占用 |
| R28 旧候选不得评新考卷 | C-025 标 diagnostic；W5b 必须重生成 |

## 5. W5a' 验收记录（2026-10-25，专家第六轮 P0-1/P0-2/P0-3）

| 验收项 | 结果 |
|---|---|
| C-021 可复现 | 重跑 `score_baseline.py --tasks papers/tasks_v4.jsonl` ⇒ **exam TSR 5/11 (45.5%)、SFR 5/10、dev 11/19、问错字段 0**，与 C-021 文本**逐项一致** |
| C-021 全链 MSR 可复现 | `msr_l3.py --tasks papers/tasks_v4.jsonl` ⇒ **MSR 11/21 (52.4%)、exam 4/9、dev 7/12**（失败分层 model 7 + contract 3，env 0），与 C-021 的 4/9 一致；实耗 18 min（两个 barrel 案各 362/468 s） |
| CI 落地 | `bootstrap_ci.py` ⇒ exam TSR 45.5% **CI95 [18.2, 72.7]**；SFR 50% [20.0, 80.0]；MSR 44.4% [11.1, 77.8] —— n=11 的区间宽度就是「为何不得对外承诺」的量化证明 |
| CLAIMS 自检 | `check_claims.py`：**22 条 active claim / 34 个 artifact / 32 项语义检查**，逐条查存在 + 追踪 + 路径一致 + sha256 + **语义计数（R29）** |
| 负控 | **44/44**（NC-23/24/25 注入临时 CLAIMS 打结构检查；NC-26 缺 gold 硬报错；NC-27 文本计数漂移被语义检查抓到；NC-28 候选未覆盖全卷被标记；NC-29 跨口径混比被拒） |

### ★ 两个新踩到的坑（已修，写进这里防复发）

1. **`_bridge_v3/tasks/tasks.jsonl` ≠ 考卷 v4**。它是 b2e9b74 的 v3 考卷（无 `coordinate_convention`、ec 集也不同）。
   用它打出来 exam 恰好也是 5/11，但 **dev 是 10/19、问错字段 1**，与 C-021 的 11/19、0 **不符**。
   正确复现必须用 `papers/tasks_v4.jsonl`（`git show 28e66bb:`）。**「总数对上了」不等于「复现对了」**。
2. **NC-21 跨卷核对 = 假红**。负控原先用「当前 `tasks.jsonl` 的澄清题清单」核对成绩单分母；
   v4 成绩单的卷子里 str3 不是澄清题（600x600 才是），于是报 `L3_stiffened_panel_600x600_str3` 混进分母。
   修法：负控按成绩单自带的 `provenance.tasks_path` 回读**它当时那张卷子**再核对。
   （同源教训：任何「拿现态去判历史产物」的检查都会假红或假绿。）

## 6. W5b-3 验收记录（2026-10-25，专家第七轮 P1-1..P1-7）

| 验收项 | 结果 |
|---|---|
| 文档语义计数（P1-1..P1-4） | C-010 **165**（L1 55 + L2 55 + L3 55）、C-011 内插 = **v6 interp 6**、C-019 coverage **31**、C-027/RUBRIC/W5B_PLAN 的「C-021 的 N 条」统一为 **11**（另两数 19 / 25 分列）；README 的 RUBRIC 版本统一 **v4** |
| 语义自检（P1-5/R29） | `check_claims.py --semantic`（**默认开**）：**29 项**逐条核对文本数字 vs artifact 实读 ⇒ 全过（W5c 收口实测 22 claims / 34 artifacts / 29 语义）。S-01..S-20 覆盖 行数/内插/负控/exam 条数/三栏/跨文档「C-021 的 N 条」/RUBRIC §1 三行/README 版本与负控数/**S-17..S-20 与 S-23..S-26·S-28 现指向 C-029**（TSR/三栏/SFR/全链 MSR·exam MSR/R38 文案/R36 by_split/覆盖分解/id 集）、S-22 仍校 C-028；**W5c 新增 S-21..S-28**（内插族=wingbox 6 / 消歧计数 26·25 / R38 文案由考卷生成 / by_split 纯 dev / SFR 14/21 / 覆盖与产出分解 / R37 git 追踪 / exam id 集逐 id 相等） |
| 负控（R29/R30/R31/R33–R49） | **44/44**（W5c 起）：NC-27 注入 C-010「140 行」⇒ 语义检查 FAIL（先断言替换命中，防静默空转）；NC-28 候选 30/55 ⇒ `scorecard_coverage_problems` 报 3 条；NC-29 v6(25) vs C-021(11) 混比 ⇒ `comparability` 拒（4 条理由），同文件自比仍可；**W5c 新增 NC-30（R33 考卷冻结闸：抽掉考卷里 web1 的腹板句 ⇒ R32 必须报 VIOLATION，含 `web_chordwise`）/ NC-31（R34 从 `GRADED_FIELDS` 实读键名比对 SYS prompt + 禁键明示）/ NC-32（R40 源码过滤 + `t1_leave_one_out` + 无 `T1_self_hit`）/ NC-33（R38 成绩单文案由考卷生成）/ NC-34（R37 官方文档不引 `eval_runs/` 具体文件）/ NC-35（R39 同条数不同 task-id 集必须拒）** |
| 成绩单覆盖记账（R31） | 成绩单新增 `n_tasks_in_paper` / `candidates_missing` / `partial_candidates`；v6b 显示「覆盖 **55/55** 条（完整）」，`partial_candidates=false` |
| 跨口径闸（R30） | `compare_scorecards.py`：口径不同 ⇒ **rc=3 拒绝**且只打印三栏、不给任何「提升/下降」（v4 vs v6b 实测 rc=3，4 条理由：exam 11 vs 25、分层构成、boundary 4 vs 6、extrap 7 vs 13） |
| 考卷 v6b 状态 | **冻结并已跑出成绩**（C-027 + C-028）；`candidates_l3_v6` 55/55 已入库 |

### key 的出处（W5b-0 已解决，勿再当阻塞）

`WORKBUDDY_PUBLISHABLE_KEY` **不是模型厂商 key**，是 WorkBuddy 云服务应用「FEM基线评测」
（`wbapp_Tl8jf0GeqRmnK59Hr64PuS`）的 `publicConfig.publishableKey`（`wbpk_` 前缀、无权限语义）。
取法：`workbuddy_cloud_service` → `action=activate` + `mode=reuse` + 该 appId（`inspect` 不返回 key）。
**已 `setx` 进用户级环境变量**（新开窗口生效）。`.env` 文件无效（脚本不装 dotenv）。
**仍不要**把 key 写进仓库或对话（R31 精神）。

### W5b 遗留缺陷的处置（W5c 已逐条闭环，2026-10-25）

| 编号 | 缺陷 | 处置 | 状态 |
|---|---|---|---|
| A 类 | 生成器 SYS prompt 未列开孔板 `hole_d/hole_x/hole_y/layup` 键名 ⇒ exam 开孔板 4/4 全败 | **R34**：prompt 加「四族键名总表」+ 禁用键；重生成 | **已修**：exam 开孔板 **0/4 → 3/4**（余 1 条是 `layup` 写成标量，模型侧） |
| B 类 | `stringer_flange_width` gold 有值但题面未给（`str3_T`）；3 条 web 题面**完全没提腹板** | **R32**：v6c 补 4 条题面依据（只做 insert，不改写） | **已修**：v6c R32 主判据违规 4 → 0 |
| C 类-1 | `blade` 剖面 `stringer_flange_width` 是死字段，却被判 | **§7.2** 死字段登记（用 gold 的 `stringer_kind` 判，不用候选的） | **已修**：bridge A→B 唯一翻转 `wingbox_str5` |
| C 类-2 | `extra.end_torque` 等自创键被判错，RUBRIC 未定义「多余键」 | **§1.1.1 / §7.1**：自创键一律判错（载荷机制多写 = 编造机制），并非口径漏洞 | **定案**：`web1_offcentre` 剩余失败属模型侧，保留 |
| **新发现** | 加筋板题面 `{width} × {length}` 与 gold 角色相反（R32 盲区） | **R41 + §7.3**：单列「字段角色可判」闸；模板改显式标注 | **已修模板**；v6c 候选不重生成 ⇒ 2 条 dev 记为已知下界 |
| solver | **4 条**柱壳（143k / 158k×2 / 169.6k 节点）超本机内存（阈值 158,548），**1 条在 exam、3 条在 dev** | **R35**：MSR 原始/剔除双口径四行分列，不算模型能力；**桶归属随候选变** | 算力边界，非卷子缺陷 |

明细：`reports/diagnostics/w5b4_defect_analysis_v6b.md`（探针 `_probe_w5b4_fail_fields.py` 可复跑）。
**R37：官方文档一律不引 `eval_runs/`**，诊断材料统一放 `reports/diagnostics/`。

## 7. W5c 修复轮验收记录（2026-10-25，专家第八轮 §3/§6）

| 验收项 | 结果 |
|---|---|
| R32/R41 审计（R33 闸） | `r32_audit.py`：v6b all = **8 违规** → v6c all = **4 违规**（全在 dev：`stiffened_panel_800x600` / `_str3`，R41）→ **v6c exam = 0 违规（rc=0）**。三份 artifact：`r32_audit_v6b_before.json` / `r32_audit_v6c.json` / `r32_audit_v6c_exam.json` |
| 考卷 v6c 冻结 | `_verify_tasks_v6c.py` **PASS**：改动行数 == 10、L1/L2 110 条逐字节、题面只做 insert（difflib opcodes ⊆ {insert}）、exam 25 = 6/13/6、纯 train 13、R33 两端守 |
| T1 地板（R40） | leave-one-out 后 v6c exam **T1 0/25**、train 池 13 条**无自命中**（旧 v6b train 12/13 全部 `T1_nn == task_id`）；T0 0/25、T2 25/25 |
| 成绩单口径（R36/R38/R39） | `exam_definition` 由考卷生成（含 'exam_stratum'）、`note` 无 W4d 旧串、`by_split` 纯 dev（train 13 + val 17 = 30）、`exam_task_ids_sha256` + `exam_by_family` 落盘；`by_stratum` 键名与考卷一致 |
| 负控 | **44/44**（NC-30 改两端守：exam 0 + 非 exam 白名单逐字相等 + 反向抽依据必被抓；NC-33 自动读最新成绩单；NC-34 `eval_runs/` 清零） |
| bridge 四格 | `reports/diagnostics/bridge_w5c_table.md`：A 17/25 → B 18/25（判分修正 +1）→ C 18/25（**考卷修复对定型候选 +0**）→ D 23/25（重生成 +5）。`bridge_w5c_B/C_*.json` 为诊断产物，**不得当成绩**（R28） |
| 文档同步 | RUBRIC **v4.7**（R33–R49 + §7.3/§7.4/§7.5/§7.6）、CLAIMS **R1–R49**（C-019 41/41、C-030 两端口径）、README/INDEX/W5B_PLAN 同步 |

### 7.1 W5c-6b 收口轮验收（2026-10-25，专家第九轮 4 个 P1）

| 第九轮问题 | 处置 | 实证 |
|---|---|---|
| **P1-1 headline 文档漂移** | README 两处改 C-029；C-021/C-025/C-026 历史化（「已被 C-029 取代」）；INDEX 109–110 旧计数改 22/34/33；W5B 79 改 32 项；**新增 S-29（headline 唯一）** | S-29 首跑抓到 `["C-021"]`（FAKE PASS），改文档后过；**NC-38 反向**：给 C-021 状态列注入自指标记 ⇒ S-29 必红 |
| **P1-2 dev 25/30 是投影** | C-029 与 bridge 表改「**23/30 实测 + paper-clean 投影 25/30 + 5 条模型侧失败仍在**」；**新增 S-30** | S-30 首跑抓到 C-029 缺「投影」字样 |
| **P1-3 T1+ 仍是 null** | `trivial_baselines.py` 新增 **`T1plus_family`**（逐字段族级众数）与 **`T1plus_family_oracle`**（只报不判）；`value_added` 增**字段级**尺度；**新增 S-32** | **T1+ exam 0/25 但字段命中率 85.93%**、缺口 min 1 / 中位 3 / max 5；**oracle 0/25** ⇒ 「0 地板」是全或无判据的必然；**字段级 85.93% → 99.34%（Δ+13.4 pp）** |
| **P1-4 key 只止血未轮换** | 复核「轮换 ⇒ endpoint 变 ⇒ provenance 重签」这一成本判断，写 `W5B_PLAN §6.0b` | **判定为错两处**：endpoint 是 `gen_candidates.js:10` 硬编码常量、`provenance` 不含 key/endpoint ⇒ 轮换本身**不需要重签**。同应用轮换是否可行**未验证**（未做轮换操作） |
| P2-1 MSR 别名 null | 补 `dev_msr_pct` / `full_msr_excl_solver`（由同一变量写出）；**新增 S-31** | 九字段全非空、别名 38/47 逐字相等 |
| P2-5 旧负控并存 | INDEX 标 `_39/_37/_31` 为**历史快照，不得引用** | 现状 41 为当前 |
| 门禁 | `check_claims` **23 条 active / 35 artifact / 36 语义项全过**；负控 **44/44**；`_verify_tasks_v6c` PASS | 新增 NC-38（headline 反向）/ NC-39（T1+ 反向两向） |

### 7.2 W5c-6c 跨模型轮验收（2026-10-25，W5b-5 第二模型）

| 项 | 处置 | 实证 |
|---|---|---|
| **模型 id 实测** | `_probe_models.js` 打 `llm.models.list()` | 服务端 **35 个** id；`deepseek-v4-pro` 在其中（R13 不猜） |
| **同卷约束** | 同一份 `tasks_v6c.jsonl` | `tasks_sha256` = `9c1faa3a…` 与 C-029 **逐字节相同** |
| **生成** | `--limit 55 --model deepseek-v4-pro --max-turns 3` | 55/55（9 min），`turns {2:52, 3:3}`，`clarify` **0 条**、`n_unresolved=1` |
| **打分** | `score_baseline.py --candidates candidates_l3_v6c_dsv4pro` | exam **TSR 20/25 (80.0%)**、SFR 20/25、dev 22/30；三栏 6/6 · 9/13 · 5/6 |
| **MSR** | `msr_l3.py`（不 `--reuse`，真起 ccx） | exam **20/22**、dev 22/28、full **42/50**；**`n_solver_excluded=0`**（C-029 是 4） |
| **CI** | `bootstrap_ci.py` 两份 | C-031 TSR **[64.0, 96.0]**、SFR [64.0, 96.0]、MSR **[77.3, 100.0]** |
| **跨模型诊断** | `_diag_model_diff.py`（先过 R30 闸） | exam 2×2 = both **20** / only_a **3** / only_b **0** / neither **2**；共同失败 2 条**字段集全同** |
| **口径 bug（新发现）** | 字段级命中率静默排除编造题 | 修前两份都是 **99.34%**（假象）；修后 C-029 不变、C-031 → **87.42%**（Δ+1.5 pp，BELOW） |
| **新红线** | R47 分母显式 / R48 不得择优 / R49 分裂标出 | S-33/S-34/S-35 + NC-40/41/42 |
| **门禁** | `check_claims` **23 claims / 35 artifacts / 36 语义项全过**；负控 **44/44** | 新增 NC-40/41/42 各一条反向 |

**★ 本轮的真正产出不是 80.0% 这个数，而是三条归因结论**（详见 CLAIMS C-031）：

1. **`spec_pass` 两模型都是 20/25** ⇒ 「92.0% vs 80.0%」不来自建模能力；
2. **两条 `spec_fail` 同题同字段**（`extra.end_torque`+`torque_axis_dof`、`layup` 标量），dev 侧 `stiffened_panel_800x600`/`_str3` 的 `length`/`width` 也是**两模型同错**（R41 题面缺陷）⇒ **失分主因是题面/prompt，不是模型差异**；
3. **唯一实质差异 = 缺失信息处理**（glm 澄清 3/3 vs dsv4pro 编造 3/3），其中 `n_stringers=0` **由 SYS prompt「未提长桁→长桁数=0」直接授权** ⇒ **我方 prompt 与题面冲突，下一轮必修**。

**★ 反直觉点（必须一并读）**：C-031 的 **exam MSR 90.9% > C-029 的 86.4%**，而 TSR 低 12 pp。
原因是 MSR 分母 22 **排除了 4 条 clarify 题**，而 C-031 编造的 3 条**恰好全在这 4 条里** ⇒ 它最差的 3 条被排除在 MSR 之外。
**TSR 与 MSR 分母不同（25 vs 22），排名可以相反，不得互相替代。**

