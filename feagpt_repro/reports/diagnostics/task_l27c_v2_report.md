# T-L27c v2：L2「信息完备题型」16 条诊断报告

> **性质**：`diagnostic`。**不进入任何对外数字**，**不得与 v7 的 L2 分数并列或相减**（R54/R65）。
> **日期**：2026-11-04
> **拍板**：老王 2026-11-04「方案 A：16 条（每族 4 条），只标 diagnostic」。
> **卷**：`feagpt_repro/tasks/tasks_l2_informative_v2.jsonl`（16 条，sha256 `76ee70f6e16d…`，CRLF）
> **成绩单**：`reports/diagnostics/l2i_v2_scores_{glm,ds}.json`
> **生成器**：`_l27c_make_l2_informative.py --per-family 4`（入库，可复现）

---

## 1. 一句话结论

**16 条上两模型都极低（glm 12.5%、ds 18.8%），但这个差距完全不可分辨 —— 配对 McNemar 精确检验 p = 1.00，不一致对只有 1 个；而同 4 条题跨卷重跑，判类翻转率是 4/8 = 50%。**

⇒ **本卷的产出不是「谁更强」，而是「n=16 上任何排名都没有意义」**，而且这个结论有两条独立证据（配对检验 + 翻转率），比单看置信区间硬。

---

## 2. 卷的设计

| 项 | 值 |
|---|---|
| 条数 | 16（4 族 × 4 条） |
| `expected_clarifications` | 全为空（信息完备 ⇒ 该答 spec，不该澄清） |
| 派生方式 | 每族从 L1 池按 **split 轮转**取 4 条；`task_id` = `L2i_` + 源 L1 名 |
| split 覆盖 | wingbox 4 种（bh/ex/val/train）；其余三族各 3 种 |
| 与 v1 关系 | **v1 ⊂ v2**，v1 那 4 条在 v2 里**逐字段相同**（断言守，见 §6） |
| prompt | 未改。`node gen_candidates_v2.js --print-prompt-sha-l2` = `03129c56d83b…`，与 v1 候选里记录的**逐字节相同** |

**为什么改用 split 轮转**（v1 是全局排序取第 1 条）：`boundary_holdout` 在 wingbox 有 6 条、全排最前 ⇒ 若直接取前 4 条，4 条全落在同一 split，测的是「同类结构的 4 个变体」，**族级代表性是假的**。轮转法让每族尽量覆盖多个 split；而各轮的第 1 条恰好就是 v1 选的那条 ⇒ 顺带拿到「v1 ⊂ v2」。

---

## 3. 结果

| 模型 | `strata.informative` | CI95（Wilson, n=16） | spec_ok | spec_bad | clarify_wrong |
|---|---|---|---|---|---|
| glm-5.3-flash | **3/16 = 18.8%** | [6.6, 43.0] | 3 | 11 | 2 |
| deepseek-v4-pro | **4/16 = 25.0%** | [10.2, 49.5] | 4 | 3 | 9 |

> **★ 本表为 2026-11-05 N-35 修正后的口径**（`extra` 的 7 个数据集记账键不再判分）。旧口径为
> glm 2/16 = 12.5% [3.5, 36.0]（spec_ok 2 / spec_bad 12）、ds 3/16 = 18.8% [6.6, 43.0]（spec_ok 3 / spec_bad 4）。
> 旧代成绩单归档在 `reports/archive/l2i_v2_scores_*__pre_n35.json`，对照见 `n35_bridge.md`。

`strata.clarified` 两层都是 `0/0`，`_coverage = informative_only` —— **本卷只覆盖「信息完备」层，另一层的 `0/0` 不是 0 分**。

**分族**（每族 n=4，仅作形态观察，**不可比大小**）：

| 族 | glm spec_ok | ds spec_ok |
|---|---|---|
| wingbox | 2/4 | 3/4 |
| open_hole_panel | 0/4 | 0/4 |
| fuselage_barrel | **1/4** | **1/4** |
| stiffened_panel | 0/4 | 0/4 |

> wingbox 仍是主力（两模型合计 **7** 个通过里 **5** 个在它），但 **fuselage_barrel 各 1 条**在 N-35 修正后也进账了 —— 旧口径下这两条被判成 spec_bad，失败字段是 `extra.split_tag` / `v11_bracket` 这类数据集记账键。**不解释成「柱壳更容易」**：既可能是族特性、也可能是 n=4 的偶然。记为待查，不当结论。

---

## 4. 题面完备性：四档独立证据

判 `clarify_wrong`（该答不答）的前提是题面**真的完备**。这一条不能靠构造声明，必须独立核：

1. **构造上删 0 个键**（v7 的 L2 是「删 1 个键」，同族同向更弱）；
2. **`structure` 段与 gold 逐键一致**：`stiffened_panel_600x600_str3` 题面 31 键 / gold 48 键，但「gold 有而题面缺」的 17 个**全是 `airfoil.*` + `description`** —— 翼盒专用段，对平板/柱壳族不适用（judge 侧按 `dead_fields` 排除）。「题面有而 gold 无」= 0，「两边都有但值不同」= 0；
3. **被判失败的字段在题面里确实存在**：glm 失败的 `mesh.leading_edge_threshold` / `refine_at_leading_edge` / `size_chord` / `size_span` —— 题面与 gold **都列了这四个键**；
4. **ds 追问的字段在 gold 里也不存在**：`hole_x`/`hole_y` 两边都无（孔心默认居中，`feagpt/geometry.py`）；`skin_thickness` 只存在于 gold 的 `airfoil` 段；`frame_thickness` 两边都无。

⇒ **ds 那 9 条追问，没有一条是「题面真缺信息」。**

---

## 5. 失败模式（这才是本卷的信息量）

### glm：12 条 `spec_bad` 是真实保真失败，且高度同构

| 形态 | 字段 | 出现次数 |
|---|---|---|
| **丢字段** | `mesh.leading_edge_threshold`、`mesh.refine_at_leading_edge` | 各 7 |
| **改名/合并** | `mesh.size_chord` + `mesh.size_span` → 写成 `mesh.size` | 7 / 7（多给 `size` 4 次） |
| **编造键** | `extra.moment_axis`、`extra.shear_axis`（gold 里都没有） | 各 4 |

⇒ 12 条里绝大部分栽在 **mesh 段的「省略」与「合并」**，而不是物理参数算错。这是「无损转写」能力的缺口，与建模能力无关。

### ds：9 条 `clarify_wrong` 全部是「质疑 schema」而非「缺信息」

| 形态 | 例子 | 条数 |
|---|---|---|
| **段名/键名错位** | 把 `airfoil.stringer_height` 的要求套到 `structure.params` 上、要求 `poisson_ratio` 改成 `nu` | 4 |
| **要求非必需字段** | `hole_x`/`hole_y`（默认居中） | 3 |
| **漏看题面** | 说「缺失 span」，而 `airfoil.span = 2000.0` 就在题面里 | 1 |
| **质疑 `n_stringers=0`** | 素板情形要求确认 | 1 |

⇒ ds 在信息完备题上的失败**不是「不肯答」，而是「把规范意见当成了澄清理由」**。这条对下一步（是否要改 prompt 引导「照抄键名」）有直接指向。

---

## 6. 统计边界（本卷不能推出什么）

### 6.1 两模型差异不可分辨

配对列联表（同一批 16 题）：

| | 数 |
|---|---|
| 都对 | 2 |
| 只 glm 对 | 0 |
| 只 ds 对 | 1 |
| 都错 | 13 |

**McNemar 精确双侧检验 p = 1.00**（不一致对仅 1 个：0 vs 1）。

> ⚠ 这里我先写过一次**费雪独立样本检验（p = 0.000）**，那是**错的**：① 公式写成 `C(16,a)·C(16,b)/N`（应为 `C(5,a)·C(27,16−a)/C(32,16)`）；② 更根本的是**同一批题的两模型结果是配对数据**，根本不该用独立样本检验。已改为 McNemar。**「先假定是自己错」这次又救了一次。**

### 6.2 同题重跑翻转率 50%

v1 与 v2 有 4 条题完全相同（同 `task_id`、同 prompt、同 spec），两次独立运行：

| 模型 | 翻转 | 明细 |
|---|---|---|
| glm | 1/4 | `open_hole_panel…d40`：`spec_bad` → `clarify_wrong` |
| ds | 3/4 | `naca…chord1000`：`spec_bad`→`clarify_wrong`；`fuselage…d1600`：`clarify_wrong`→`spec_bad`；`stiffened…str3`：`spec_ok`→`clarify_wrong` |
| **合计** | **4/8 = 50%** | |

⇒ **单次运行的判类本身就不稳定**。这一条比 CI 更有力：既然同一道题跑两遍有一半会换类别，那么「glm 2/16 vs ds 3/16」的差（1 条题）落在噪声里是必然的。

> 样本极小（4 题 × 2 模型 = 8 次比较），**只能示量级、不能给出翻转率点估计**。但它足以否掉本卷上的任何排名。

### 6.3 本卷**不能**说的事

- ❌ 不能说「glm 弱于 ds」或反之（p=1.00）
- ❌ 不能说「某族好/坏」（每族 n=4，CI 半宽 ≥ ±30pp）
- ❌ 不能把这 16 条并进 v7 的 L2 主分母算「整体退化率」（摊薄另见下）
- ❌ 不能说「L2 抗退化」（`clarified` 层穷举残余 48.4% 仍在）

### 6.4 摊薄：加题为什么压不下整体退化率

老卷最坏 **31/64** 仍可被「纯列举 2 个键名」命中，ec=0 题上穷举 **0/59**：

| 新增 ec=0 条数 | 16 | 32 | 64 | 96 | 246 |
|---|---|---|---|---|---|
| `(31+0)/(64+N)` | 38.8% | 32.3% | 24.2% | 19.4% | **10.0%** |

⇒ 要压到 10% 需 **246 条**。**加题的价值在「分层报」，不在「摊薄」。**

---

## 7. 复现

```bash
cd "F:/AI FEA Modeling DataSets/feagpt_repro"
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 1) 造卷（确定性，不手挑）
"$PY" _l27c_make_l2_informative.py --per-family 4 --out tasks/tasks_l2_informative_v2.jsonl
"$PY" _l27c_make_l2_informative.py --check --per-family 4 --out tasks/tasks_l2_informative_v2.jsonl

# 2) prompt 应等于 03129c56d83b8bd37dc1393b649e7250d4bdda2edf680d83889ebae07c4c0d83
node gen_candidates_v2.js --print-prompt-sha-l2

# 3) 跑模型（两模型各 16 条；产物已入库，可跳过）
node gen_candidates_v2.js --tasks tasks/tasks_l2_informative_v2.jsonl --levels L2 \
     --out candidates_l2i_v2_glm --model glm-5.3-flash --max-turns 3
node gen_candidates_v2.js --tasks tasks/tasks_l2_informative_v2.jsonl --levels L2 \
     --out candidates_l2i_v2_ds  --model deepseek-v4-pro --max-turns 3

# 4) 打分（逐字节可复算，已实测）
"$PY" score_l2.py --cand candidates_l2i_v2_glm --tasks tasks/tasks_l2_informative_v2.jsonl --label l2i_v2_glm
"$PY" score_l2.py --cand candidates_l2i_v2_ds  --tasks tasks/tasks_l2_informative_v2.jsonl --label l2i_v2_ds
```

**跑批必须用项目 venv 之外的 node**（`gen_candidates_v2.js`），打分用 venv python。**数据集本体不在 git 里**（`FEM-Bench-Aero/modeling/` 需 `fetch_data.py` 解包）—— 缺它时 `score_l2` 会 `rc=2` 硬错而不是静默判 `spec_bad`（本轮新加的闸，已在干净 clone 上实测拦住）。

---

## 8. 收口清单

- [x] 卷 sha256 `76ee70f6e16d…`（CRLF）；成绩单内嵌 sha 与磁盘卷**一致**（行尾规范化**之前**生成的会被这一步抓到）
- [x] 成绩单**逐字节可复算**（重跑两次 `cmp` 相同）
- [x] `v1 ⊂ v2` 双向断言（含「基线 v1 自身完整性」），七向变体验证各红在正确位置
- [x] `require_dataset` 前置闸在干净 clone 上实测拦截
- [x] 负控 NC-80（见 `negative_controls_80.json`）
- [x] 对外数字**零变动**（v7 两份 L2 成绩单未受影响：本卷独立、不进主分母）
