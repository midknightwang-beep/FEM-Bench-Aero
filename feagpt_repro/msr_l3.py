# -*- coding: utf-8 -*-
"""
msr_l3.py — W4d 全链 MSR（红线 R14：skip_solve 不得称基线）

对 candidates_l3_v2 中产出 spec 的候选逐条走 evaluate_one 全链
（契约闸 → run_pipeline(ccx) → 关1 网格 → 关4 语义 → fidelity_disp → spec_fidelity）。
ccx 串行（绝不并行，环境铁律）。输出合并进 baseline_scorecard_L3.json 的 msr 节。

MSR = 全链 gates 全 PASS 的候选 / 全部 30 条任务（无 spec 候选计 FAIL）。
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS

CAND_DIR = os.path.join(HERE, 'candidates_l3_v2')
REPORT = os.path.join(RUNS, 'baseline_scorecard_L3.json')


def main():
    tasks = {t['task_id']: t for t in load_tasks(os.path.join(HERE, 'tasks', 'tasks.jsonl'))
             if t['input_level'] == 'L3'}
    cands = {}
    for fn in sorted(os.listdir(CAND_DIR)):
        if fn.endswith('.json'):
            c = json.load(open(os.path.join(CAND_DIR, fn), encoding='utf-8'))
            cands[c['task_id']] = c

    rows = []
    for tid in sorted(tasks):
        t = tasks[tid]
        c = cands.get(tid) or {}
        if not c.get('spec'):
            rows.append({'task_id': tid, 'msr_pass': False,
                         'reason': 'no spec (clarify/unresolved/fabricated-rejected)'})
            print(f"  [--] {tid}: no spec -> FAIL")
            continue
        try:
            r = evaluate_one(t, os.path.join(CAND_DIR, tid + '.json'), skip_solve=False,
                             timeout=1800)
        except Exception as e:
            rows.append({'task_id': tid, 'msr_pass': False, 'reason': f'exception: {e}'})
            print(f"  [!!] {tid}: exception {e}")
            continue
        gates = {k: bool(v.get('pass')) for k, v in r['gates'].items()}
        ok = bool(r.get('overall_pass'))
        rows.append({'task_id': tid, 'msr_pass': ok, 'gates': gates,
                     'pipeline_rc': r.get('pipeline_rc'),
                     'wall_seconds': r.get('wall_seconds'),
                     'fidelity_dev_pct': r.get('fidelity_disp_dev_pct')})
        bad = [k for k, v in gates.items() if not v]
        print(f"  [{'ok' if ok else 'FAIL'}] {tid}: gates={gates} "
              f"fidelity={r.get('fidelity_disp_dev_pct','n/a')}% wall={r.get('wall_seconds')}s"
              + (f" bad={bad}" if bad else ''))

    n = len(rows)
    p = sum(1 for r in rows if r['msr_pass'])
    msr = {'note': '全链 MSR（红线 R14）：契约闸+ccx 求解+关1网格+关4语义+fidelity+spec_fidelity 全 PASS；'
                   '分母=全部 30 条任务（无 spec 候选计 FAIL）。串行 ccx。',
           'msr': f'{p}/{n}', 'msr_pct': round(100 * p / max(1, n), 1),
           'gate_fail_counts': dict(collections.Counter(
               k for r in rows for k, v in (r.get('gates') or {}).items() if not v)),
           'per_task': rows}
    sc = json.load(open(REPORT, encoding='utf-8'))
    sc['msr_section'] = msr
    json.dump(sc, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nMSR = {p}/{n} ({msr['msr_pct']}%)  gate_fail={msr['gate_fail_counts']}")
    print('merged ->', REPORT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
