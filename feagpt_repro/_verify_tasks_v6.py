# -*- coding: utf-8 -*-
"""W5b 验收：新 tasks.jsonl(165) vs v5 冻结稿——L1/L2 必须逐字节不变，L3 老 30 条只加 exam_stratum。"""
import json, collections, sys


def load(p):
    return {json.loads(l)['task_id']: json.loads(l) for l in open(p, encoding='utf-8') if l.strip()}


old = load('reports/papers/tasks_v5.jsonl')      # 140 行（L1 55 + L2 55 + L3 30）
new = load('tasks/tasks.jsonl')                  # 165 行（L3 55）
print(f'old {len(old)} / new {len(new)}')

l1l2_old = {k: v for k, v in old.items() if v['input_level'] in ('L1', 'L2')}
l1l2_new = {k: v for k, v in new.items() if v['input_level'] in ('L1', 'L2')}
diff1212 = [k for k in l1l2_old if json.dumps(l1l2_old[k], sort_keys=True, ensure_ascii=False)
            != json.dumps(l1l2_new.get(k), sort_keys=True, ensure_ascii=False)]
print('L1/L2 内容改动:', diff1212[:5] or 'NONE', f'（{len(diff1212)} 条）')

l3_old = {k: v for k, v in old.items() if v['input_level'] == 'L3'}
l3_new = {k: v for k, v in new.items() if v['input_level'] == 'L3'}
common = sorted(set(l3_old) & set(l3_new))
print(f'L3 老 {len(l3_old)} 条 / 新 {len(l3_new)} 条 / 共同 {len(common)} 条')

strip = lambda r: {k: v for k, v in r.items() if k != 'exam_stratum'}
bad = [k for k in common if json.dumps(strip(l3_old[k]), sort_keys=True, ensure_ascii=False)
       != json.dumps(strip(l3_new[k]), sort_keys=True, ensure_ascii=False)]
print('L3 老题除 exam_stratum 外的改动:', bad[:5] or 'NONE')

strata = collections.Counter(r.get('exam_stratum') for r in l3_new.values())
print('新考卷 exam_stratum:', dict(strata))
exam = sum(1 for r in l3_new.values() if r.get('exam_stratum'))
print(f'exam = {exam}（应 25）')

# 内插点必须来自 train
weird = [k for k, r in l3_new.items() if r.get('exam_stratum') == 'interpolation' and r['split_v2'] != 'train']
print('interp 非 train:', weird or 'NONE')
# 互斥：老 30 条里原来 is_exam 的仍是 boundary/extrapolation
changed_stratum = [k for k in common
                   if (l3_old[k]['split_v2'] in ('boundary_holdout', 'extrapolation_test'))
                   != (l3_new[k].get('exam_stratum') in ('boundary', 'extrapolation'))]
print('老题 exam 身份变动:', changed_stratum or 'NONE')

ok = (not diff1212) and (not bad) and exam == 25 and not weird and not changed_stratum
print('VERDICT:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
