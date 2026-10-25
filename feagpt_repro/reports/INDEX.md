# reports/ — 官方产物索引（W5a'，红线 R25/R27）

> **为什么有这个目录**：`feagpt_repro/eval_runs/` 被 `.gitignore` 排除（第 52 行），
> 官方数字放在那里 ⇒ 新 clone 只能看到命令看不到文件，重跑即覆盖（C-021 的 v4 成绩单
> 已被 v5 重打分覆盖，第六轮复评才发现）。本目录**入库**，文件名带版本，作为唯一官方出处。
> **纪律**：诊断结果不得占用官方路径（R27）；文件改名/覆盖必须更新本表与 `CLAIMS.md`。

## 1. 一句话读法

| 用途 | 文件 | 口径 |
|---|---|---|
| **官方 headline（对外唯一可引用）** | `baseline_scorecard_L3_v4.json` | C-021：考卷 **v4** × 候选 **v4**（`candidates_l3_v3`），exam 11 条 **TSR 5/11 (45.5%) / SFR 5/10 / MSR 4/9**，**n=11 UNDERPOWERED**；CI95 见 `bootstrap_ci_L3_v4.json`（TSR **[18.2, 72.7]**） |
| **诊断（不是模型成绩）** | `baseline_scorecard_L3_v5_rescore.json` | C-025：**旧候选**（v4 生成）打 **v5** 考卷 ⇒ exam TSR 4/11。旧候选不能评新考卷（R28），只用于验证「修题改了什么」 |
| L1 冒烟（非模型基线） | `baseline_scorecard_L1_smoke.json` | C-017：spec-copy 19 条 SFR 0/19，无 schema 约束解码时的指令遵循失败 |
| 桥接表 | `bridge_v3_v4.json` + `bridge_A/B/C_*.json` | C-024：A 7/11、B 5/11、C 0/11、D 5/11；A→D = −3 wingbox 方向 +1 d2000 |
| 负控 | `negative_controls_27.json` | C-019：PC-1 + NC-1..22 + NC-15b + **NC-23..25** = **27/27** |
| T1 检索地板 | `trivial_baselines_L3.json` | `value_added` 的对照项（exam T1 = 0/11） |
| MSR 明细 | `msr_l3_v4.json` / `msr_l3_v5_rescore.json` | 从对应成绩单抽出的 `msr_section`（逐任务门禁 + 失败分层；v4 = 11/21、exam 4/9） |
| bootstrap CI | `bootstrap_ci_L3_v4.json` / `bootstrap_ci_L3_v5_rescore.json` | exam 任务重采样（B=4000, seed=20261025）：TSR/SFR/MSR 点估计 + CI95 + by_family（**n<20 不得据此判 PASS**） |
| 考卷快照 | `papers/tasks_v4.jsonl` / `papers/tasks_v5.jsonl`（+ `nl_human_*`、`SHA256SUMS`） | v4 = `git show 28e66bb:` 逐字节；v5 = tag `v1.0-l3-v5`；sha256 见 `papers/SHA256SUMS` |
| 自检输出 | `check_claims.json` | `check_claims.py` 的逐条结果（sha256 + mtime） |

## 2. 复现命令（一条一条贴，照抄可跑）

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"   # gmsh 在这个 venv

# ① 官方 headline（C-021，考卷 v4 × 候选 v4）
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
"$PY" check_claims.py
```

## 3. 版本对照表

| 版本 | 考卷 | 候选目录 | 生成器 | 状态 |
|---|---|---|---|---|
| v3 | 考卷 v3（b2e9b74） | `candidates_l3_v2` | gen_candidates_v2.js | 历史（C-020 superseded） |
| **v4** | 考卷 v4（28e66bb，`papers/tasks_v4.jsonl`） | `candidates_l3_v3` | gen_candidates_v2.js | **官方（C-021）** |
| v5 | 考卷 v5（tag `v1.0-l3-v5`，`papers/tasks_v5.jsonl`） | 同 v4（**只重打分**） | — | **诊断（C-025）**，正式 v5 待 W5b 重生成 |

> `papers/tasks_v4.jsonl` 是 `git show 28e66bb:feagpt_repro/tasks/tasks.jsonl` 的逐字节快照。
> 用它（而不是 `_bridge_v3/tasks/`）才能复现 C-021 的 dev TSR 11/19 与「问错字段 0」；
> 用 `_bridge_v3/tasks/` 打出来是 dev 10/19、问错字段 1（exam 恰好同为 5/11），**不可混用**。

## 4. 红线对照

| 红线 | 落点 |
|---|---|
| R25 官方 artifact 必须入库（非 `eval_runs/`） | 本目录；`check_claims.py` 检查 git 追踪 |
| R26 CLAIMS 自检必须进 CI | `check_claims.py`（rc=1）+ NC-23..25 |
| R27 官方 vs 诊断必须分文件 | `_v4` / `_v5_rescore` 两个文件；`check_claims` 检查同路径占用 |
| R28 旧候选不得评新考卷 | C-025 标 diagnostic；W5b 必须重生成 |

## 5. W5a' 验收记录（2026-10-25，专家第六轮 P0-1/P0-2/P0-3）

| 验收项 | 结果 |
|---|---|
| C-021 可复现 | 重跑 `score_baseline.py --tasks papers/tasks_v4.jsonl` ⇒ **exam TSR 5/11 (45.5%)、SFR 5/10、dev 11/19、问错字段 0**，与 C-021 文本**逐项一致** |
| C-021 全链 MSR 可复现 | `msr_l3.py --tasks papers/tasks_v4.jsonl` ⇒ **MSR 11/21 (52.4%)、exam 4/9、dev 7/12**（失败分层 model 7 + contract 3，env 0），与 C-021 的 4/9 一致；实耗 18 min（两个 barrel 案各 362/468 s） |
| CI 落地 | `bootstrap_ci.py` ⇒ exam TSR 45.5% **CI95 [18.2, 72.7]**；SFR 50% [20.0, 80.0]；MSR 44.4% [11.1, 77.8] —— n=11 的区间宽度就是「为何不得对外承诺」的量化证明 |
| CLAIMS 自检 | `check_claims.py`：18 条 active claim / 19 个 artifact，逐条查存在 + 追踪 + 路径一致 + sha256 |
| 负控 | **27/27**（新增 NC-23/24/25，注入临时 CLAIMS 打 check_claims，不删真实文件） |

### ★ 两个新踩到的坑（已修，写进这里防复发）

1. **`_bridge_v3/tasks/tasks.jsonl` ≠ 考卷 v4**。它是 b2e9b74 的 v3 考卷（无 `coordinate_convention`、ec 集也不同）。
   用它打出来 exam 恰好也是 5/11，但 **dev 是 10/19、问错字段 1**，与 C-021 的 11/19、0 **不符**。
   正确复现必须用 `papers/tasks_v4.jsonl`（`git show 28e66bb:`）。**「总数对上了」不等于「复现对了」**。
2. **NC-21 跨卷核对 = 假红**。负控原先用「当前 `tasks.jsonl` 的澄清题清单」核对成绩单分母；
   v4 成绩单的卷子里 str3 不是澄清题（600x600 才是），于是报 `L3_stiffened_panel_600x600_str3` 混进分母。
   修法：负控按成绩单自带的 `provenance.tasks_path` 回读**它当时那张卷子**再核对。
   （同源教训：任何「拿现态去判历史产物」的检查都会假红或假绿。）

