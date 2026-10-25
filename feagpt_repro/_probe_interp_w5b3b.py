# -*- coding: utf-8 -*-
"""_probe_interp_w5b3b.py — 内插名额 vs train 池枯竭的量化（W5b-3b 探针，只读不写考卷）

背景：v6 的内插名额是「按族 wingbox 2 / open_hole 2 / barrel 1 / panel 1」。
实测发现 train 池被抽到只剩 wingbox：`trivial_baselines.py` 跑 v6 时
T0 众数池缺 3 个族、T1 检索库只有 13 条且全翼盒 ⇒ **三个族的检索地板无法计算**，
value_added 的对照项失真（T1 记 0/25 会让任何成绩都"有增量"）。

本探针只回答一个问题：换不同的 interp 名额，各族 train 池还剩多少？
用法：python _probe_interp_w5b3b.py [--out eval_runs/_probe_interp.json]
"""
import argparse, collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, 'reports', 'papers', 'tasks_v6.jsonl')
FAMS = ('wingbox', 'open_hole_panel', 'fuselage_barrel', 'stiffened_panel')


def load():
    rows = [json.loads(l) for l in open(TASKS, encoding='utf-8') if l.strip()]
    return [r for r in rows if r['input_level'] == 'L3']


def pool(rows, plan):
    """plan = {fam: n_interp}；返回 (train_pool_by_fam, exam_by_fam, interp_ids)"""
    train = collections.defaultdict(list)
    for r in rows:
        if r['split_v2'] == 'train':
            train[r['family']].append(r['task_id'])
    for f in train:
        train[f].sort()
    interp, taken = [], {}
    for fam, n in plan.items():
        ids = train.get(fam, [])[:n]
        if len(ids) < n:
            print(f'  [WARN] {fam} 的 train 只有 {len(train.get(fam, []))} 条 < 请求 {n}')
        interp += ids
        taken[fam] = set(ids)
    pool_n = {f: len([t for t in train.get(f, []) if t not in taken.get(f, set())]) for f in FAMS}
    exam = collections.Counter()
    for r in rows:
        if r['split_v2'] in ('boundary_holdout', 'extrapolation_test') or r['task_id'] in set(interp):
            exam[r['family']] += 1
    return pool_n, dict(exam), interp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'eval_runs', '_probe_interp_w5b3b.json'))
    args = ap.parse_args()
    rows = load()

    plans = {
        '现状 v6（2/2/1/1）': {'wingbox': 2, 'open_hole_panel': 2, 'fuselage_barrel': 1, 'stiffened_panel': 1},
        'A：全翼盒（6/0/0/0）': {'wingbox': 6},
        'C：翼盒 5 + 开孔 1': {'wingbox': 5, 'open_hole_panel': 1},
        'D：翼盒 4 + 开孔 2': {'wingbox': 4, 'open_hole_panel': 2},
    }
    out = {'tasks': os.path.relpath(TASKS, HERE).replace('\\', '/'), 'n_l3': len(rows), 'plans': {}}
    print(f'L3 任务 {len(rows)} 条；train 分布 =', dict(collections.Counter(
        r['family'] for r in rows if r['split_v2'] == 'train')))
    print(f"{'方案':<22} {'train 池(族)':<40} {'exam 族构成':<44} 可算 T1 的族")
    print('-' * 150)
    for name, plan in plans.items():
        p, exam, interp = pool(rows, plan)
        calc = [f for f in FAMS if p.get(f, 0) > 0]
        print(f"{name:<22} {str(p):<40} {str(exam):<44} {len(calc)}/4 {calc}")
        out['plans'][name] = {'plan': plan, 'train_pool': p, 'exam_by_family': exam,
                              'n_interp': len(interp), 'families_with_t1': calc,
                              'interp_ids': interp}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\nreport ->', args.out)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
