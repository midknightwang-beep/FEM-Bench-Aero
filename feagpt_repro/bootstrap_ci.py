# -*- coding: utf-8 -*-
"""
bootstrap_ci.py — 给成绩单的 exam 指标加 bootstrap 置信区间（W5b 前置，专家第六轮 P1-6）

为什么：n=11 的 45.5% 与 36.4% 在统计上无法区分；只报点估计会让「修题后 5→4」被读成模型退步。
本脚本对 **exam 任务**做有放回重采样，给 TSR / SFR / MSR 三指标各出一个百分位区间。

纪律（R12/R24）：
  - CI 只描述「同一考卷上换个抽样会长什么样」，**不放宽 n≥20 的门槛**；
  - 输出里强制带 `underpowered` 标记与「不得据此宣布 PASS」的 note；
  - 重采样单位 = 任务（不是字段），因为任务才是抽样单元。
  - 分层口径：overall 之外另给 by_family（每族任务更少，只报不判）。

用法：
  python bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v4.json \
      --out reports/bootstrap_ci_L3_v4.json --boot 4000 --seed 20261025
"""
import argparse, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXAM_SPLITS = ('boundary_holdout', 'extrapolation_test')


def pct(sorted_vals, q):
    """百分位（线性插值），sorted_vals 已排序。"""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def boot_rate(flags, B, seed):
    """对 0/1 序列做有放回重采样，返回 (point, lo, hi)。"""
    n = len(flags)
    if n == 0:
        return None, None, None
    point = 100.0 * sum(flags) / n
    rnd = random.Random(seed)
    vals = []
    for _ in range(B):
        s = sum(flags[rnd.randrange(n)] for _ in range(n))
        vals.append(100.0 * s / n)
    vals.sort()
    return round(point, 1), round(pct(vals, 0.025), 1), round(pct(vals, 0.975), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scorecard', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--boot', type=int, default=4000)
    ap.add_argument('--seed', type=int, default=20261025)
    args = ap.parse_args()

    sc = json.load(open(args.scorecard, encoding='utf-8'))
    rows = [r for r in sc.get('per_task', []) if r.get('is_exam')]
    msr_rows = {r['task_id']: r for r in (sc.get('msr_section') or {}).get('per_task', [])}

    tsr_flags = [1 if r['tsr_pass'] else 0 for r in rows]
    spec_rows = [r for r in rows if r['category'] in ('spec_pass', 'spec_fail', 'fabricated')]
    sfr_flags = [1 if r['category'] == 'spec_pass' else 0 for r in spec_rows]
    msr_flags, msr_ids = [], []
    for r in rows:
        m = msr_rows.get(r['task_id']) or {}
        if m.get('denominator'):
            msr_flags.append(1 if m.get('msr_pass') else 0)
            msr_ids.append(r['task_id'])

    out = {
        'note': 'exam 任务的 bootstrap 百分位区间（B 次有放回重采样，单位=任务）。'
                'CI 只描述抽样波动，**不放宽 n≥20 门槛**；n<20 时任何 CI 都不得用于宣布 PASS（R12/R24）。',
        'source_scorecard': os.path.relpath(os.path.abspath(args.scorecard), HERE).replace('\\', '/'),
        'boot': args.boot, 'seed': args.seed,
        'n_exam': len(rows),
        'underpowered': len(rows) < 20,
        'exam_splits': {s: sum(1 for r in rows if r.get('split_v2') == s) for s in EXAM_SPLITS},
        'metrics': {},
    }
    for name, flags, denom in (('TSR', tsr_flags, 'exam 全部任务'),
                               ('SFR', sfr_flags, 'exam 中产出 spec 的候选'),
                               ('MSR', msr_flags, 'exam 中 spec-required 且非澄清题（R23 分母）')):
        p, lo, hi = boot_rate(flags, args.boot, args.seed)
        out['metrics'][name] = {'point_pct': p, 'ci95': [lo, hi], 'n': len(flags),
                                'n_pass': sum(flags), 'denominator': denom}

    # 分层：by_family（任务更少，只报不判）
    by_fam = {}
    for fam in sorted({r['family'] for r in rows}):
        f_rows = [r for r in rows if r['family'] == fam]
        p, lo, hi = boot_rate([1 if r['tsr_pass'] else 0 for r in f_rows], args.boot, args.seed)
        by_fam[fam] = {'n': len(f_rows), 'tsr_pct': p, 'ci95': [lo, hi],
                       'note': 'n<10，只报不判'}
    out['by_family_tsr'] = by_fam

    out_path = args.out or os.path.join(HERE, 'reports', 'bootstrap_ci.json')
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('== exam bootstrap CI ==')
    print(f"  n_exam={out['n_exam']}  underpowered={out['underpowered']}  B={args.boot} seed={args.seed}")
    for k, v in out['metrics'].items():
        print(f"  {k}: {v['n_pass']}/{v['n']} = {v['point_pct']}%  CI95 [{v['ci95'][0]}, {v['ci95'][1]}]")
    for fam, v in by_fam.items():
        print(f"  [{fam}] n={v['n']} TSR {v['tsr_pct']}% CI95 {v['ci95']}")
    print(f'report -> {out_path}')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
