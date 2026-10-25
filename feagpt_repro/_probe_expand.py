# -*- coding: utf-8 -*-
"""W5b 扩卷设计探针：统计 L1 各族 × split 的可用 case 数，估算 L3 扩卷后 exam 规模。"""
import json, collections, sys

p = sys.argv[1] if len(sys.argv) > 1 else 'tasks/tasks.jsonl'
rows = [json.loads(ln) for ln in open(p, encoding='utf-8') if ln.strip()]
L1 = [r for r in rows if r['input_level'] == 'L1']
L3 = [r for r in rows if r['input_level'] == 'L3']
EXAM = ('boundary_holdout', 'extrapolation_test')

by = collections.Counter((r['family'], r['split_v2']) for r in L1)
fams = sorted({r['family'] for r in L1})
splits = ['train', 'val', 'boundary_holdout', 'extrapolation_test']
print(f'L1 共 {len(L1)} 条 / L3 共 {len(L3)} 条')
print(f"{'family':<20}" + ''.join(f'{s:>20}' for s in splits) + f"{'exam':>8}{'all':>6}")
tot = collections.Counter()
for f in fams:
    line = f'{f:<20}'
    ex = al = 0
    for s in splits:
        c = by[(f, s)]
        line += f'{c:>20}'
        al += c
        if s in EXAM:
            ex += c
    line += f'{ex:>8}{al:>6}'
    print(line)
print()
print('全 L3 化（把 55 条全做成 L3）后 exam 上限 =',
      sum(by[(f, s)] for f in fams for s in EXAM))
print('当前 L3 exam =', sum(1 for r in L3 if r['split_v2'] in EXAM))
# L3 当前按族
print('当前 L3 按族:', dict(collections.Counter(r['family'] for r in L3)))
print('L1 族内 case 名（用于挑扩卷名额）:')
for f in fams:
    names = [r['task_id'][3:] for r in L1 if r['family'] == f]
    print(f'  {f} ({len(names)}):', ', '.join(names[:6]), '...' if len(names) > 6 else '')
