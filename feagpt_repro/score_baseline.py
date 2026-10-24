# -*- coding: utf-8 -*-
"""
score_baseline.py — W4b-2 基线成绩单（spec_fidelity 判分，skip_solve 快通道）

读 candidates/*.json（gen_candidates.js 产物）→ 逐条 spec_fidelity → 汇总：
  - TSR / FPR（overall = spec_fidelity PASS；FPR 另需一次性生成，此处报首轮即终轮的 TSR）
  - ID/OOD 分报（boundary_holdout = B、extrapolation_test = OOD——注意 W4a 定名后两者都是外推族，
    ID 内插留 v1.1；成绩单按 split_v2 分列不合并）
  - value_added = TSR_LLM − TSR_T1（对照 eval_runs/trivial_baselines.json）
  - 失败归因：clarify / schema 无效 / 字段错（spec_fidelity.failed 前三）
输出：eval_runs/baseline_scorecard.json
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS

def main(cand_dir):
    tasks = {t['task_id']: t for t in load_tasks(os.path.join(HERE, 'tasks', 'tasks.jsonl'))
             if t['input_level'] == 'L1'}
    trivial = json.load(open(os.path.join(RUNS, 'trivial_baselines.json'), encoding='utf-8'))
    rows = []
    for fn in sorted(os.listdir(cand_dir)):
        if not fn.endswith('.json'):
            continue
        cand = json.load(open(os.path.join(cand_dir, fn), encoding='utf-8'))
        tid = cand.get('task_id')
        t = tasks.get(tid)
        if t is None:
            continue
        if cand.get('clarify') and not cand.get('spec'):
            rows.append({'task_id': tid, 'split_v2': t['split_v2'], 'family': t['family'],
                         'pass': False, 'outcome': 'clarify',
                         'detail': cand['clarify'][:120]})
            continue
        if cand.get('error'):
            rows.append({'task_id': tid, 'split_v2': t['split_v2'], 'family': t['family'],
                         'pass': False, 'outcome': 'llm_error', 'detail': cand['error']})
            continue
        cp = os.path.join(cand_dir, fn)
        r = evaluate_one(t, cp, skip_solve=True)
        sf = r['gates'].get('spec_fidelity', {})
        failed = [f['field'] for f in (sf.get('failed') or [])]
        # 归因：schema 合法性在生成侧由 prompt 约束，此处字段错细分
        rows.append({'task_id': tid, 'split_v2': t['split_v2'], 'family': t['family'],
                     'pass': r['overall_pass'], 'outcome': 'judged',
                     'n_fields': sf.get('n_fields'), 'n_fail_fields': sf.get('n_fail'),
                     'failed_fields': failed[:6]})

    def tsr(sub):
        s = [r for r in rows if r['split_v2'] in sub]
        p = sum(1 for r in s if r['pass'])
        return {'tsr': f'{p}/{len(s)}', 'pct': round(100 * p / max(1, len(s)), 1), 'n': len(s)}

    splits_present = sorted({r['split_v2'] for r in rows})
    n_tasks_l1 = 19
    partial = len(rows) < n_tasks_l1
    scorecard = {'note': 'W4c：SFR（spec_fidelity，skip_solve）口径。MSR（全链）未跑时不得到处宣称模型基线（红线 R9/R14）。',
                 'n_candidates': len(rows), 'n_tasks_exam': n_tasks_l1,
                 'partial': partial,
                 'partial_warning': f'WARNING: partial candidate set ({len(rows)}/{n_tasks_l1})' if partial else None,
                 'underpowered': len(rows) < 20,
                 'by_split': {s: tsr([s]) for s in splits_present},
                 'exam': tsr(('boundary_holdout', 'extrapolation_test')),
                 'outcome_counts': dict(collections.Counter(r['outcome'] for r in rows)),
                 'failure_attribution': dict(collections.Counter(
                     (r['failed_fields'] or ['n/a'])[0] if r['outcome'] == 'judged' and not r['pass']
                     else r['outcome'] for r in rows if not r['pass'])),
                 'per_task': rows}
    # value_added
    t1 = trivial['T1_retrieval']['exam_pct']
    scorecard['value_added'] = {
        'TSR_T1_pct': t1,
        'TSR_LLM_pct': scorecard['exam']['pct'],
        'delta_pp': round(scorecard['exam']['pct'] - t1, 1),
        'criterion': '≥ 10 pp 才算 LLM 真有增量（专家 6.3.1）',
        'verdict': ('UNDERPOWERED (n<20, 红线 R12)' if len(rows) < 20 else
                        ('PASS' if scorecard['exam']['pct'] - t1 >= 10 else 'BELOW')),
    }
    out = os.path.join(RUNS, 'baseline_scorecard.json')
    json.dump(scorecard, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('== LLM 基线成绩单 ==')
    for s, v in scorecard['by_split'].items():
        print(f"  {s:22s} TSR {v['tsr']} ({v['pct']}%)")
    print(f"  考卷合计 TSR {scorecard['exam']['tsr']} ({scorecard['exam']['pct']}%)")
    print(f"  归因: {scorecard['failure_attribution']}")
    print(f"  value_added: T1 {t1}% → LLM {scorecard['exam']['pct']}% "
          f"(Δ{scorecard['value_added']['delta_pp']}pp, {scorecard['value_added']['verdict']})")
    print('report ->', out)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'candidates')))
