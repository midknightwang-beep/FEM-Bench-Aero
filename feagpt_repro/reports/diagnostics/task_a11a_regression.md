# T-A11a 回归报告：v7 双分母改造对老卷零影响

> 生成方式：`python _regress_task_a11a.py`（本文件由脚本写出，不要手改）
> 判据来源：R-A2（改了判分必须证明老数不动）+ R66（判据失效子集隔离+双报）

## 1. 为什么做这件事

`score_baseline.py` / `msr_l3.py` 原来判定「哪些题算 exam」用的是
`exam_stratum 非空`。v7 把 9 条 v1.1 内插题标成 `interpolation_v11` ⇒ 会被算成 exam，
于是 exam 由 **25** 变 **34**，与 C-032 **不同分母**（R53/R54 禁止并列/相减）；
更隐蔽的是 `dev = not is_exam` 会把那 9 条同时折进 dev，**dev 分母 30→39**，
「dev 只作开发诊断」这条也被污染。

改造后四桶互斥穷尽：`exam(legacy 25) + exam_v11(9) + dev(30) == 64`，
且 `exam_full = exam + exam_v11 = 34`。`exam` 这个键**仍是 legacy**，所以 C-032 继续可比。

## 2. 怎么验的

用**官方 C-032 完全同参数**重跑 v6c（`--label`、`--trivial` 也照抄，否则会造出假 diff），
msr 用 `--reuse` 复用同一批求解结果只重算分母（不起求解器），再与官方两份 artifact 逐叶子比。

## 3. 结果

| artifact | 既有叶子 | changed（未声明） | removed | added（越界 / 允许） | 结论 |
|---|---|---|---|---|---|
| scorecard v6c_p2 | 1607 | **0** | **0** | 0 / 96 | RESULT: PASS —— 除显式声明的变更与 allowlist 内新增键外零差异 |
| bootstrap CI v6c_p2 | 64 | **0** | **0** | 0 / 0 | RESULT: PASS —— 除显式声明的变更与 allowlist 内新增键外零差异 |

**老数字实读（重跑值）**：

```
EXAM   TSR 23/25 (92.0%)   ← 与 C-032 同为 23/25
exam_full TSR 23/25 (92.0%)  ← v6c 上 == exam（v11 为 0 条）
exam_v11  n = 0
DEV    TSR 22/30 (73.3%)     ← 仍是 30 条，没被 v11 污染
四桶闭合 25 + 0 + 30 = 55 == 55  ok=True
```

## 4. 唯一一处「值变了」

`msr_section.provenance.reuse_source`：官方记 `self(recompute-only…)`，本次记官方成绩单路径。
原因是本次用 `--reuse` 指向官方文件、官方那次指向自己。**这是调用方式差异，不是口径差异**，
已在命令行用 `--allow-changed` 逐条声明（改值类差异不接受前缀批量放行）。

## 5. 顺带修掉的同源 bug（值得单独记）

`bootstrap_ci.py` 在 scorecard 位于 `C:\Temp` 时抛
`ValueError: path is on mount 'C:', start on mount 'F:'` —— 与 2026-10-28 在
`check_claims.py` / `report_l2_clarify.py` 撞的是同一个坑。

**只修撞到的那一处，它一定会长回来**。本次收敛到 `_paths.rel()`，覆盖 8 个脚本
（`bootstrap_ci` / `score_baseline` / `msr_l3` / `check_l2_leak` / `audit_contract` /
`export_msr` / `trivial_baselines` / `r32_audit`）。在 F: 内输出与原 `relpath` 逐字相同，
这也是上表 `removed=0` 能成立的原因之一。

## 6. 边界（不假装验过的事）

- 本报告只证明**老卷老数不动**；v7 新卷的双分母是否正确，要靠 T-A11b 的真候选跑完再看。
- `exam_full` 目前**没有 bootstrap CI**（`bootstrap_ci.py` 只对 `is_exam` 做重采样）。
  两条口径并列时，一条有 CI 一条没有是不对称的 ⇒ 见 follow-up。
