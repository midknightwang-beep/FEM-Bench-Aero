# -*- coding: utf-8 -*-
"""W5b 扩卷验收：v6 稿 vs v5 冻结稿——① NL 文本零改动 ② 只新增 exam_stratum ③ 三栏计数正确。"""
import json, collections, sys


def load(p):
    return {json.loads(l)['task_id']: json.loads(l) for l in open(p, encoding='utf-8') if l.strip()}


v5 = load('reports/papers/nl_human_v5.jsonl')
v6 = load('eval_runs/_nl_v6.jsonl')

print(f'v5 {len(v5)} 条 / v6 {len(v6)} 条')
common = sorted(set(v5) & set(v6))
print(f'共同任务 {len(common)} 条；v6 新增 {len(set(v6) - set(v5))} 条')

bad_nl = [t for t in common if v5[t]['input']['nl'] != v6[t]['input']['nl']]
bad_ec = [t for t in common if (v5[t].get('expected_clarifications') or []) != (v6[t].get('expected_clarifications') or [])]
bad_cc = [t for t in common if v5[t].get('coordinate_convention') != v6[t].get('coordinate_convention')]
print('NL 文本改动:', bad_nl or 'NONE')
print('ec 改动:', bad_ec or 'NONE')
print('coordinate_convention 改动:', bad_cc or 'NONE')

strata = collections.Counter(r.get('exam_stratum') for r in v6.values())
print('exam_stratum:', dict(strata))
exam = [t for t, r in v6.items() if r.get('exam_stratum')]
print(f'exam 合计 {len(exam)} 条')
print('按族×分层:')
for fam in sorted({r['family'] for r in v6.values()}):
    row = {s: sum(1 for r in v6.values() if r['family'] == fam and r.get('exam_stratum') == s)
           for s in ('boundary', 'extrapolation', 'interpolation')}
    print(f"  {fam:<18} {row}  exam={sum(row.values())}")

# 内插点必须原本是 train（不得偷偷把 boundary/extrap 改成 interp）
wrong = [t for t, r in v6.items() if r.get('exam_stratum') == 'interpolation' and r['split_v2'] != 'train']
print('interp 但 split_v2≠train:', wrong or 'NONE')
# 互斥：split_v2 是 exam 的，exam_stratum 必须与之一致（不能为空）
mis = [t for t, r in v6.items()
       if r['split_v2'] in ('boundary_holdout', 'extrapolation_test') and not r.get('exam_stratum')]
print('dataset exam 但 exam_stratum 空:', mis or 'NONE')
ok = not (bad_nl or bad_ec or bad_cc or wrong or mis)
print('VERDICT:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
