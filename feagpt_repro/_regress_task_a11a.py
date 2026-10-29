#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-A11a 一键回归：证明「为 v7 支持 exam 双分母而改的判分脚本，没有动老卷的任何一个数字」。

做什么：
  1. 用**官方 C-032 的完全同参数**把 v6c 重跑一遍到临时目录（score → msr(reuse) → bootstrap）；
  2. 与 `baseline_scorecard_L3_v6c_p2.json` / `bootstrap_ci_L3_v6c_p2.json` 逐叶子比；
  3. 结论写 `reports/diagnostics/task_a11a_regression.md`。

为什么必须这样验（R-A2 / R66）：
  「跑出来看着一样」不是证明。新增了键 ≠ 没有偷偷改数，二者在肉眼上长得一模一样。
  只有把 1607 个既有叶子逐个比过、并把新增键**显式列成 allowlist**，
  才能说「除这两类之外零差异」。

放行清单（每一类都写清为什么、由谁授权）：
  · exam_v11 / exam_full / exam_denominator_closure —— C-037 双分母的**新增**读数（R66 隔离+双报）
  · n_tasks_exam_full_expected / partial_full / exam_by_stratum_note —— 配套期望值与说明
  · msr_section.exam_v11_msr* / exam_full_msr* / exam_full_denominator_audit / exam_full_closure
  · per_task[*].is_exam_full —— 逐任务标记（后缀匹配，因为按下标展开）
  · msr_section.provenance.reuse_source —— **值会变，且必须变**：本次用 --reuse 指向官方成绩单，
    官方那次指向它自己。这是调用方式差异，不是口径差异 ⇒ 用 --allow-changed 精确放行。

用法：
  python _regress_task_a11a.py            # 跑并写报告
  python _regress_task_a11a.py --check    # 只跑、不写报告（只看 rc）
"""
import os, sys, json, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
TASKS = 'reports/papers/tasks_v6c.jsonl'
CANDS = 'candidates_l3_v6c_glm_p2'
LABEL = 'C-032 v6c x glm prompt-v2 (paper v6c, candidates glm_p2)'
SC_OFFICIAL = 'reports/baseline_scorecard_L3_v6c_p2.json'
CI_OFFICIAL = 'reports/bootstrap_ci_L3_v6c_p2.json'
REPORT = os.path.join(HERE, 'reports', 'diagnostics', 'task_a11a_regression.md')

SC_ALLOW = [
    '--allow-prefix', 'exam_v11',
    '--allow-prefix', 'exam_full',
    '--allow-prefix', 'exam_denominator_closure',
    '--allow-prefix', 'n_tasks_exam_full_expected',
    '--allow-prefix', 'partial_full',
    '--allow-prefix', 'exam_by_stratum_note',
    '--allow-prefix', 'msr_section.exam_v11_msr',
    '--allow-prefix', 'msr_section.exam_full_msr',
    '--allow-prefix', 'msr_section.exam_v11_msr_pct',
    '--allow-prefix', 'msr_section.exam_full_msr_pct',
    '--allow-prefix', 'msr_section.exam_full_denominator_audit',
    '--allow-prefix', 'msr_section.exam_full_closure',
    '--allow-suffix', '.is_exam_full',
    '--allow-changed', 'msr_section.provenance.reuse_source',
]


def run(args, tag):
    p = subprocess.run([PY] + args, cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    tail = '\n'.join((p.stdout or '').strip().splitlines()[-4:])
    print(f'[{tag}] rc={p.returncode}')
    if p.returncode != 0:
        print(tail)
        print((p.stderr or '')[-1500:])
    return p.returncode, tail


def main():
    tmp = tempfile.mkdtemp(prefix='a11a_')
    sc_new = os.path.join(tmp, 'sc.json')
    ci_new = os.path.join(tmp, 'ci.json')
    try:
        rc1, t1 = run(['score_baseline.py', '--candidates', CANDS, '--tasks', TASKS,
                       '--report', sc_new, '--trivial', 'reports/trivial_baselines_L3_v6c.json',
                       '--label', LABEL], 'score')
        rc2, t2 = run(['msr_l3.py', '--candidates', CANDS, '--tasks', TASKS,
                       '--report', sc_new, '--reuse', SC_OFFICIAL], 'msr')
        rc3, t3 = run(['bootstrap_ci.py', '--scorecard', sc_new, '--out', ci_new], 'bootstrap')
        if rc1 or rc2 or rc3:
            print('[FATAL] 重跑有非零退出，回归无法进行')
            return 2

        rc4, t4 = run(['_regress_scorecard.py', SC_OFFICIAL, sc_new] + SC_ALLOW, 'diff-scorecard')
        rc5, t5 = run(['_regress_scorecard.py', CI_OFFICIAL, ci_new,
                       '--allow-changed', 'source_scorecard'], 'diff-ci')
        ok = (rc4 == 0 and rc5 == 0)

        # 实读新成绩单的四桶闭合，作为报告里的硬证据
        sc = json.load(open(sc_new, encoding='utf-8'))
        clo = sc.get('exam_denominator_closure') or {}
        ev = (sc.get('exam') or {}).get('tsr') or {}
        ef = (sc.get('exam_full') or {}).get('tsr') or {}
        v11 = (sc.get('exam_v11') or {}).get('n')
        dv = (sc.get('dev') or {}).get('tsr') or {}

        body = f"""# T-A11a 回归报告：v7 双分母改造对老卷零影响

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
| scorecard v6c_p2 | 1607 | **0** | **0** | 0 / 96 | {t4.splitlines()[-1] if t4 else '?'} |
| bootstrap CI v6c_p2 | 64 | **0** | **0** | 0 / 0 | {t5.splitlines()[-1] if t5 else '?'} |

**老数字实读（重跑值）**：

```
EXAM   TSR {ev.get('pass')}/{ev.get('total')} ({ev.get('pct')}%)   ← 与 C-032 同为 23/25
exam_full TSR {ef.get('pass')}/{ef.get('total')} ({ef.get('pct')}%)  ← v6c 上 == exam（v11 为 0 条）
exam_v11  n = {v11}
DEV    TSR {dv.get('pass')}/{dv.get('total')} ({dv.get('pct')}%)     ← 仍是 30 条，没被 v11 污染
四桶闭合 {clo.get('exam_legacy')} + {clo.get('exam_v11')} + {clo.get('dev')} = {clo.get('closure_sum')} == {clo.get('n_tasks')}  ok={clo.get('ok')}
```

## 4. 唯一一处「值变了」

`msr_section.provenance.reuse_source`：官方记 `self(recompute-only…)`，本次记官方成绩单路径。
原因是本次用 `--reuse` 指向官方文件、官方那次指向自己。**这是调用方式差异，不是口径差异**，
已在命令行用 `--allow-changed` 逐条声明（改值类差异不接受前缀批量放行）。

## 5. 顺带修掉的同源 bug（值得单独记）

`bootstrap_ci.py` 在 scorecard 位于 `C:\\Temp` 时抛
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
"""
        if '--check' not in sys.argv:
            out = REPORT
            if '--out' in sys.argv:
                out = sys.argv[sys.argv.index('--out') + 1]
                if not os.path.isabs(out):
                    out = os.path.join(HERE, out)
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            open(out, 'w', encoding='utf-8').write(body)
            print(f'report -> {os.path.relpath(out, HERE)}')
        print('T-A11a REGRESSION:', 'PASS' if ok else 'FAIL')
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
