# T-A14 交付报告 — L2 clarify 按族分层口径说明（R72 / S-60 / NC-66）

## 1. 任务 id + 单变量

- **task_id**: T-A14
- **单变量**: **无（纯派生 + 标注）** —— 不重跑模型、不改判据、不改分母、不改 prompt/paper。
  族级数字本来就完全由已入库的 `per_task[].{family,pass,name_leak}` 决定，本轮只把它**落盘 + 加闸**。

## 2. SOT（改前 / 改后）

| 项 | 改前 | 改后 |
|---|---|---|
| headline（唯一） | **C-032** | **C-032**（未动） |
| paper `tasks/tasks.jsonl` sha256 | `caf0f6c3be81…` | 同（未动，S-52 绿） |
| L2 prompt sha256 | `03129c56d83b…` | 同（未动） |
| rubric 版本 | v6.6 | **v6.7**（**只登记口径，判据一行未改**） |
| model | `glm-5.3-flash` / `deepseek-v4-pro` | 同（未重跑） |
| 分母 | 64 / 45 / 19 | 同（未动） |

## 3. 改了哪些文件（allowlist 对照）

| 文件 | 性质 | 是否在合同 allowlist |
|---|---|---|
| `score_l2.py` | `_block` 增 `by_family`；族级不闭合 `FATAL` 返回 rc=5；`_note` 写明两层同名词 | ✅ |
| `report_l2_clarify.py` | 透传 `by_family`（未跑满不透传）+ 逐块闭合断言 + md 增族级表 + 原写死数字改现算 | ✅ |
| `reports/l2_scores_v7_{glm,ds}.json` | 各 **+36 叶子（全为 `by_family`）**、`_note` 1 处；**删 0 / 其余 0 改动** | ✅ |
| `reports/l2_clarify_dual.json` | **+75 叶子**（3 个 `by_family_note` + 72 个族级）；**删 0 / 改 0** | ✅ |
| `reports/l2_clarify_dual.md` | 增「按族分层」表 + N-27 说明改为现算 | ✅ |
| `check_claims.py` | 新增 `l2_family_closure()` / `_family_text()` / **S-60** | ✅ |
| `negative_controls.py` | 新增 **NC-66 六向** | ✅ |
| `reports/negative_controls_68.json` | 新 artifact；`_67` 归档 | ✅ |
| `RUBRIC.md` | 新增 **R72** + 版本头 v6.7 + 版本历史行；**R70/R71 顺序摆回** | ✅ |
| `CLAIMS.md` | C-019 计数 67→68 + NC-66 描述；C-041 增「边界五」+ 命令补 `--label` | ✅ |
| `reports/INDEX.md`、`README.md` | 负控 68/68 · NC-23..66 · RUBRIC v6.7 · 族级出处 | ✅ |
| `reports/diagnostics/task_a14_{contract,report}.md` | 合同与本报 | ✅ |

**未动**（合同默认不改）：`judge_clarify_field_level`、`check_l2_leak.py`、任何分母、任何 L3 产物、headline。

## 4. 跑了哪些命令 + 实际输出

```bash
# pre-flight（R59 顺序，写临时 JSON 不动官方）
"$PY" negative_controls.py          # 67/67 ok（内容未变，未重写 —— F-1）
"$PY" check_claims.py --json "$TEMP/check_claims_preflight.json"   # 全过

# 重算（只派生，不跑模型）
"$PY" score_l2.py --cand candidates_l2_v7_glm --label "T-A13b v7 x glm L2 clarify" --out …
"$PY" score_l2.py --cand candidates_l2_v7_ds  --label "T-A13c v7 x ds L2 clarify" --out …
"$PY" report_l2_clarify.py --scores reports/l2_scores_v7_glm.json,reports/l2_scores_v7_ds.json --out … --md …
```

**逐叶子比对（构造性证据，R67）**

| artifact | 旧叶子 | 新叶子 | 新增 | 删除 | 改动 | 新增是否全在 allowlist |
|---|---|---|---|---|---|---|
| `l2_scores_v7_glm.json` | 659 | 695 | +36 | **0** | **1**（`/_note`，有意） | 是（全为 `by_family`） |
| `l2_scores_v7_ds.json` | 652 | 688 | +36 | **0** | **1**（`/_note`，有意） | 是 |
| `l2_clarify_dual.json` | 233 | 308 | +75 | **0** | **0** | 是（3 `by_family_note` + 72 族级） |

**六个既有数字逐数未变**：`49/64` · `30/45` · `19/19` · `36/64` · `21/45` · `15/19`。

**族级实读（落盘后）**

| 模型 | 族 | `clarify_all` | `informative` | `invalid` |
|---|---|---|---|---|
| glm-5.3-flash | wingbox | 24/39 = 61.5% | 21/36 | 3/3 |
| glm-5.3-flash | fuselage_barrel / open_hole_panel / stiffened_panel | 7/7 · 13/13 · 5/5 | 2/2 · 3/3 · 4/4 | 5/5 · 10/10 · 1/1 |
| deepseek-v4-pro | wingbox | 15/39 = 38.5% | 13/36 | 2/3 |
| deepseek-v4-pro | fuselage_barrel / open_hole_panel / stiffened_panel | 5/7 · 11/13 · 5/5 | 2/2 · 2/3 · 4/4 | 3/5 · 9/10 · 1/1 |

与 C-041 里**原有的手抄值逐个对上**（`24/39`、非翼盒 `25/25`、`15/39`、非翼盒 `21/25`、泄漏 19 条里 16 条不在最差族）
⇒ **这是「数字对但没有 artifact」，不是数字错**。这一区分很重要：不能事后把它说成「发现了一个错」。

## 5. 通过 / 失败项（逐项）

| # | 项 | 结果 |
|---|---|---|
| 1 | 六个既有数字 | ✅ 逐数未变 |
| 2 | `l2_scores_*` 零删除、零非 allowlist 改动 | ✅ 2 处 `_note` 已声明 |
| 3 | `l2_clarify_dual.json` 零删除零改动 | ✅ |
| 4 | 族级闭合 `Σ族 == 总数`（n 与 passed 两侧） | ✅ S-60 |
| 5 | 每族 `informative + invalid == all` | ✅ S-60 |
| 6 | 三桶族集合一致 | ✅ S-60 |
| 7 | 两层 `by_family` 不换义（顶层 int / 模型块 dict） | ✅ S-60 |
| 8 | `negative_controls.py` | ✅ **68/68**（含 NC-66 六向，**首跑即全中**） |
| 9 | `check_claims.py` | ✅ **33 claims / 68 artifacts / 60 语义项 → 全过** |

## 6. 已知问题 / 未验证项

1. **S-60 的边界（已写进 R72）**：只守「落盘 + 闭合 + 可加 + 不换义」，**守不了「族划分本身是否合理」** —— 族是考卷属性，改族 = 改卷（走 R65）。也不守「该有的族没出现」。
2. **`R27` 的 `is_diag` 是关键字判据（脆弱，本轮实际踩到）**：它用 `status/level/statement` 里是否含「diagnostic / 诊断」判定层级。我在 C-041 正文里写「此前只活在一份手写**诊断** md 里」，一句话就把 C-041 判成 diag，随即与共用同一 artifact 的 C-038 冲突（红）。已改措辞（去掉「诊断」二字）恢复。**建议 follow-up**：把这个判据改成结构化字段（如 `level` 显式取值），否则任何一条 claim 只要在正文里提到「诊断」就会被静默改级。
3. **C-041 命令列补了 `--label`**：原记录的命令复现不出 artifact 里的 `label` 字段（我实测发现：不带 `--label` 会写成默认值 `T-A14 …`）。与上一轮 C-033 补 `--tasks` 同源。
4. **R71 / R70 顺序错位已摆回**：上一轮我把 R71 插在 R70 之前（升序表被打破），本轮修正 —— 这是**我自己上一轮的错**，在此登记以免被读成「顺手改别人东西」。
5. **`_family_text()` 只是给 S-60 的「声称」段做 live read**，不参与判定；判定全在 `l2_family_closure()`。

## 7. 下一步（一个）

**B —— 第三方可用性验收**（clone + `fetch_data.py` 能否复现 headline 的 C-032 数字），因为它是"这个 benchmark 别人能不能用"的唯一未验证前提；A（口径说明）到此收口。
