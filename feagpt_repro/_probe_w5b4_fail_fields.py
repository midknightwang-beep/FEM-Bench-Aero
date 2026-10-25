# -*- coding: utf-8 -*-
"""_probe_w5b4_fail_fields.py — W5b-4 诊断探针：exam 失败条目的字段级原因

成绩单 per_task 只存了 note/ec，没存 judge_l3_candidate 的 detail.failed_fields，
导致「哪条挂了、挂在哪个字段」要重跑才能看到。本探针只为诊断，不产出官方 artifact。

用法（输出必须带里程碑标签 + 显式 --out，R37：不落 eval_runs/，官方文档不引用）：
  python _probe_w5b4_fail_fields.py --scorecard reports/baseline_scorecard_L3_v6b.json \
      --tasks reports/papers/tasks_v6b.jsonl --candidates candidates_l3_v6 \
      --out reports/diagnostics/probe_w5b4_fail_fields_v6b.json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from score_baseline import judge_l3_candidate, load_tasks  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scorecard', required=True)
    ap.add_argument('--tasks', required=True)
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    sc = json.load(open(args.scorecard, encoding='utf-8'))
    tasks = {t['task_id']: t for t in load_tasks(args.tasks) if t['input_level'] == 'L3'}
    bad = [r for r in sc.get('per_task', []) if r.get('is_exam') and not r.get('tsr_pass')]

    rows = []
    for r in bad:
        tid = r['task_id']
        t = tasks.get(tid)
        path = os.path.join(args.candidates, tid + '.json')
        if t is None or not os.path.exists(path):
            rows.append({'task_id': tid, 'skipped': True})
            continue
        cand = json.load(open(path, encoding='utf-8'))
        cand['_path'] = path
        cat, ok, detail = judge_l3_candidate(cand, t)
        rows.append({'task_id': tid, 'family': r.get('family'),
                     'exam_stratum': r.get('exam_stratum'),
                     'category': cat, 'tsr_pass': bool(ok),
                     'detail': detail})

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump({'scorecard': os.path.basename(args.scorecard),
               'n_fail': len(rows), 'rows': rows},
              open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'[probe] exam 失败 {len(rows)} 条 -> {args.out}')
    for x in rows:
        if x.get('skipped'):
            print(f"  ?? {x['task_id']}  (任务或候选缺失)")
            continue
        d = x['detail'] or {}
        ff = d.get('failed_fields')
        print(f"  {x['task_id']:<52} [{x['category']}] "
              f"fail={d.get('n_fail')}/{d.get('n_fields')} fields={ff if ff else d.get('note') or d.get('clarify') or ''}")


if __name__ == '__main__':
    main()
