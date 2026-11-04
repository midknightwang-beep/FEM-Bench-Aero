# T-L27c v3：L2 prompt 单变量消融（3 arm × 2 模型 × 2 遍）

> **性质**：`diagnostic`。**不进入任何对外数字**，**不得与 v7 的 L2 分数并列或相减**（R54/R65）。
> **日期**：2026-11-04
> **卷**：`tasks/tasks_l2_informative_v2.jsonl`（16 条，sha256 `76ee70f6e16d…`，CRLF）—— 与前一轮**同一张卷、逐字节未改**
> **唯一变量**：L2 prompt（`SYS + L2_ADDENDUM` 之后追加的段落），题面 / 判据 / 判分器**一律未动**
> **产物**：`candidates_l2i_v3s_{glm,ds}`、`candidates_l2i_v3sm_{glm,ds}`、`candidates_l2i_v3sm2_{glm,ds}`
> **成绩单**：`reports/diagnostics/l2i_v3{s,sm,sm2}_scores_{glm,ds}.json`（6 份）
> **对比产物**：`reports/diagnostics/l27c_v3_arm_*.json` / `l27c_v3_repro_*.json`（6 份，由 `_l27c_arm_compare.py` 生成，不重算判分）

---

## 1. 一句话结论

**瓶颈在 prompt，不在能力 —— 这一条现在有 8 次实跑的配对证据：只加一句「按题面键名逐字转写、不质疑 schema 命名、不省略、不合并」，glm 从 2/16 到 10/16（McNemar p=0.0078，8 条单向改善、0 条变差），ds 从 3/16 到 8/16（p=0.0625，5 条改善、0 条变差）。**

**但「修 SYS 里那句网格键错话」只对 glm 单向有效（10→16，p=0.0312），对 ds 无效且引入反向噪声（8→10，p=0.73，且 3 条变差）**；而 glm 那次 16/16 在同 prompt 第二遍掉到 14/16 ⇒ **16/16 不可引用，保守下界是 14/16 = 87.5%**。

---

## 2. 三个 arm 的设计

| arm | prompt 内容 | sha256（前 12） |
|---|---|---|
| **A base** | `SYS + L2_ADDENDUM`（与 v7 完全一致，未改一字节） | `03129c56d83b` |
| **B strict** | A + 「按题面键名逐字转写，不质疑 schema 命名，不省略、不合并」 | `99466166dc04` |
| **C strict+meshfix** | B + 「E. 网格键（本小节覆盖上文「size（板壳类）」那一句）：四族的网格块只有 size_chord 与 size_span，开孔板与加筋板也用这两个键名，没有 size 这个键」 | `24cf0978369f` |

**A 的 sha 必须不变**：`03129c56d83b` 是 C-041 的锚点（S-39 靠它做漂移闸）。实测未变，实验分支的 sha 各自独立（`--print-prompt-sha-l2-<arm>` 五条命令互不干扰）。

**为什么分成两跳**：B 只加「别改键名」这条指令性约束；C 在 B 之上**点名一处具体的 prompt 缺陷**。两跳分开才能回答「是引导有效，还是补漏有效」。

---

## 3. 结果

### 3.1 八次实跑

| 模型 | A base | B strict | C1 strict+meshfix | C2 C1 复现 |
|---|---|---|---|---|
| glm-5.3-flash | 2/16 | 10/16 | **16/16** | **14/16** |
| deepseek-v4-pro | 3/16 | 8/16 | 10/16 | 8/16 |

追问数（本卷 16 条 `expected_clarifications` 全为空 ⇒ 任何追问一律记错）：

| 模型 | A | B | C1 | C2 |
|---|---|---|---|---|
| glm | 2 | 0 | 0 | 0 |
| ds | **9** | **1** | 4 | 5 |

### 3.2 六组配对检验

| 模型 | 对比 | 前 | 后 | b（前对后错） | c（前错后对） | McNemar 精确双侧 p | 判类逐条相同 |
|---|---|---|---|---|---|---|---|
| glm | A→B | 2/16 | 10/16 | **0** | 8 | **0.0078** | 7/16 (43.8%) |
| glm | B→C1 | 10/16 | 16/16 | **0** | 6 | **0.0312** | 10/16 (62.5%) |
| ds | A→B | 3/16 | 8/16 | **0** | 5 | **0.0625** | 8/16 (50.0%) |
| ds | B→C1 | 8/16 | 10/16 | **3** | 5 | **0.7266** | 6/16 (37.5%) |
| glm | C1→C2 | 16/16 | 14/16 | 2 | 0 | 0.5000 | 14/16 (87.5%) |
| ds | C1→C2 | 10/16 | 8/16 | 4 | 2 | 0.6875 | 10/16 (62.5%) |

**b=0 这件事比 p 值更有信息量**：A→B 在两个模型上都是「零个 case 变差、只有改善」。p 值受 n=16 限制（ds 的 p=0.0625 差一点没到 0.05），但方向是纯单向的 —— 这不是均值为零的噪声能产生的形状。

---

## 4. 三条结论

### 4.1 「按题面键名逐字转写」是这一轮最有效的单点改动

它同时压掉了两类失败：

- **glm**：`spec_bad` 从 12 条降到 5 条，失败键全部集中在 mesh 段被省略/合并（`size_chord`+`size_span` → `size`、丢 `leading_edge_threshold`）。
- **ds**：追问从 **9 条降到 1 条**。base arm 那 9 条追问里，8 条是「质疑 schema 规范」而不是「题面缺信息」——加了「不质疑 schema 命名」之后基本消失。

⇒ v2 报告里「失败模式指向 prompt 而非能力」的推断，在这一步得到**干预验证**（不是再看一遍失败模式，是改掉它、看它降不降）。

### 4.2 「修 SYS 网格键错话」只对 glm 有效，对 ds 无效甚至有害

glm：10→16，b=0、c=6、p=0.0312，纯单向。
ds：8→10，**b=3**、c=5、p=0.7266，三条变差、判类只同 6/16（37.5%，比随机稍好）。

**ds 那 3 条变差不是随机波动，有原文证据**（C1 的 4 条追问里）：

| task | ds 追问原文（截断） | 问题 |
|---|---|---|
| `L2i_fuselage_barrel_d2000_l2000_str8_frm3` | 「`mesh.size_span` 与 `mesh.size_chord` 在 fuselage_barrel 族中**不是合法网格键**；本族网格键**只能使用** size_chord、size_span，题面已给出 size_chord…」 | **自相矛盾**：前半句说不合法、后半句说只能用这两个 |
| `L2i_open_hole_panel_400x200_d20_offcentre` | 「`material.poisson_ratio` 与键名总表不符（**应为 nu**），且未给剪切模量 G」；「`load.kind=tip_force` 对 open_hole_panel **不适用**」 | 把「schema 命名建议」当成澄清理由 |
| `L2i_naca4412_wingbox`（C2） | 「题面缺失 wingbox 族的必需键 `stringer_kind`（**已给出**但需确认其取值…已按题面保留）」 | 自己都写了「已给出」还在追问 |

**机制**：SYS 原话是「size（板壳类）」，覆盖段 E 说「上文那句不算、只有 size_chord/size_span」。**覆盖段把一个原本可以忽略的矛盾显式化了** —— glm 照做（16/16），ds 去追问那个矛盾（4 条追问）。

⇒ **补漏式 prompt 修法不能假设对所有模型都成立**：同一处修改，对一个模型是「消除歧义」，对另一个是「提示这里有问题，值得一问」。

### 4.2b 那条失败路径的直接证据（按候选产物核，不按 prompt 文本核）

用 `_l27c_check_mesh_keys.py` 直接扫候选产物里 **mesh 段实际写了哪些键**（核 `多余 = 未知键` 与 `缺失 = gold 有而没写` 两个方向）：

| 候选目录 | 给出 spec | mesh 键有问题的题 | 多余键 | 缺失键 | 典型形态 |
|---|---|---|---|---|---|
| `candidates_l2i_v2_glm`（base） | 14 | **9** | 9 | 40 | `多余=['size']` + `缺失=['size_chord','size_span',…]` |
| `candidates_l2i_v2_ds`（base） | 7 | **3** | 3 | 19 | 同上 |
| `candidates_l2i_v3sm_glm`（C 臂） | 16 | **0** | 0 | 0 | — |
| `candidates_l2i_v3sm_ds`（C 臂） | 12 | 1 | 0 | 7 | 缺 7 个执行配置键（**整段省略**，与 size 无关） |

⇒ base arm 的 **12 条问题题全部**多写了一个 `size`（12/12），其中 12 条同时少写 `size_chord`/`size_span` —— 完全一致的模式，不是随机转写失误，是**按 SYS 那句话执行的必然结果**。

**这条判据为什么落在候选产物上、不落在 prompt 文本上**（第一版写错、值得记）：第一版读 SYS、抽 `\bsize\b` 词元再核 gold，结果 base 与 meshfix **两个 arm 都判红** —— 因为覆盖段原文是「…**没有 size 这个键**」，这句话**提到**了 `size`，是否定它。⇒ **「是否出现某词」这条轴无法区分肯定与否定**（R77 ⑧ 的同一个坑）。改判效果后双向清楚：base 红在「多写 size」，C 臂绿。

### 4.3 16/16 不可引用：同 prompt 第二遍掉到 14/16

| 模型 | C1 | C2 | 翻转 | 结论 |
|---|---|---|---|---|
| glm | 16/16 | 14/16 | 2 条（全为对→错） | **不可引用 16/16**，保守下界 **14/16 = 87.5%** |
| ds | 10/16 | 8/16 | 6 条（4 对→错、2 错→对） | 两次都在 8–10 区间，**只有区间可引用** |

**glm C2 那 2 条失败，全是把题面已经给出的执行配置键写错了**（`algorithm_2d` / `element_order` / `min_jacobian` / `recombine` / `recombination_algorithm`）。

**这里有一个必须说清的判断**：我一开始怀疑「L2 判分器不豁免 `EXEC_CONFIG_KEYS`、而 L3 豁免 ⇒ 同类闸漏装」。**核实后不成立，两个口径都对**：

- L2 informative 题面**直接给全 spec_json**，实测 16/16 条的 mesh 段都含全部 9 个键（含 `algorithm_2d`、`min_jacobian`）⇒ 考的就是逐字转写，写错就该罚。
- L3 是 NL 任务书，这些键**永远不会被提及** ⇒ 豁免（W4d 拍板）。

⇒ 差异来自输入形态，不是漏装闸。**但 `extra` 段要单独看**：16 条里 8 条给的是 `{}`，模型写 `moment_axis`/`shear_axis` 属编造、罚得对；另 2 条题面给了 `split_tag` / `v11_*`（数据集记账键），照抄即可。

---

## 5. 顺带查出的真实缺陷：SYS 那句「size（板壳类）」与四族 gold 全冲突

### 5.1 事实

`gen_candidates_v2.js` 第 40 行（SYS 常量，**L3 也在用**）：

> 网格键 size_chord/size_span（翼盒）、**size（板壳类）**

实测 `FEM-Bench-Aero/modeling/*/spec.json` 全部 gold：**四族 mesh 段只有 `size_chord` / `size_span`，没有任何一个 gold 有 `size`**。

### 5.1b 这句话的来历：改对过，被回滚带走，且没有任何闸报错

- `_psa_fix_mesh_keys.py` 里 `OLD1`（p3 版 SYS 片段）与 `NEW1`（p4 版）**都含**「板壳类也用这两个键名——**没有 size 这个键**」⇒ p3/p4 期间这句话是对的。
- `git log -S "size（板壳类）"` 显示这句错话由 **`b2e9b74`（2026-10-25，W4d L3 主基线）** 引入，在 `ce225186` 里存在。
- 2026-11-01 为「不换代」把 SYS **回滚到 `ce225186`**（p5c 作废）⇒ 那句更正**跟着回滚一起消失**。
- **没有任何闸报错**，因为闸只锚「`ce225186` 这个 sha 变没变」（S-39），**不锚「这个 sha 对应的那句话对不对」**。

⇒ 记成一条可复用的判断法：**回滚可以证「回到原样」，但证不了「原样是对的」**。锚点闸守的是同一性，不是正确性；这两件事必须各有一条闸。

### 5.1c 新增守卫闸 `_l27c_check_mesh_keys.py`

按上面那条判断法补的闸，判据落在**候选产物实际写了哪些 mesh 键**上（不判 prompt 文本，理由见 §4.2b）：

```
python _l27c_check_mesh_keys.py --candidates candidates_l2i_v2_glm     # 红：9 条多写 size
python _l27c_check_mesh_keys.py --candidates candidates_l2i_v3sm_glm   # 绿：16/16 键集一致
python _l27c_check_mesh_keys.py --self-test                            # 自比 A==A + 三向变异
```

双向判据：① 候选写了 gold 没有的键 ⇒ 红；② gold 有而候选不写 ⇒ 红（只核①会漏「整段省略」）。自检四向：自比绿 / 凭空多 `size` 报多余 / 漏写报缺失 / mesh 整段清空报缺失。空目录、解析不到 gold case 一律**判红不 skip**。

### 5.2 影响范围：已发布数字 **零变动**（实测，不是推断）

| 已发布口径 | 是否受影响 | 证据 |
|---|---|---|
| **L3 v7（C-032 来源卷）** | **否** | 复算 `candidates_l3_v7_{glm,ds}` 共 118 个给出 spec 的候选，`spec_fidelity(engineering_layer=True)`：**mesh 段失败 0 条**（glm、ds 均为 0）；复算 FAIL 数 glm 11 / ds 9，与已发布 `sfr_all`（48/59、50/59）**完全吻合** |
| **L2 v7（64 条）** | **否** | 64 条 `expected_clarifications` **全部非空** ⇒ 题型是「应追问」，不判 spec 保真 |
| L2 informative 诊断卷（16 条） | **是** | 本轮 C 臂修好后 glm **16/16（第二遍 14/16）**、ds **10/16（第二遍 8/16）**；本来就未进对外数字 |

**L3 为什么没中招**：L3 是 NL 输入，没有 spec 呈现，模型凭工程常识自己写 `size_chord`/`size_span`，恰好对。而 L2 informative 把 spec 摊开给模型看，模型看到题面写 `size_chord`、SYS 说「板壳类用 size」，一部分模型选择听 SYS ⇒ 改名/合并 ⇒ 被罚。

### 5.3 为什么没顺手改掉

改 SYS 常量会改 `ce225186`，那是 **C-032 / C-033 / C-040 / C-041 的锚点**（R53 / S-39），动它必须老王拍板（R-A6）。本轮**只在实验 arm 里加覆盖段，SYS 常量一字未动**，已记入 `CONFLICT.md` N-34。

---

## 6. 这一轮**不**声称的事

1. **不声称 L2 已装上「信息完备题型」**。16 条仍是 diagnostic，`ROADMAP §13` 第 10 项**不算装上**。
2. **不声称 glm 优于 ds**。两模型在 C 臂上 16/16 vs 10/16 的差距没有做跨模型配对检验的意义 —— 本轮的配对只在**同一模型的两个 arm 之间**做。
3. **不声称 meshfix 是通用修法**。它在 ds 上引入反向噪声（§4.2），这本身就是反例。
4. **不引用任何单次 C 臂数字**。glm 的 C1=16/16 与 C2=14/16 必须一起出现（N-31）。
5. **没有走 v8**。`ROADMAP` 记录的是「下一步待拍板」，v8 需要 R65 的全新冻结 + bridge + 两模型全量重跑，不在本轮范围。

---

## 7. 复现

```bash
cd feagpt_repro
PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 三个 arm 的 prompt sha（A 必须仍是 03129c56d83b）
node gen_candidates_v2.js --print-prompt-sha-l2
node gen_candidates_v2.js --print-prompt-sha-l2-strict
node gen_candidates_v2.js --print-prompt-sha-l2-strict-meshfix

# 跑批（每臂每模型 16 条）
node gen_candidates_v2.js --tasks tasks/tasks_l2_informative_v2.jsonl --levels L2 \
  --l2-strict --l2-meshfix --out candidates_l2i_v3sm_glm --model glm-5.3-flash --max-turns 3

# 判分
"$PY" score_l2.py --cand candidates_l2i_v3sm_glm --tasks tasks/tasks_l2_informative_v2.jsonl \
  --label l2i_v3sm_glm --out reports/diagnostics/l2i_v3sm_scores_glm.json

# 配对对比（ablation 模式有四条前置闸：同卷 / 同模型 / 两 arm prompt sha 必须不同 / 同条数）
"$PY" _l27c_arm_compare.py --base reports/diagnostics/l2i_v3s_scores_glm.json \
  --strict reports/diagnostics/l2i_v3sm_scores_glm.json \
  --tasks tasks/tasks_l2_informative_v2.jsonl \
  --out reports/diagnostics/l27c_v3_arm_glm_strict_vs_strictmeshfix.json

# 复现性检查（同 prompt 两遍，没开 --mode repro 会判红）
"$PY" _l27c_arm_compare.py --mode repro \
  --base reports/diagnostics/l2i_v3sm_scores_glm.json \
  --strict reports/diagnostics/l2i_v3sm2_scores_glm.json \
  --tasks tasks/tasks_l2_informative_v2.jsonl \
  --out reports/diagnostics/l27c_v3_repro_glm.json
```
